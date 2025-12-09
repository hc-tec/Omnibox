"""
模板 API Schemas

Phase 4: 模板市场相关的请求/响应模型
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class VariableSchema(BaseModel):
    """变量定义 Schema"""
    name: str
    var_type: str  # string | number | boolean | datasource | list
    description: str = ""
    default: Optional[Any] = None
    required: bool = True
    enum_values: Optional[List[Any]] = None


class TemplateListQuery(BaseModel):
    """模板列表查询参数"""
    category: Optional[str] = Field(None, description="按分类筛选")
    tags: Optional[List[str]] = Field(None, description="按标签筛选")
    search: Optional[str] = Field(None, description="搜索关键词")
    sort_by: str = Field("usage_count", description="排序方式: usage_count | created_at | name")
    limit: int = Field(20, ge=1, le=100, description="返回数量")
    offset: int = Field(0, ge=0, description="偏移量")


class TemplateResponse(BaseModel):
    """模板响应"""
    template_id: str
    name: str
    description: str
    category: Optional[str] = None
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    usage_count: int = 0
    preview_image: Optional[str] = None
    version: str = "1.0.0"

    # 变量定义
    variables: Dict[str, VariableSchema] = Field(default_factory=dict)

    # 步骤概要
    step_count: int = 0
    step_types: List[str] = Field(default_factory=list)

    created_at: str
    updated_at: str


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    templates: List[TemplateResponse]
    total: int
    categories: Dict[str, int] = Field(default_factory=dict)


class CreateTemplateRequest(BaseModel):
    """创建模板请求"""
    workflow_id: str = Field(..., description="源工作流 ID")
    category: str = Field("custom", description="模板分类")
    author: str = Field("anonymous", description="作者")
    preview_image: Optional[str] = Field(None, description="预览图 URL")
    tags: Optional[List[str]] = Field(None, description="标签")


class InstantiateRequest(BaseModel):
    """实例化模板请求"""
    variable_values: Dict[str, Any] = Field(default_factory=dict, description="变量值")
    new_name: Optional[str] = Field(None, description="新工作流名称")


class InstantiateResponse(BaseModel):
    """实例化响应"""
    workflow_id: str
    name: str
    status: str
    template_source_id: str


class ValidateVariablesRequest(BaseModel):
    """变量校验请求"""
    variable_values: Dict[str, Any]


class ValidateVariablesResponse(BaseModel):
    """变量校验响应"""
    valid: bool
    errors: List[str] = Field(default_factory=list)


class ImportTemplateRequest(BaseModel):
    """导入模板请求"""
    template_data: Dict[str, Any] = Field(..., description="模板 JSON 数据")
    author: str = Field("imported", description="导入后的作者标记")


class CategoryStats(BaseModel):
    """分类统计"""
    category: str
    label: str
    count: int


class TemplateStatsResponse(BaseModel):
    """模板市场统计响应"""
    total: int
    categories: List[CategoryStats]
