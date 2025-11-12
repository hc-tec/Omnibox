"""
数据执行器 - RSS数据获取与解析
职责：
1. 调用RSSHub API（本地优先，支持降级）
2. 健康检查
3. 数据标准化
4. 错误处理和重试
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal, Dict, Any, Tuple
import httpx
import logging
from datetime import datetime
from urllib.parse import quote, parse_qsl, urlencode

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """
    数据获取结果

    包含从RSSHub获取的所有数据项和元信息
    """
    status: Literal["success", "error"]
    items: List[Dict[str, Any]]              # 原始数据项列表
    source: Literal["local", "fallback"]     # 数据来源
    feed_title: Optional[str] = None         # Feed标题
    feed_link: Optional[str] = None          # Feed链接
    feed_description: Optional[str] = None   # Feed描述
    error_message: Optional[str] = None
    fetched_at: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now().isoformat()


class DataExecutor:
    """
    RSS数据执行器（同步版本）

    职责：
    - 调用RSSHub获取RSS数据（JSON格式）
    - 健康检查
    - 本地优先
    - 数据标准化

    使用示例：
        executor = DataExecutor()
        result = executor.fetch_rss("/bilibili/user/video/2267573")
        if result.status == "success":
            for item in result.items:
                print(item.get("title"))
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1200",
        health_check_timeout: int = 3,
        request_timeout: int = 30,
        max_retries: int = 2,
    ):
        """
        初始化数据执行器

        Args:
            base_url: 本地RSSHub地址
            health_check_timeout: 健康检查超时（秒）
            request_timeout: 请求超时（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.health_check_timeout = health_check_timeout
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        # 使用同步httpx客户端
        self.client = httpx.Client(
            timeout=request_timeout,
            follow_redirects=True,
        )

        # 健康状态缓存
        self._local_healthy: Optional[bool] = None
        self._last_health_check: Optional[datetime] = None

        logger.info("DataExecutor初始化: 本地=%s", self.base_url)

    def ensure_rsshub_alive(self) -> bool:
        """
        健康检查：检查本地RSSHub是否可用

        Returns:
            True表示本地RSSHub健康
        """
        try:
            response = self.client.get(
                self.base_url,
                timeout=self.health_check_timeout
            )
            healthy = response.status_code == 200
            self._local_healthy = healthy
            self._last_health_check = datetime.now()

            if healthy:
                logger.info(f"✓ 本地RSSHub健康检查通过: {self.base_url}")
            else:
                logger.warning(
                    f"本地RSSHub响应异常: 状态码={response.status_code}"
                )

            return healthy

        except Exception as e:
            logger.warning(f"本地RSSHub不可达: {e}")
            self._local_healthy = False
            self._last_health_check = datetime.now()
            return False

    def fetch_rss(self, path: str) -> FetchResult:
        """
        获取并解析RSS数据（JSON格式）

        策略：
        1. 尝试本地RSSHub
        2. 失败则返回错误

        Args:
            path: RSSHub路径，如 "/hupu/bbs/bxj/1"

        Returns:
            FetchResult包含文章列表和来源信息
        """
        # 确保path以/开头
        if not path.startswith('/'):
            path = '/' + path

        # 1. 优先尝试本地
        logger.info(f"开始获取RSS数据: {path}")
        result = self._try_fetch(self.base_url, path, "local")

        if result.status == "success":
            logger.info("✓ 本地获取成功: %d条数据", len(result.items))
        else:
            logger.error("✗ 本地获取失败: %s", result.error_message)

        return result

    def _try_fetch(
        self,
        base_url: str,
        path: str,
        source: Literal["local", "fallback"]
    ) -> FetchResult:
        """
        内部方法：尝试从指定URL获取数据

        使用RSSHub的JSON格式：在URL后加 ?format=json
        """
        # 构造完整URL（含format=json参数），确保特殊字符安全
        url = self._build_request_url(base_url, path)

        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(
                    f"请求RSS ({source}): {url} [尝试 {attempt + 1}/{self.max_retries + 1}]"
                )

                # 发送HTTP GET请求
                response = self.client.get(url)
                response.raise_for_status()

                # 解析 JSON
                data = response.json()

                if isinstance(data, dict):
                    payload = data
                    feed_title = data.get("title")
                    feed_link = data.get("link")
                    feed_description = data.get("description")
                else:
                    payload = {"value": data}
                    feed_title = None
                    feed_link = None
                    feed_description = None

                logger.info(
                    "✓ 成功获取数据 (%s): %s",
                    source,
                    path,
                )

                return FetchResult(
                    status="success",
                    items=[payload],
                    source=source,
                    feed_title=feed_title,
                    feed_link=feed_link,
                    feed_description=feed_description,
                    payload=payload,
                )

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP错误 ({source}): {e.response.status_code} - {url}"
                )
                error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"

            except httpx.RequestError as e:
                logger.error(f"请求错误 ({source}): {e}")
                error_msg = f"请求失败: {str(e)}"

            except ValueError as e:
                logger.error(f"JSON解析错误 ({source}): {e}")
                error_msg = f"数据格式错误: {str(e)}"

            except Exception as e:
                logger.error(f"未知错误 ({source}): {e}")
                error_msg = f"未知错误: {str(e)}"

            # 如果不是最后一次尝试，继续重试
            if attempt < self.max_retries:
                logger.debug(f"准备重试 ({attempt + 2}/{self.max_retries + 1})")

        # 所有重试都失败
        return FetchResult(
            status="error",
            items=[],
            source=source,
            error_message=error_msg,
        )


    def _build_request_url(self, base_url: str, path: str) -> str:
        """
        构建完整请求URL，确保路径安全编码并追加format=json参数
        """
        normalized_base = base_url.rstrip('/')

        clean_path, query_string = self._split_path_and_query(path)
        encoded_path = self._encode_path(clean_path)

        query_params = self._build_query_params(query_string)
        query_string = urlencode(query_params, doseq=True)

        full_url = f"{normalized_base}{encoded_path}"
        if query_string:
            full_url = f"{full_url}?{query_string}"

        return full_url

    @staticmethod
    def _split_path_and_query(path: str) -> Tuple[str, str]:
        """
        拆分路径与查询字符串，保留#等特殊字符作为实际路径的一部分
        """
        if not path.startswith('/'):
            path = '/' + path

        # 手动拆分查询字符串，避免 # 被解释为 fragment
        if '?' in path:
            path_part, query_part = path.split('?', 1)
        else:
            path_part, query_part = path, ''

        return path_part, query_part

    @staticmethod
    def _encode_path(path: str) -> str:
        """
        对路径的每个段进行URL编码（保留斜杠），确保 # 等字符不会被截断
        """
        segments = path.split('/')
        encoded_segments = [quote(segment, safe='') for segment in segments]
        encoded_path = '/'.join(encoded_segments)

        if not encoded_path.startswith('/'):
            encoded_path = '/' + encoded_path

        return encoded_path

    @staticmethod
    def _build_query_params(query: str) -> List[Tuple[str, str]]:
        """
        构建查询参数列表，移除已有的format参数并追加format=json
        """
        params = []
        if query:
            params.extend(parse_qsl(query, keep_blank_values=True))

        params = [
            (key, value) for key, value in params
            if key.lower() != "format"
        ]
        params.append(("format", "json"))
        return params

    def close(self):
        """关闭HTTP客户端，释放资源"""
        self.client.close()
        logger.info("DataExecutor已关闭")

    def __enter__(self):
        """上下文管理器：进入"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器：退出时自动关闭"""
        self.close()


def create_data_executor_from_config() -> DataExecutor:
    """
    从配置文件创建DataExecutor实例

    使用query_processor.config中的RSSHubSettings
    """
    try:
        from query_processor.config import rsshub_settings

        return DataExecutor(
            base_url=rsshub_settings.base_url,
            health_check_timeout=rsshub_settings.health_check_timeout,
            request_timeout=rsshub_settings.request_timeout,
            max_retries=rsshub_settings.max_retries,
        )
    except ImportError:
        logger.warning("无法导入配置，使用默认值")
        return DataExecutor()
