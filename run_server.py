#!/usr/bin/env python
"""
FastAPI 服务器启动脚本

使用方式：
    python run_server.py              # 开发模式（热重载）
    python run_server.py --prod       # 生产模式
    python run_server.py --port 8080  # 自定义端口
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="启动 FastAPI 服务器")
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="监听地址（默认：0.0.0.0）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8002,
        help="监听端口（默认：8002）"
    )
    parser.add_argument(
        "--prod",
        action="store_true",
        help="生产模式（禁用热重载）"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="debug",
        choices=["debug", "info", "warning", "error"],
        help="日志级别（默认：info）"
    )

    args = parser.parse_args()

    print(f"启动 FastAPI 服务器...")
    print(f"地址: http://{args.host}:{args.port}")
    print(f"模式: {'生产' if args.prod else '开发（热重载）'}")
    print(f"日志级别: {args.log_level}")
    print("-" * 50)

    uvicorn.run(
        "api.app:app",
        host=args.host,
        port=args.port,
        reload=not args.prod,  # 开发模式启用热重载
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
