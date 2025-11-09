"""
测试 Panel 的 append 模式是否正确工作
"""

import services.panel.panel_generator as panel_generator_module
from api.schemas.panel import SourceInfo


def test_panel_append_mode_generates_unique_node_ids():
    """测试 append 模式下，多次生成的 layout node id 不会重复"""
    generator = panel_generator_module.PanelGenerator()

    source_info_1 = SourceInfo(
        datasource="test",
        route="/test/route1",
        params={},
        fetched_at=None,
        request_id=None,
    )

    source_info_2 = SourceInfo(
        datasource="test",
        route="/test/route2",
        params={},
        fetched_at=None,
        request_id=None,
    )

    # 第一次生成
    block_input_1 = panel_generator_module.PanelBlockInput(
        block_id="block-1",
        records=[{"title": "Item 1", "link": "http://example.com/1"}],
        source_info=source_info_1,
        title="第一批数据",
    )

    result_1 = generator.generate(mode="append", block_inputs=[block_input_1])

    # 第二次生成
    block_input_2 = panel_generator_module.PanelBlockInput(
        block_id="block-2",
        records=[{"title": "Item 2", "link": "http://example.com/2"}],
        source_info=source_info_2,
        title="第二批数据",
    )

    result_2 = generator.generate(mode="append", block_inputs=[block_input_2])

    # 验证两次生成的 node id 不同
    node_ids_1 = {node.id for node in result_1.payload.layout.nodes}
    node_ids_2 = {node.id for node in result_2.payload.layout.nodes}

    # 确保没有重复的 node id
    assert len(node_ids_1.intersection(node_ids_2)) == 0, (
        f"第一次和第二次生成的 node id 有重复: "
        f"第一次={node_ids_1}, 第二次={node_ids_2}, 重复={node_ids_1.intersection(node_ids_2)}"
    )

    # 验证 node id 格式 (row-{batch_id}-{index})
    for node_id in node_ids_1:
        assert node_id.startswith("row-"), f"node id 应该以 row- 开头: {node_id}"
        parts = node_id.split("-")
        assert len(parts) == 3, f"node id 格式应该是 row-batch_id-index: {node_id}"
        # batch_id 是 8 位十六进制字符
        assert len(parts[1]) == 8, f"node id 的 batch_id 部分应该是 8 位: {node_id}"
        # 验证是否为十六进制
        try:
            int(parts[1], 16)
        except ValueError:
            assert False, f"node id 的 batch_id 部分应该是十六进制: {node_id}"
        # index 是数字
        assert parts[2].isdigit(), f"node id 的 index 部分应该是数字: {node_id}"


def test_panel_append_mode_accumulates_blocks():
    """测试 append 模式下，前端应该能够累积多次请求的 blocks"""
    # 这个测试验证概念：
    # 1. 后端第一次返回 mode=append，1个 block，layout 有 1 个 node (row-{ts1}-1)
    # 2. 后端第二次返回 mode=append，1个 block，layout 有 1 个 node (row-{ts2}-1)
    # 3. 前端合并后应该有 2 个 blocks，2 个 layout nodes

    generator = panel_generator_module.PanelGenerator()

    # 模拟第一次请求
    result_1 = generator.generate(
        mode="append",
        block_inputs=[
            panel_generator_module.PanelBlockInput(
                block_id="data-1",
                records=[{"title": "bilibili 热搜", "link": "http://example.com"}],
                source_info=SourceInfo(
                    datasource="rsshub", route="/bilibili/hot-search", params={}, fetched_at=None, request_id=None
                ),
            )
        ],
    )

    assert len(result_1.payload.blocks) == 1
    assert len(result_1.payload.layout.nodes) == 1
    node_1_id = result_1.payload.layout.nodes[0].id

    # 模拟第二次请求（时间稍后一点，确保时间戳不同）
    import time

    time.sleep(0.01)  # 等待 10ms，确保时间戳不同

    result_2 = generator.generate(
        mode="append",
        block_inputs=[
            panel_generator_module.PanelBlockInput(
                block_id="data-2",
                records=[{"title": "UP主视频", "link": "http://example.com/video"}],
                source_info=SourceInfo(
                    datasource="rsshub", route="/bilibili/user/video", params={}, fetched_at=None, request_id=None
                ),
            )
        ],
    )

    assert len(result_2.payload.blocks) == 1
    assert len(result_2.payload.layout.nodes) == 1
    node_2_id = result_2.payload.layout.nodes[0].id

    # 验证两次生成的 node id 不同
    assert node_1_id != node_2_id, f"两次生成的 node id 应该不同: {node_1_id} vs {node_2_id}"

    # 前端应该能够合并这两次结果：
    # - blocks 数组：[...result_1.blocks, ...result_2.blocks] = 2 个
    # - layout.nodes 数组：[...result_1.nodes, ...result_2.nodes] = 2 个（因为 node id 不重复）
    simulated_frontend_blocks = result_1.payload.blocks + result_2.payload.blocks
    simulated_frontend_nodes = result_1.payload.layout.nodes + result_2.payload.layout.nodes

    assert len(simulated_frontend_blocks) == 2
    assert len(simulated_frontend_nodes) == 2
