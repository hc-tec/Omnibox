"""测试 Prompt 加载器"""
import pytest
from pathlib import Path
from langgraph_agents.prompt_loader import load_prompt, PROMPT_DIR


class TestPromptLoader:
    """测试 prompt_loader 模块"""

    def test_load_existing_prompt(self):
        """测试加载已存在的 prompt"""
        # router_system.txt 应该存在
        content = load_prompt("router_system.txt")
        assert isinstance(content, str)
        assert len(content) > 0
        assert "RouterAgent" in content

    def test_load_planner_prompt(self):
        """测试加载 planner prompt"""
        content = load_prompt("planner_system.txt")
        assert "PlannerAgent" in content
        assert "可用工具列表" in content  # 修复后应该包含这段

    def test_load_nonexistent_prompt_raises_error(self):
        """测试加载不存在的 prompt 抛出异常"""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt.txt")

    def test_prompt_dir_exists(self):
        """测试 prompt 目录存在"""
        assert PROMPT_DIR.exists()
        assert PROMPT_DIR.is_dir()

    def test_all_required_prompts_exist(self):
        """测试所有必需的 prompt 文件都存在"""
        required_prompts = [
            "router_system.txt",
            "planner_system.txt",
            "reflector_system.txt",
            "synthesizer_system.txt",
            "summarizer_system.txt",
        ]
        for prompt_name in required_prompts:
            prompt_path = PROMPT_DIR / prompt_name
            assert prompt_path.exists(), f"{prompt_name} 不存在"

    def test_caching(self):
        """测试 lru_cache 工作正常"""
        # 多次加载同一个文件，应该使用缓存
        content1 = load_prompt("router_system.txt")
        content2 = load_prompt("router_system.txt")
        assert content1 is content2  # 应该是同一个对象（缓存）
