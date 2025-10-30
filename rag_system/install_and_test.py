"""
安装依赖并测试系统
"""
import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        logger.error("Python版本过低，需要Python 3.8+")
        logger.error(f"当前版本: {sys.version}")
        return False
    logger.info(f"✓ Python版本: {sys.version.split()[0]}")
    return True


def install_dependencies():
    """安装依赖"""
    logger.info("\n开始安装依赖...")
    logger.info("="*80)

    try:
        # 升级pip
        logger.info("1. 升级pip...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            check=True
        )

        # 安装核心依赖
        logger.info("\n2. 安装核心依赖...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install",
             "sentence-transformers", "chromadb", "numpy", "pandas", "tqdm", "modelscope"],
            check=True
        )

        logger.info("\n✓ 依赖安装完成")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"✗ 安装失败: {e}")
        return False


def test_imports():
    """测试导入"""
    logger.info("\n测试模块导入...")
    logger.info("="*80)

    modules = [
        ("torch", "PyTorch"),
        ("sentence_transformers", "Sentence Transformers"),
        ("chromadb", "ChromaDB"),
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("tqdm", "tqdm"),
        ("modelscope", "ModelScope（国内镜像加速）"),
    ]

    all_ok = True
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            logger.info(f"✓ {display_name}")
        except ImportError as e:
            logger.error(f"✗ {display_name}: {e}")
            all_ok = False

    return all_ok


def test_gpu():
    """测试GPU可用性"""
    logger.info("\n检查GPU...")
    logger.info("="*80)

    try:
        import torch
        if torch.cuda.is_available():
            logger.info(f"✓ CUDA可用")
            logger.info(f"  GPU设备: {torch.cuda.get_device_name(0)}")
            logger.info(f"  显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            logger.warning("✗ CUDA不可用，将使用CPU模式")
            logger.warning("  提示：如需GPU加速，请安装CUDA版本的PyTorch")
    except Exception as e:
        logger.error(f"检查GPU失败: {e}")


def test_system():
    """测试系统功能"""
    logger.info("\n测试系统功能...")
    logger.info("="*80)

    try:
        # 测试配置加载
        logger.info("1. 测试配置...")
        import config
        logger.info("✓ 配置加载成功")

        # 测试语义文档生成器
        logger.info("\n2. 测试语义文档生成器...")
        from semantic_doc_generator import SemanticDocGenerator
        logger.info("✓ 语义文档生成器加载成功")

        # 测试向量模型
        logger.info("\n3. 测试向量模型...")
        from embedding_model import EmbeddingModel
        logger.info("✓ 向量模型加载成功")

        # 测试向量数据库
        logger.info("\n4. 测试向量数据库...")
        from vector_store import VectorStore
        logger.info("✓ 向量数据库加载成功")

        # 测试RAG管道
        logger.info("\n5. 测试RAG管道...")
        from rag_pipeline import RAGPipeline
        logger.info("✓ RAG管道加载成功")

        logger.info("\n✓ 所有模块测试通过")
        return True

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return False


def main():
    """主函数"""
    logger.info("\n" + "="*80)
    logger.info("RAG系统安装和测试")
    logger.info("="*80)

    # 检查Python版本
    if not check_python_version():
        sys.exit(1)

    # 询问是否安装依赖
    logger.info("\n是否安装依赖？")
    logger.info("注意：这会安装PyTorch等大型依赖包（~2GB）")
    user_input = input("继续安装？[Y/n]: ").strip().lower()

    if user_input in ['', 'y', 'yes']:
        if not install_dependencies():
            logger.error("\n安装失败，请检查错误信息")
            sys.exit(1)
    else:
        logger.info("跳过安装步骤")

    # 测试导入
    if not test_imports():
        logger.error("\n模块导入测试失败")
        logger.error("请先安装依赖：pip install -r requirements.txt")
        sys.exit(1)

    # 测试GPU
    test_gpu()

    # 测试系统功能
    if not test_system():
        logger.error("\n系统功能测试失败")
        sys.exit(1)

    # 成功
    logger.info("\n" + "="*80)
    logger.info("✓ 系统安装和测试完成！")
    logger.info("="*80)
    logger.info("\n下一步：")
    logger.info("1. 构建向量索引: python rag_pipeline.py --build")
    logger.info("2. 快速开始: python quick_start.py")
    logger.info("3. 查看示例: python example_usage.py")
    logger.info("4. 交互式查询: python rag_pipeline.py --interactive")


if __name__ == "__main__":
    main()
