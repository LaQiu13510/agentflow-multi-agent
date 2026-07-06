"""Milvus / SmartKB MCP 风格服务。"""

from pymilvus import Collection, connections, utility

from config import MILVUS_HOST, MILVUS_PORT, SMARTKB_COLLECTION, TOP_K_KNOWLEDGE
from models.embedding import get_embedding_model
from tools.mcp_base import LocalMCPServer, ToolResult, ToolSpec


class MilvusMCPServer(LocalMCPServer):
    server_name = "milvus"

    def __init__(self):
        self._connected = False
        super().__init__()

    def register_tools(self):
        self.add_tool(ToolSpec("health", "检查 Milvus 连接"), self.health)
        self.add_tool(
            ToolSpec("collection_stats", "查看 SmartKB Collection 状态"),
            self.collection_stats,
        )
        self.add_tool(
            ToolSpec(
                "search_smartkb",
                "在项目一 SmartKB 向量知识库中检索内容",
                {"query": "用户问题", "top_k": 4},
            ),
            self.search_smartkb,
        )

    def connect(self):
        if self._connected:
            return
        connections.connect(
            alias="default",
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            timeout=10,
        )
        self._connected = True

    def health(self) -> ToolResult:
        self.connect()
        return ToolResult(True, f"Milvus 连接正常: {MILVUS_HOST}:{MILVUS_PORT}")

    def collection_stats(self) -> ToolResult:
        self.connect()
        if not utility.has_collection(SMARTKB_COLLECTION):
            return ToolResult(False, f"Collection 不存在: {SMARTKB_COLLECTION}")
        collection = Collection(SMARTKB_COLLECTION)
        collection.load()
        return ToolResult(
            True,
            f"{SMARTKB_COLLECTION}: {collection.num_entities} vectors",
            {"collection": SMARTKB_COLLECTION, "vectors": collection.num_entities},
        )

    def search_smartkb(self, query: str, top_k: int = TOP_K_KNOWLEDGE) -> ToolResult:
        self.connect()
        if not utility.has_collection(SMARTKB_COLLECTION):
            return ToolResult(False, f"Collection 不存在: {SMARTKB_COLLECTION}")

        embedding_model = get_embedding_model()
        query_embedding = embedding_model.embed_query(query)
        collection = Collection(SMARTKB_COLLECTION)
        collection.load()
        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            output_fields=["content", "file_name", "chunk_index", "source_page"],
        )

        rows = []
        for hits in results:
            for hit in hits:
                rows.append(
                    {
                        "file_name": hit.entity.get("file_name", ""),
                        "content": hit.entity.get("content", ""),
                        "score": float(hit.score),
                        "chunk_index": hit.entity.get("chunk_index", 0),
                        "source_page": hit.entity.get("source_page", 0),
                    }
                )

        if not rows:
            return ToolResult(True, "未检索到相关内容", {"rows": []})

        lines = []
        for idx, row in enumerate(rows, start=1):
            content = row["content"].replace("\n", " ")[:500]
            lines.append(
                f"[{idx}] {row['file_name']} score={row['score']:.4f}\n{content}"
            )
        return ToolResult(True, "\n\n".join(lines), {"rows": rows})

