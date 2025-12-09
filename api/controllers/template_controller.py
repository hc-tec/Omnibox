"""
模板 API Controller

Phase 4: 模板市场相关 API 端点
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from services.workflow import (
    get_workflow_store,
    get_template_service,
    TemplateCategory,
)
from api.schemas.template import (
    TemplateListQuery,
    TemplateResponse,
    TemplateListResponse,
    CreateTemplateRequest,
    InstantiateRequest,
    InstantiateResponse,
    ValidateVariablesRequest,
    ValidateVariablesResponse,
    ImportTemplateRequest,
    CategoryStats,
    TemplateStatsResponse,
    VariableSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


# ========== 分类映射 ==========

CATEGORY_LABELS = {
    "data_analysis": "数据分析",
    "content_research": "内容研究",
    "competitive": "竞品分析",
    "social_monitoring": "社交监控",
    "report_generation": "报告生成",
    "custom": "自定义",
}


def _workflow_to_template_response(workflow) -> TemplateResponse:
    """将 Workflow 转换为 TemplateResponse"""
    steps = workflow.get_steps()
    variables = workflow.get_variables()

    return TemplateResponse(
        template_id=workflow.workflow_id,
        name=workflow.name,
        description=workflow.description,
        category=workflow.category,
        author=workflow.author,
        tags=workflow.get_tags(),
        usage_count=workflow.usage_count,
        preview_image=workflow.preview_image,
        version=workflow.version,
        variables={
            name: VariableSchema(
                name=var.name,
                var_type=var.var_type.value if hasattr(var.var_type, 'value') else var.var_type,
                description=var.description,
                default=var.default,
                required=var.required,
                enum_values=var.enum_values,
            )
            for name, var in variables.items()
        },
        step_count=len(steps),
        step_types=list(set(s.step_type.value for s in steps)),
        created_at=workflow.created_at.isoformat(),
        updated_at=workflow.updated_at.isoformat(),
    )


# ========== 模板列表 ==========

@router.get("", response_model=TemplateListResponse)
async def list_templates(
    category: Optional[str] = Query(None, description="按分类筛选"),
    tags: Optional[str] = Query(None, description="按标签筛选，逗号分隔"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    sort_by: str = Query("usage_count", description="排序: usage_count | created_at | name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    获取模板列表

    支持分类筛选、标签筛选、关键词搜索、排序
    """
    store = get_workflow_store()

    # 解析标签
    tag_list = tags.split(",") if tags else None

    # 查询
    templates, total = store.list_templates(
        category=category,
        tags=tag_list,
        search=search,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
    )

    # 获取分类统计
    stats = store.get_template_stats()

    return TemplateListResponse(
        templates=[_workflow_to_template_response(t) for t in templates],
        total=total,
        categories=stats.get("by_category", {}),
    )


@router.get("/categories", response_model=List[CategoryStats])
async def list_categories():
    """
    获取模板分类列表及统计
    """
    store = get_workflow_store()
    stats = store.get_template_stats()
    by_category = stats.get("by_category", {})

    result = []
    for cat in TemplateCategory:
        result.append(CategoryStats(
            category=cat.value,
            label=CATEGORY_LABELS.get(cat.value, cat.value),
            count=by_category.get(cat.value, 0),
        ))

    return result


@router.get("/stats", response_model=TemplateStatsResponse)
async def get_template_stats():
    """
    获取模板市场统计
    """
    store = get_workflow_store()
    stats = store.get_template_stats()

    categories = [
        CategoryStats(
            category=cat,
            label=CATEGORY_LABELS.get(cat, cat),
            count=count,
        )
        for cat, count in stats.get("by_category", {}).items()
    ]

    return TemplateStatsResponse(
        total=stats.get("total", 0),
        categories=categories,
    )


# ========== 模板详情 ==========

@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str):
    """
    获取模板详情
    """
    store = get_workflow_store()
    workflow = store.load_workflow(template_id)

    if not workflow:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")

    if not workflow.is_template:
        raise HTTPException(status_code=400, detail=f"{template_id} 不是模板")

    return _workflow_to_template_response(workflow)


# ========== 创建模板 ==========

@router.post("", response_model=TemplateResponse)
async def create_template(request: CreateTemplateRequest):
    """
    从工作流创建模板
    """
    service = get_template_service()

    template = service.create_template_from_workflow(
        workflow_id=request.workflow_id,
        category=request.category,
        author=request.author,
        preview_image=request.preview_image,
        tags=request.tags,
    )

    if not template:
        raise HTTPException(status_code=400, detail="创建模板失败，请检查源工作流是否存在")

    return _workflow_to_template_response(template)


# ========== 实例化模板 ==========

@router.post("/{template_id}/instantiate", response_model=InstantiateResponse)
async def instantiate_template(template_id: str, request: InstantiateRequest):
    """
    从模板创建工作流实例
    """
    service = get_template_service()

    workflow = service.instantiate_template(
        template_id=template_id,
        variable_values=request.variable_values,
        new_name=request.new_name,
    )

    if not workflow:
        raise HTTPException(status_code=400, detail="实例化失败，请检查变量值是否正确")

    return InstantiateResponse(
        workflow_id=workflow.workflow_id,
        name=workflow.name,
        status=workflow.status,
        template_source_id=template_id,
    )


# ========== 变量校验 ==========

@router.post("/{template_id}/validate", response_model=ValidateVariablesResponse)
async def validate_variables(template_id: str, request: ValidateVariablesRequest):
    """
    校验变量值是否满足模板要求
    """
    service = get_template_service()

    errors = service.validate_variable_values(
        template_id=template_id,
        values=request.variable_values,
    )

    return ValidateVariablesResponse(
        valid=len(errors) == 0,
        errors=errors,
    )


# ========== 导出模板 ==========

@router.get("/{template_id}/export")
async def export_template(template_id: str):
    """
    导出模板为 JSON
    """
    service = get_template_service()

    export = service.export_template(template_id)

    if not export:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")

    return export.model_dump()


# ========== 导入模板 ==========

@router.post("/import", response_model=TemplateResponse)
async def import_template(request: ImportTemplateRequest):
    """
    从 JSON 导入模板
    """
    service = get_template_service()

    template = service.import_template(
        template_data=request.template_data,
        author=request.author,
    )

    if not template:
        raise HTTPException(status_code=400, detail="导入失败，请检查 JSON 格式")

    return _workflow_to_template_response(template)
