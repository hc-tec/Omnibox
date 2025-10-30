"""
RAG-in-Action 使用示例
演示如何使用新的分层架构
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator.rag_in_action import create_rag_in_action


def example_1_basic_usage():
    """
    示例1：基本使用
    最简单的调用方式
    """
    print("\n" + "="*80)
    print("示例1：基本使用")
    print("="*80)

    # 配置LLM（需要设置环境变量 OPENAI_API_KEY）
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  请先设置环境变量: export OPENAI_API_KEY=your_key")
        print("或者在代码中设置: os.environ['OPENAI_API_KEY'] = 'your_key'")
        return

    # 创建RAG-in-Action实例
    ria = create_rag_in_action(
        llm_provider="openai",
        llm_config={
            "model": "gpt-4",  # 或 gpt-3.5-turbo
        }
    )

    # 处理用户查询
    user_query = "帮我看看虎扑步行街今天最新发布的帖子"

    result = ria.process(
        user_query=user_query,
        verbose=True,
    )

    # 使用结果
    if result["status"] == "success":
        print(f"\n✅ 可以调用API:")
        print(f"   路径: {result['generated_path']}")
        print(f"   参数: {result['parameters_filled']}")


def example_2_custom_llm():
    """
    示例2：使用自定义LLM
    演示如何集成自己的LLM服务
    """
    print("\n" + "="*80)
    print("示例2：使用自定义LLM")
    print("="*80)

    # 自定义LLM生成函数
    def my_llm_generate(prompt: str) -> str:
        """
        这里可以调用你自己的LLM服务
        比如本地部署的大模型、其他API等
        """
        # 示例：简单返回一个JSON
        return '''
        {
          "status": "success",
          "reasoning": "这是自定义LLM的响应",
          "selected_tool": {
            "route_id": "hupu_bbs",
            "provider": "hupu",
            "name": "社区"
          },
          "generated_path": "/hupu/bbs/bxj/1",
          "parameters_filled": {
            "id": "bxj",
            "order": "1"
          },
          "clarification_question": null
        }
        '''

    from query_processor.llm_client import create_llm_client
    from rag_system.rag_pipeline import RAGPipeline
    from orchestrator.rag_in_action import RAGInAction

    # 创建自定义LLM客户端
    llm_client = create_llm_client(
        provider="custom",
        generate_func=my_llm_generate,
        name="MyLLM"
    )

    # 创建RAG管道
    rag_pipeline = RAGPipeline()

    # 创建RAG-in-Action
    ria = RAGInAction(
        rag_pipeline=rag_pipeline,
        llm_client=llm_client,
    )

    # 处理查询
    result = ria.process("虎扑步行街")

    print(f"状态: {result['status']}")
    print(f"路径: {result['generated_path']}")


def example_3_step_by_step():
    """
    示例3：分步调用
    演示如何单独使用每个模块
    """
    print("\n" + "="*80)
    print("示例3：分步调用（了解内部工作流程）")
    print("="*80)

    from rag_system.rag_pipeline import RAGPipeline
    from query_processor.prompt_builder import PromptBuilder
    from query_processor.llm_client import create_llm_client
    from query_processor.parser import QueryParser
    from query_processor.path_builder import PathBuilder

    user_query = "虎扑步行街最新帖子"

    # 步骤1: RAG检索
    print("\n[步骤1] RAG向量检索")
    rag_pipeline = RAGPipeline()
    rag_results = rag_pipeline.search(user_query, top_k=3, verbose=False)
    retrieved_tools = [route_def for _, _, route_def in rag_results]
    print(f"✓ 检索到 {len(retrieved_tools)} 个工具")

    # 步骤2: 构建Prompt
    print("\n[步骤2] 构建Prompt")
    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build(user_query, retrieved_tools)
    print(f"✓ Prompt长度: {len(prompt)} 字符")

    # 步骤3: LLM解析（这里用模拟数据代替）
    print("\n[步骤3] LLM解析")
    print("（需要配置LLM才能实际调用）")

    # 步骤4: 路径构建
    print("\n[步骤4] 路径构建")
    path_builder = PathBuilder()

    # 模拟LLM返回的参数
    simulated_params = {"id": "bxj", "order": "1"}

    if retrieved_tools:
        path = path_builder.build(
            route_def=retrieved_tools[0],
            parameters=simulated_params
        )
        print(f"✓ 生成路径: {path}")


def example_4_error_handling():
    """
    示例4：错误处理
    演示各种状态的处理
    """
    print("\n" + "="*80)
    print("示例4：错误处理")
    print("="*80)

    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  需要设置OPENAI_API_KEY")
        return

    ria = create_rag_in_action(
        llm_provider="openai",
        llm_config={"model": "gpt-3.5-turbo"}
    )

    # 测试不同的查询
    test_queries = [
        "虎扑步行街",  # 应该成功
        "给我看看帖子",  # 可能需要澄清
        "今天天气怎么样",  # 可能找不到
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        print("-" * 40)

        result = ria.process(query, verbose=False)

        if result["status"] == "success":
            print(f"✅ 成功: {result['generated_path']}")

        elif result["status"] == "needs_clarification":
            print(f"❓ 需要澄清: {result.get('clarification_question')}")

        elif result["status"] == "not_found":
            print(f"❌ 未找到匹配功能")

        elif result["status"] == "error":
            print(f"❌ 错误: {result.get('reasoning')}")


def main():
    """运行所有示例"""
    print("\n")
    print("="*80)
    print("RAG-in-Action 使用示例")
    print("="*80)

    # 检查环境
    print("\n环境检查:")
    print(f"  OPENAI_API_KEY: {'已设置' if os.getenv('OPENAI_API_KEY') else '未设置'}")

    # 运行示例
    # example_1_basic_usage()  # 需要OPENAI_API_KEY
    # example_2_custom_llm()
    example_3_step_by_step()  # 不需要LLM
    # example_4_error_handling()  # 需要OPENAI_API_KEY

    print("\n提示:")
    print("  - example_1: 基本使用（需要OPENAI_API_KEY）")
    print("  - example_2: 自定义LLM")
    print("  - example_3: 分步调用（无需API Key）")
    print("  - example_4: 错误处理")


if __name__ == "__main__":
    main()
