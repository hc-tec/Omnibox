"""同步订阅向量化脚本

用途：将数据库中所有订阅记录重新向量化到 ChromaDB

使用场景：
1. 首次启用向量搜索
2. 向量库损坏或丢失
3. 订阅添加时向量化失败

运行方式：
    python -m scripts.sync_subscription_embeddings
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.database.subscription_service import SubscriptionService

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_embeddings():
    """同步所有订阅的向量化"""
    logger.info("开始同步订阅向量...")

    # 初始化服务
    service = SubscriptionService()

    # 检查向量存储
    if not service.vector_store:
        logger.error("❌ 向量存储加载失败，无法同步")
        return False

    # 获取所有订阅
    subscriptions = service.list_subscriptions(limit=1000)
    logger.info(f"找到 {len(subscriptions)} 个订阅记录")

    if not subscriptions:
        logger.warning("数据库中没有订阅记录")
        return True

    # 批量向量化
    subscription_data_list = []
    for sub in subscriptions:
        subscription_data = {
            "display_name": sub.display_name,
            "platform": sub.platform,
            "entity_type": sub.entity_type,
            "description": sub.description,
            "aliases": sub.aliases,  # JSON 字符串
            "tags": sub.tags  # JSON 字符串
        }
        subscription_data_list.append((sub.id, subscription_data))
        logger.info(f"  - {sub.id}: {sub.display_name} ({sub.platform}/{sub.entity_type})")

    # 批量添加
    try:
        service.vector_store.batch_add_subscriptions(subscription_data_list)
        logger.info(f"✅ 成功同步 {len(subscriptions)} 个订阅的向量")

        # 验证
        vector_count = service.vector_store.count()
        logger.info(f"向量库当前数量: {vector_count}")

        return True

    except Exception as e:
        logger.error(f"❌ 向量化失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = sync_embeddings()
    sys.exit(0 if success else 1)
