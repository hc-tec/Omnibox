"""
数据执行器 - RSS数据获取与解析
职责：
1. 调用RSSHub API（本地优先，支持降级）
2. 健康检查
3. 数据标准化
4. 错误处理和重试
"""

from dataclasses import dataclass
from typing import List, Optional, Literal, Dict, Any, Tuple
import httpx
import logging
from datetime import datetime
from urllib.parse import quote, parse_qsl, urlencode

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    """
    RSS Feed数据项通用模型（万物皆可RSS）

    适用于各种数据类型：
    - 视频（B站、YouTube）
    - 社交动态（微博、推特）
    - 论坛帖子（虎扑、V2EX）
    - 商品、天气、股票、GitHub仓库等
    """
    title: str                      # 标题（必需）
    link: str                       # 链接（必需）
    description: str                # 描述/摘要（必需）
    pub_date: Optional[str] = None  # 发布时间
    author: Optional[str] = None    # 作者/发布者
    guid: Optional[str] = None      # 唯一标识

    # 通用扩展字段
    category: Optional[List[str]] = None     # 分类/标签
    media_url: Optional[str] = None          # 媒体URL（图片/视频/音频）
    media_type: Optional[str] = None         # 媒体类型（image/video/audio）

    # 原始数据（保留RSSHub返回的所有字段）
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_rsshub_item(cls, item: Dict[str, Any]) -> "FeedItem":
        """
        从RSSHub JSON格式创建FeedItem实例

        自动提取常见字段，并保留原始数据供后续使用
        """
        # 提取媒体信息（如果有）
        media_url = None
        media_type = None

        # 尝试从enclosure提取媒体信息
        enclosure = item.get("enclosure", {})
        if isinstance(enclosure, dict):
            media_url = enclosure.get("url")
            media_type = enclosure.get("type", "").split("/")[0]  # image/jpeg -> image

        # 提取分类
        category = item.get("category")
        if isinstance(category, str):
            category = [category]
        elif not isinstance(category, list):
            category = None

        return cls(
            title=item.get("title", ""),
            link=item.get("link", ""),
            description=item.get("description", ""),
            pub_date=item.get("pubDate"),
            author=item.get("author"),
            guid=item.get("guid"),
            category=category,
            media_url=media_url,
            media_type=media_type,
            raw_data=item,  # 保留原始数据
        )


@dataclass
class FetchResult:
    """
    数据获取结果

    包含从RSSHub获取的所有数据项和元信息
    """
    status: Literal["success", "error"]
    items: List[FeedItem]                    # 数据项列表（原articles）
    source: Literal["local", "fallback"]     # 数据来源
    feed_title: Optional[str] = None         # Feed标题
    feed_link: Optional[str] = None          # Feed链接
    feed_description: Optional[str] = None   # Feed描述
    error_message: Optional[str] = None
    fetched_at: Optional[str] = None

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = datetime.now().isoformat()


class DataExecutor:
    """
    RSS数据执行器（同步版本）

    职责：
    - 调用RSSHub获取RSS数据（JSON格式）
    - 健康检查
    - 本地优先+降级机制
    - 数据标准化

    使用示例：
        executor = DataExecutor()
        result = executor.fetch_rss("/bilibili/user/video/2267573")
        if result.status == "success":
            for item in result.items:
                print(f"{item.title} - {item.media_type}")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1200",
        fallback_url: str = "https://rsshub.app",
        health_check_timeout: int = 3,
        request_timeout: int = 30,
        max_retries: int = 2,
    ):
        """
        初始化数据执行器

        Args:
            base_url: 本地RSSHub地址
            fallback_url: 降级RSSHub地址
            health_check_timeout: 健康检查超时（秒）
            request_timeout: 请求超时（秒）
            max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.fallback_url = fallback_url.rstrip('/')
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

        logger.info(
            f"DataExecutor初始化: 本地={self.base_url}, "
            f"降级={self.fallback_url}"
        )

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
        1. 优先尝试本地RSSHub
        2. 失败则降级到公共RSSHub
        3. 两者都失败则返回错误

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
            logger.info(f"✓ 本地获取成功: {len(result.items)}条数据")
            return result

        # 2. 降级到公共服务
        logger.warning(
            f"本地获取失败，降级到公共RSSHub: {self.fallback_url}"
        )
        result = self._try_fetch(self.fallback_url, path, "fallback")

        if result.status == "success":
            logger.info(f"✓ 降级获取成功: {len(result.items)}条数据")
        else:
            logger.error(f"✗ 所有来源均失败: {result.error_message}")

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

                # 解析JSON
                data = response.json()

                # 提取feed信息
                feed_title = data.get("title", "")
                feed_link = data.get("link", "")
                feed_description = data.get("description", "")

                # 提取数据项列表
                raw_items = data.get("item", [])
                if not raw_items:
                    logger.warning(f"RSS数据为空: {url}")

                # 转换为FeedItem对象列表
                feed_items = [
                    FeedItem.from_rsshub_item(item)
                    for item in raw_items
                ]

                logger.info(
                    f"✓ 成功获取 {len(feed_items)} 条数据 ({source}): {feed_title}"
                )

                return FetchResult(
                    status="success",
                    items=feed_items,
                    source=source,
                    feed_title=feed_title,
                    feed_link=feed_link,
                    feed_description=feed_description,
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
            fallback_url=rsshub_settings.fallback_url,
            health_check_timeout=rsshub_settings.health_check_timeout,
            request_timeout=rsshub_settings.request_timeout,
            max_retries=rsshub_settings.max_retries,
        )
    except ImportError:
        logger.warning("无法导入配置，使用默认值")
        return DataExecutor()
