from __future__ import annotations

"""私有笔记检索工具，默认基于 docs/ 目录的 Markdown 文件。"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..runtime import NoteSearchBackend, ToolExecutionContext
from ..state import ToolCall, ToolExecutionPayload
from .registry import ToolRegistry, tool

logger = logging.getLogger(__name__)


@dataclass
class MarkdownDocument:
    path: Path
    title: str
    content: str


class MarkdownNoteStore(NoteSearchBackend):
    """
    极简 Markdown 检索器，用于演示“私有知识库”工具。
    可后续替换为向量检索实现。
    """

    def __init__(self, root: Path, encoding: str = "utf-8"):
        if not root.exists():
            raise FileNotFoundError(f"笔记目录不存在: {root}")
        self.root = root
        self.encoding = encoding
        self.documents: List[MarkdownDocument] = []
        self._load_documents()
        logger.info("MarkdownNoteStore 加载完成，共 %s 篇文档", len(self.documents))

    def _load_documents(self) -> None:
        for file_path in self.root.rglob("*.md"):
            try:
                text = file_path.read_text(encoding=self.encoding)
            except UnicodeDecodeError:
                logger.warning("无法读取文件（编码错误）: %s", file_path)
                continue
            title = text.splitlines()[0].strip("# ").strip() if text else file_path.stem
            self.documents.append(MarkdownDocument(file_path, title, text))

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        scored: List[tuple[float, MarkdownDocument]] = []
        for doc in self.documents:
            content_lower = doc.content.lower()
            score = content_lower.count(query_lower)
            if score == 0:
                continue
            snippet = self._build_snippet(doc.content, query)
            scored.append((float(score), doc, snippet))

        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, doc, snippet in scored[:top_k]:
            results.append(
                {
                    "title": doc.title,
                    "score": score,
                    "snippet": snippet,
                    "path": str(doc.path.relative_to(self.root)),
                }
            )
        return results

    @staticmethod
    def _build_snippet(content: str, query: str, radius: int = 120) -> str:
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:radius] + ("..." if len(content) > radius else "")
        start = max(0, idx - radius // 2)
        end = min(len(content), idx + radius // 2)
        snippet = content[start:end]
        return snippet.replace("\n", " ").strip()


def register_private_notes_tool(registry: ToolRegistry) -> None:
    """向注册表写入 search_private_notes 工具。"""

    @tool(
        registry,
        plugin_id="search_private_notes",
        description="在本地 Markdown 笔记中检索相关内容",
        schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    )
    def search_private_notes(
        call: ToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        backend = context.note_backend
        if backend is None:
            raise RuntimeError("未配置 NoteSearchBackend，无法执行 search_private_notes")

        query = call.args.get("query")
        if not query:
            raise ValueError("search_private_notes 需要 query 参数")
        top_k = int(call.args.get("top_k", 5))

        logger.info("搜索私有笔记: %s", query)
        results = backend.search(query=query, top_k=top_k)
        payload: Dict[str, Any] = {
            "type": "private_notes",
            "query": query,
            "results": results,
        }
        status = "success" if results else "error"
        error_message = None if results else "未在笔记中找到相关内容"
        return ToolExecutionPayload(
            call=call,
            raw_output=payload,
            status=status,
            error_message=error_message,
        )

