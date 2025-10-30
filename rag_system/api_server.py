"""
RAG系统API服务器（可选）
提供REST API接口用于路由检索
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
import logging

from rag_pipeline import RAGPipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI应用
app = FastAPI(
    title="RAG路由检索API",
    description="基于语义向量的智能路由检索服务",
    version="1.0.0",
)

# 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局RAG管道实例
pipeline = None


# 请求/响应模型
class SearchRequest(BaseModel):
    query: str = Field(..., description="查询文本", min_length=1, max_length=500)
    top_k: int = Field(5, description="返回结果数量", ge=1, le=20)
    filter_datasource: Optional[str] = Field(None, description="过滤特定数据源")


class RouteResult(BaseModel):
    route_id: str
    similarity_score: float
    route_definition: Dict[str, Any]


class SearchResponse(BaseModel):
    query: str
    results: List[RouteResult]
    total_results: int


class StatsResponse(BaseModel):
    total_documents: int
    datasource_distribution: Dict[str, int]
    collection_name: str
    distance_metric: str


# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化RAG管道"""
    global pipeline
    logger.info("正在初始化RAG管道...")

    try:
        pipeline = RAGPipeline()

        # 检查是否有索引
        count = pipeline.vector_store.collection.count()
        if count == 0:
            logger.warning("向量数据库为空，请先构建索引！")
            logger.info("运行命令: python rag_pipeline.py --build")
        else:
            logger.info(f"✓ RAG系统初始化完成，当前索引数量: {count}")

    except Exception as e:
        logger.error(f"初始化失败: {e}")
        raise


# API端点
@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "RAG路由检索API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    count = pipeline.vector_store.collection.count()
    return {
        "status": "healthy",
        "index_count": count,
    }


@app.post("/search", response_model=SearchResponse)
async def search_routes(request: SearchRequest):
    """
    搜索路由

    示例请求：
    ```json
    {
        "query": "虎扑步行街热帖",
        "top_k": 5,
        "filter_datasource": null
    }
    ```
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    try:
        # 执行搜索
        results = pipeline.search(
            query=request.query,
            top_k=request.top_k,
            filter_datasource=request.filter_datasource,
            verbose=False,
        )

        # 转换为响应格式
        route_results = [
            RouteResult(
                route_id=route_id,
                similarity_score=score,
                route_definition=route_def,
            )
            for route_id, score, route_def in results
        ]

        return SearchResponse(
            query=request.query,
            results=route_results,
            total_results=len(route_results),
        )

    except Exception as e:
        logger.error(f"搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/route/{route_id}")
async def get_route(route_id: str):
    """
    根据route_id获取完整路由定义

    示例：GET /route/hupu_bbs
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    route_def = pipeline.get_route_by_id(route_id)

    if route_def is None:
        raise HTTPException(status_code=404, detail=f"路由 {route_id} 不存在")

    return {
        "route_id": route_id,
        "route_definition": route_def,
    }


@app.get("/stats", response_model=StatsResponse)
async def get_statistics():
    """
    获取系统统计信息

    示例：GET /stats
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    stats = pipeline.vector_store.get_statistics()
    return StatsResponse(**stats)


@app.post("/rebuild_index")
async def rebuild_index(force: bool = True):
    """
    重建向量索引

    警告：这是一个耗时操作，会阻塞服务

    示例：POST /rebuild_index?force=true
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="服务未就绪")

    try:
        logger.info("开始重建索引...")
        pipeline.build_index(force_rebuild=force)
        logger.info("索引重建完成")

        return {
            "status": "success",
            "message": "索引重建完成",
            "index_count": pipeline.vector_store.collection.count(),
        }

    except Exception as e:
        logger.error(f"重建索引失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 主函数
def main():
    """启动API服务器"""
    import argparse

    parser = argparse.ArgumentParser(description="RAG API服务器")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--reload", action="store_true", help="开发模式（自动重载）")

    args = parser.parse_args()

    logger.info(f"启动API服务器: http://{args.host}:{args.port}")
    logger.info(f"API文档: http://{args.host}:{args.port}/docs")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
