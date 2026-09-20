from dataclasses import dataclass
from pydantic import Field
from src.history_agent.dom.tool import ToolKwargs, ToolResult, Tool
from src.history_agent.inf.tools.rag_tool.models.document import Document
from src.history_agent.inf.tools.rag_tool.ports.retriever import Retriver
from src.history_agent.inf.tools.rag_tool.ports.reranker import Reranker

class RAGToolKwargs(ToolKwargs):
    query: str = Field(
        description=(
            "The user's original question, copied verbatim or with only minimal "
            "normalization. Use this only as the query for reranking retrieved documents. "
            "Do NOT answer the question, infer its expected answer, add facts, provide "
            "reasoning, summarize the question, or expand it with additional information."
        )
    )

    search_queries: list[str] = Field(
        description=(
            "Search queries used to retrieve relevant documents from the knowledge base. "
            "Generate concise keyword-based queries derived only from the user's question. "
            "Do NOT include answers, reasoning, assumptions, conclusions, or facts that "
            "are not explicitly present in the user's question. Each query should focus "
            "on terms likely to appear in the knowledge base."
        )
    )

@dataclass
class RAGToolResult(ToolResult):
    documents: list[Document] | None
    error: str | None
    def to_text(self) -> str:
        if self.error:
            return f"RAG search failed: {self.error}"

        if not self.documents:
            return "Không tìm thấy tài liệu liên quan."

        if not self.documents:
            return "Không tìm thấy tài liệu liên quan."

        results = []

        for index, document in enumerate(self.documents, start=1):
            metadata = document.metadata

            results.append(
                (
                    f"[SOURCE {index}]\n"
                    # f"Document ID: {document.id}\n"
                    f"Title: {metadata.get('title', 'N/A')}\n"
                    f"Author: {metadata.get('author', 'N/A')}\n"
                    f"Publication year: {metadata.get('publication_year', 'N/A')}\n"
                    # f"Volume: {metadata.get('volume', 'N/A')}\n"
                    # f"Topic: {metadata.get('topic', 'N/A')}\n"
                    f"Period: {metadata.get('period', 'N/A')}\n"
                    f"Chapter: {metadata.get('chapter_title', 'N/A')}\n"
                    f"Paragraph order: {metadata.get('paragraph_order', 'N/A')}\n"
                    f"Content:\n"
                    f"{document.text}"
                )
            )
        content = "\n\n".join(results)
        return content


class RAGTool(Tool):
    tool_name = "rag_search"
    tool_description = (
        "Search the historical knowledge base for relevant documents. "
        "Use search_queries to retrieve candidate documents and use the "
        "original query to rerank them for relevance. "
        "The returned documents contain source information that can be "
        "used to support citations in the final answer."
    )

    tool_kwargs = RAGToolKwargs

    def __init__(
            self,
            retriever: Retriver,
            reranker: Reranker,
            retrieval_top_k: int = 20,
            rerank_top_k: int = 5,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.retrieval_top_k = retrieval_top_k
        self.rerank_top_k = rerank_top_k

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            # 1. Retrieve candidate documents using search queries.
            documents = self.retriever.search(
                queries=args.search_queries,
                number_results=self.retrieval_top_k,
            )

            if not documents:
                return RAGToolResult(
                    documents=None,
                    error=None,
                )

            # 2. Rerank candidates using the original user query.
            documents = self.reranker.rerank(
                query=args.query,
                documents=documents,
                top_k=self.rerank_top_k,
            )

            # 3. Return the final ranked documents.
            return RAGToolResult(
                documents=documents,
                error=None
            )

        except Exception as e:
            return RAGToolResult(
                documents=[],
                error=str(e),
            )


if __name__ == "__main__":
    from src.history_agent.inf.tools.rag_tool.chroma_baai_retriever import ChromaBAAIRetriever
    from src.history_agent.inf.tools.rag_tool.baai_reranker import BAAIReranker
    from src.history_agent.config import Config

    retriever = ChromaBAAIRetriever(
        path=Config.VECDB,
        collection_name="history",
    )

    reranker = BAAIReranker()

    tool = RAGTool(
        retriever=retriever,
        reranker=reranker,
    )

    # 1. Có kết quả
    result = tool.execute(
        query="Hồ Chí Minh giữ những chức vụ gì?",
        search_queries=[
            "Hồ Chí Minh chức vụ",
            "Hồ Chí Minh Chủ tịch",
            "Hồ Chí Minh Ngoại giao",
        ],
    )

    print("=== RESULT ===")
    print(result.to_text())
