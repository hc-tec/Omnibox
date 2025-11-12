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
from api.controllers.research_stream import router as research_stream_router
from api.controllers.research_controller import router as research_router
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
    app.include_router(chat_stream_router)  # WebSocket流式接口
    app.include_router(research_stream_router)  # WebSocket研究流式接口
    app.include_router(research_router)

    # ========== 启动和关闭事件 ==========
    @app.on_event("startup")
    async def startup_event():
        """应用启动事件"""
        logger.info("应用启动中...")
        try:
            initialize_services()
            logger.info("✓ 应用启动完成")
        except Exception as e:
            logger.error(f"应用启动失败: {e}", exc_info=True)
            raise

    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭事件"""
        logger.info("应用关闭中...")
        try:
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
