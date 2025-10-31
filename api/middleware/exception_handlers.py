"""
异常处理中间件
职责：统一处理API异常，返回标准错误响应
"""

import logging
import time
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def exception_handler_middleware(request: Request, call_next):
    """
    异常处理中间件

    捕获所有未处理的异常，返回统一的错误响应格式

    Args:
        request: FastAPI请求对象
        call_next: 下一个中间件或路由处理器

    Returns:
        响应对象
    """
    start_time = time.time()

    try:
        response = await call_next(request)
        return response

    except Exception as e:
        # 记录异常
        process_time = time.time() - start_time
        logger.error(
            f"未捕获异常: {type(e).__name__}: {str(e)} "
            f"[{request.method} {request.url.path}] "
            f"({process_time:.2f}s)",
            exc_info=True
        )

        # 返回统一错误响应
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "message": "服务器内部错误",
                "error_code": "INTERNAL_ERROR",
                "detail": str(e),
            },
        )


def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    HTTP异常处理器

    处理HTTPException，返回统一格式

    Args:
        request: 请求对象
        exc: HTTP异常

    Returns:
        JSON响应
    """
    logger.warning(
        f"HTTP异常: {exc.status_code} {exc.detail} "
        f"[{request.method} {request.url.path}]"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
        },
    )


def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    请求验证异常处理器

    处理Pydantic验证错误，返回详细的验证错误信息

    Args:
        request: 请求对象
        exc: 验证异常

    Returns:
        JSON响应
    """
    logger.warning(
        f"请求验证失败: {exc.errors()} "
        f"[{request.method} {request.url.path}]"
    )

    # 提取验证错误信息
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "请求参数验证失败",
            "error_code": "VALIDATION_ERROR",
            "detail": errors,
        },
    )


async def add_process_time_header_middleware(request: Request, call_next):
    """
    添加处理时间头中间件

    为每个响应添加X-Process-Time头，记录处理时间

    Args:
        request: 请求对象
        call_next: 下一个中间件或路由处理器

    Returns:
        响应对象
    """
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    return response
