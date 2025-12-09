"""
FastAPI应用实例
整合Controller、中间件和配置
"""

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.controllers.chat_controller import (
    router as chat_router,
    initialize_services,
    shutdown_services,
)
from api.controllers.chat_stream import router as chat_stream_router
from api.controllers.research_controller import router as research_router
from api.controllers.subscription_controller import router as subscription_router
from api.controllers.workflow_controller import router as workflow_router
from api.controllers.template_controller import router as template_router
from api.controllers.dashboard_controller import router as dashboard_router  # Pin panel endpoint added
from api.controllers.session_controller import (
    router as session_router,
    initialize_session_services,
    shutdown_session_services,
)
from api.middleware.exception_handlers import (
    exception_handler_middleware,
    http_exception_handler,
    validation_exception_handler,
    add_process_time_header_middleware,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    创建FastAPI应用实例

    配置：
    - API路由
    - 异常处理中间件
    - CORS中间件
    - 启动和关闭事件

    Returns:
        FastAPI应用实例
    """
    app = FastAPI(
        title="RSS聚合API",
        description="基于RAG的智能RSS数据聚合服务",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ========== 注册中间件 ==========
    # CORS中间件（允许跨域请求）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 添加处理时间头中间件
    app.middleware("http")(add_process_time_header_middleware)

    # 异常处理中间件（捕获未处理的异常）
    app.middleware("http")(exception_handler_middleware)

    # ========== 注册异常处理器 ==========
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # ========== 注册路由 ==========
    app.include_router(chat_router)
    app.include_router(chat_stream_router)  # 统一的 WebSocket 流式接口（支持普通查询和研究模式）
    app.include_router(research_router)
    app.include_router(subscription_router)  # 订阅管理接口
    app.include_router(workflow_router)  # 工作流管理接口
    app.include_router(template_router)  # 模板市场接口
    app.include_router(dashboard_router)  # 仪表盘接口
    app.include_router(session_router)  # Session 管理接口

    # ========== 启动和关闭事件 ==========
    @app.on_event("startup")
    async def startup_event():
        """应用启动事件"""
        logger.info("应用启动中...")
        try:
            initialize_services()
            # 初始化 Session 服务（需要 LLM 和 DataQueryService）
            try:
                from api.controllers.chat_controller import _chat_service
                if _chat_service and hasattr(_chat_service, 'data_query_service'):
                    # ChatService 存储 LLM 为 _llm_client（私有属性）
                    llm_client = getattr(_chat_service, '_llm_client', None)
                    data_query_service = getattr(_chat_service, 'data_query_service', None)
                    initialize_session_services(
                        llm_client=llm_client,
                        data_query_service=data_query_service
                    )
                    logger.info("✓ Session 服务初始化完成")
            except Exception as session_exc:
                logger.warning(f"Session 服务初始化失败（非致命）: {session_exc}")
            logger.info("✓ 应用启动完成")
        except Exception as e:
            logger.error(f"应用启动失败: {e}", exc_info=True)
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭事件"""
        logger.info("应用关闭中...")
        try:
            shutdown_session_services()
            shutdown_services()
            logger.info("✓ 应用已关闭")
        except Exception as e:
            logger.error(f"应用关闭失败: {e}", exc_info=True)

    # ========== 根路径 ==========
    @app.get("/", tags=["root"])
    async def root(request: Request):
        """根路径，返回API信息"""
        base_url = request.base_url
        ws_scheme = "wss" if base_url.scheme == "https" else "ws"

        if base_url.port:
            websocket_url = f"{ws_scheme}://{base_url.hostname}:{base_url.port}/api/v1/chat/stream"
        else:
            websocket_url = f"{ws_scheme}://{base_url.hostname}/api/v1/chat/stream"

        return {
            "name": "RSS聚合API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "endpoints": {
                "rest": str(base_url.replace(path="/api/v1/chat")),
                "websocket": websocket_url,
            }
        }

    return app


# 创建应用实例
app = create_app()


if __name__ == "__main__":
    import uvicorn

    # 开发模式运行
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式启用热重载
        log_level="info",
    )
