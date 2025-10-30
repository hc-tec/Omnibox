"""
语义描述文档生成器
从JSON路由定义生成富含语义信息的自然语言文档
"""
import copy
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticDocGenerator:
    """为每个路由生成语义描述文档"""

    def __init__(self, datasource_file: Path, output_dir: Path):
        """
        初始化生成器

        Args:
            datasource_file: datasource_definitions.json 文件路径
            output_dir: 语义文档输出目录
        """
        self.datasource_file = datasource_file
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._datasource_cache: Optional[List[Dict[str, Any]]] = None
        self._route_index: Optional[Dict[str, Dict[str, Any]]] = None

    def load_datasources(self) -> List[Dict[str, Any]]:
        """
        加载数据源定义，兼容列表或字典两种结构

        Returns:
            数据源定义列表
        """
        if self._datasource_cache is not None:
            return self._datasource_cache

        with open(self.datasource_file, 'r', encoding='utf-8') as f:
            raw_datasources = json.load(f)

        datasources: List[Dict[str, Any]] = []

        if isinstance(raw_datasources, list):
            for datasource in raw_datasources:
                if not isinstance(datasource, dict):
                    logger.warning("跳过无效的数据源定义: %r", datasource)
                    continue
                datasources.append(datasource)
        elif isinstance(raw_datasources, dict):
            for key, datasource in raw_datasources.items():
                if not isinstance(datasource, dict):
                    logger.warning("跳过无效的数据源定义: %s -> %r", key, datasource)
                    continue
                datasource_copy = datasource.copy()
                datasource_copy.setdefault("provider_id", key)
                datasource_copy.setdefault("provider_name", datasource_copy.get("name") or key)
                datasources.append(datasource_copy)
        else:
            raise ValueError("datasource_definitions.json 格式不受支持，应为对象或数组")

        self._datasource_cache = datasources
        return datasources

    def _safe_route_filename(self, route_id: str) -> str:
        """确保生成的文件名合法"""
        unsafe_chars = '\\/:*?"<>|'
        return ''.join('_' if ch in unsafe_chars else ch for ch in route_id)

    def _ensure_route_index(self) -> Dict[str, Dict[str, Any]]:
        """构建 route_id 到完整定义的索引"""
        if self._route_index is not None:
            return self._route_index

        route_index: Dict[str, Dict[str, Any]] = {}

        for datasource in self.load_datasources():
            provider_id = (
                datasource.get('provider_id')
                or datasource.get('datasource')
                or datasource.get('provider_name')
            )
            provider_name = datasource.get('provider_name') or provider_id or "未知数据源"

            routes = datasource.get('routes') or []
            if isinstance(routes, dict):
                route_items = routes.items()
            else:
                route_items = (
                    (route.get('route_id'), route)
                    for route in routes
                    if isinstance(route, dict)
                )

            for route_id, route_def in route_items:
                if isinstance(route_def, dict):
                    route_data = route_def.copy()
                else:
                    route_data = {}

                if not route_id:
                    route_id = route_data.get('route_id')

                if not route_id:
                    logger.warning(
                        "跳过缺少 route_id 的路由（数据源: %s）", provider_name
                    )
                    continue

                if route_id in route_index:
                    logger.warning("检测到重复的 route_id: %s，保留首次出现的定义", route_id)
                    continue

                route_data['route_id'] = route_id

                if provider_id:
                    route_data['datasource'] = provider_id
                    route_data.setdefault('provider_id', provider_id)

                if provider_name:
                    route_data.setdefault('datasource_name', provider_name)
                    route_data.setdefault('provider_name', provider_name)

                if 'provider_description' not in route_data:
                    route_data['provider_description'] = datasource.get('provider_description', '')
                if 'provider_categories' not in route_data:
                    route_data['provider_categories'] = datasource.get('provider_categories', [])
                if 'provider_lang' not in route_data:
                    route_data['provider_lang'] = datasource.get('provider_lang')
                if 'provider_url' not in route_data:
                    route_data['provider_url'] = datasource.get('provider_url')

                route_index[route_id] = route_data

        self._route_index = route_index
        logger.info(
            "已索引 %d 个路由，来自 %d 个数据源",
            len(route_index),
            len(self._datasource_cache or []),
        )
        return route_index

    def generate_semantic_doc(self, route_id: str, route_def: Dict[str, Any]) -> str:
        """
        为单个路由生成语义描述文档

        核心策略：
        1. 提取所有关键信息（名称、描述、参数、分类等）
        2. 转换为自然语言描述
        3. 包含丰富的语义关键词，便于向量检索

        Args:
            route_id: 路由ID
            route_def: 路由定义JSON对象

        Returns:
            语义描述文档（字符串）
        """
        doc_parts = []

        # 1. 基本信息
        doc_parts.append(f"路由标识: {route_id}")

        # 2. 数据源信息
        datasource_name = (
            route_def.get('datasource_name')
            or route_def.get('datasource')
            or '未知数据源'
        )
        doc_parts.append(f"数据源: {datasource_name}")

        datasource_id = route_def.get('datasource')
        if datasource_id and datasource_id != datasource_name:
            doc_parts.append(f"数据源标识: {datasource_id}")

        provider_description = route_def.get('provider_description')
        if provider_description:
            doc_parts.append(f"数据源描述: {provider_description}")

        # 3. 路由名称和描述
        name = route_def.get('name', '')
        if name:
            doc_parts.append(f"功能名称: {name}")

        description = route_def.get('description', '')
        if description:
            doc_parts.append(f"功能描述: {description}")

        # 4. 分类信息
        categories = route_def.get('categories', [])
        if categories:
            category_str = ', '.join(categories)
            doc_parts.append(f"分类标签: {category_str}")

        provider_categories = route_def.get('provider_categories') or []
        if provider_categories:
            provider_category_str = ', '.join(provider_categories)
            doc_parts.append(f"数据源分类: {provider_category_str}")

        provider_lang = route_def.get('provider_lang')
        if provider_lang:
            doc_parts.append(f"数据源语言: {provider_lang}")

        provider_url = route_def.get('provider_url')
        if provider_url:
            doc_parts.append(f"数据源网址: {provider_url}")

        # 5. 路径模板（提取关键路径信息）
        path_templates = route_def.get('path_template', [])
        if path_templates:
            if isinstance(path_templates, list):
                path_info = ', '.join(path_templates)
            else:
                path_info = str(path_templates)
            doc_parts.append(f"访问路径: {path_info}")

        # 6. 参数详细说明
        parameters = route_def.get('parameters', [])
        if parameters:
            doc_parts.append("\n参数说明:")
            for param in parameters:
                param_name = param.get('name', '')
                param_desc = param.get('description', '')
                param_default = param.get('default_value', '')

                param_text = f"- '{param_name}'"
                if param_desc:
                    param_text += f": {param_desc}"
                if param_default:
                    param_text += f" (默认值: {param_default})"

                # 如果有选项值，列出所有选项
                options = param.get('options', [])
                if options:
                    option_list = []
                    for opt in options:
                        if isinstance(opt, dict):
                            opt_value = opt.get('value', '')
                            opt_label = opt.get('label', '')
                            if opt_label:
                                option_list.append(f"'{opt_value}' ({opt_label})")
                            else:
                                option_list.append(f"'{opt_value}'")
                        else:
                            option_list.append(f"'{opt}'")

                    if option_list:
                        param_text += f", 可选值: {', '.join(option_list)}"

                doc_parts.append(param_text)

        # 7. 额外的元数据
        maintainers = route_def.get('maintainers', [])
        if maintainers:
            doc_parts.append(f"\n维护者: {', '.join(maintainers)}")

        # 8. 雷达规则（用于理解数据源特性）
        radar = route_def.get('radar', [])
        if radar:
            doc_parts.append(f"\n支持的获取方式: {', '.join(radar)}")

        # 9. 特性标签
        features = route_def.get('features', {})
        if features:
            feature_list = []
            if features.get('requireConfig'):
                feature_list.append("需要配置")
            if features.get('requirePuppeteer'):
                feature_list.append("需要浏览器渲染")
            if features.get('antiCrawler'):
                feature_list.append("反爬虫保护")
            if features.get('supportBT'):
                feature_list.append("支持BT下载")
            if features.get('supportPodcast'):
                feature_list.append("支持播客")
            if features.get('supportScihub'):
                feature_list.append("支持学术文献")

            if feature_list:
                doc_parts.append(f"\n特性: {', '.join(feature_list)}")

        # 10. 生成最终文档
        semantic_doc = '\n'.join(doc_parts)

        return semantic_doc

    def generate_all_docs(self) -> Dict[str, str]:
        """
        为所有路由生成语义文档

        Returns:
            {route_id: semantic_doc} 的字典
        """
        datasources = self.load_datasources()
        route_index = self._ensure_route_index()
        all_docs = {}

        logger.info(
            "开始生成语义文档，共 %d 个数据源，%d 条路由",
            len(datasources),
            len(route_index),
        )

        for route_id, route_def in route_index.items():
            semantic_doc = self.generate_semantic_doc(route_id, route_def)
            all_docs[route_id] = semantic_doc

            doc_file = self.output_dir / f"{self._safe_route_filename(route_id)}.txt"
            with open(doc_file, 'w', encoding='utf-8') as f:
                f.write(semantic_doc)

        logger.info(f"成功生成 {len(all_docs)} 个语义文档")
        return all_docs

    def get_route_definition(self, route_id: str) -> Dict[str, Any]:
        """
        获取指定路由的完整JSON定义

        Args:
            route_id: 路由ID

        Returns:
            路由完整定义
        """
        route_index = self._ensure_route_index()
        route_def = route_index.get(route_id)
        if route_def is None:
            return None
        return copy.deepcopy(route_def)


if __name__ == "__main__":
    # 测试代码
    from config import DATASOURCE_FILE, SEMANTIC_DOCS_PATH

    generator = SemanticDocGenerator(DATASOURCE_FILE, SEMANTIC_DOCS_PATH)

    # 生成所有语义文档
    all_docs = generator.generate_all_docs()

    # 打印一个示例
    if all_docs:
        sample_route_id = list(all_docs.keys())[0]
        print(f"\n示例路由: {sample_route_id}")
        print("=" * 80)
        print(all_docs[sample_route_id])
        print("=" * 80)
