"""
测试 bilibili 关注列表适配器
"""

import services.panel.adapters as adapters
from api.schemas.panel import SourceInfo


BILIBILI_FOLLOWINGS_SAMPLE = {
    "title": "Alice 的 bilibili 关注",
    "count": 42,
    "item": [
        {
            "title": "Alice 新关注 Bob",
            "description": "Bob<br>硬核程序员<br>总计42",
            "pubDate": "Fri, 01 Nov 2024 08:00:00 GMT",
            "link": "https://space.bilibili.com/1001",
        },
        {
            "title": "Alice 新关注 Carol",
            "description": "Carol<br>签名很长<br>总计42",
            "pubDate": "Fri, 01 Nov 2024 07:30:00 GMT",
            "link": "https://space.bilibili.com/1002",
        },
    ],
}


def test_bilibili_followings_adapter_extracts_count():
    """测试 bilibili 关注列表适配器能够提取关注数"""
    adapter = adapters.get_route_adapter("/bilibili/user/followings/2267573/3")
    source_info = SourceInfo(
        datasource="rsshub",
        route="/bilibili/user/followings/2267573/3",
        params={},
        fetched_at=None,
        request_id=None,
    )

    result = adapter(source_info, [BILIBILI_FOLLOWINGS_SAMPLE])

    # 验证记录
    assert result.records
    first = result.records[0]
    assert first["title"].startswith("Alice 新关注")
    assert first["link"] == "https://space.bilibili.com/1001"
    assert "总计42" in first["summary"]

    # 验证组件计划
    assert result.block_plans[0].component_id == "ListPanel"

    # 验证统计信息
    assert result.stats["metrics"]["follower_count"] == 42  # follower_count 现在在 metrics 中
    assert result.stats["api_endpoint"] == "/bilibili/user/followings/2267573/3"
