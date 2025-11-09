"""
Panel adapters 测试的共享配置和 fixtures
"""

import importlib

import pytest

import services.panel.adapters as adapters
import services.panel.adapters.registry as adapter_registry_module
import services.panel.adapters.hupu as adapters_hupu_module
import services.panel.adapters.bilibili as adapters_bilibili_module
import services.panel.adapters.bilibili.feed as adapters_bilibili_feed_module
import services.panel.adapters.bilibili.followings as adapters_bilibili_followings_module
import services.panel.adapters.bilibili.hot_search as adapters_bilibili_hot_search_module
import services.panel.adapters.bilibili.user_video as adapters_bilibili_user_video_module
import services.panel.adapters.github as adapters_github_module
import services.panel.adapters.generic as adapters_generic_module
import services.panel.data_block_builder as data_block_builder
import services.panel.panel_generator as panel_generator


@pytest.fixture(autouse=True)
def reload_panel_modules():
    """
    在每个测试之前重新加载所有 panel 模块

    这确保装饰器被重新执行，适配器被正确注册到注册表中
    """
    for module in [
        adapter_registry_module,
        adapters_hupu_module,
        adapters_bilibili_module,
        adapters_bilibili_feed_module,
        adapters_bilibili_followings_module,
        adapters_bilibili_hot_search_module,
        adapters_bilibili_user_video_module,
        adapters_github_module,
        adapters_generic_module,
    ]:
        importlib.reload(module)
    importlib.reload(adapters)
    importlib.reload(data_block_builder)
    importlib.reload(panel_generator)
    yield
