from src.history_agent.inf.tools.rag_tool.models.document import Document


class Reranker:
    def rerank(
            self,
            query: str,
            documents: list[Document],
            top_k: int
    ) -> list[Document]:
        '''Port thừa kế '''
