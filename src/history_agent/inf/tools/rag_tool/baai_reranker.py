from sentence_transformers import CrossEncoder
from src.history_agent.inf.tools.rag_tool.models.document import Document
from src.history_agent.inf.tools.rag_tool.ports.reranker import Reranker

class BAAIReranker(Reranker):
    def __init__(
            self,
            model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
            # model_name: str = "BAAI/bge-reranker-v2-m3"
            # model_name: str = 'Alibaba-NLP/gte-multilingual-reranker-base'
    ):
        self._model = CrossEncoder(
            model_name,
            # local_files_only=True
            trust_remote_code=True,
        )

    def rerank(
            self,
            query: str,
            documents: list[Document],
            top_k: int = 5,
    ) -> list[Document]:

        if not documents:
            return []

        pairs = [
            (query, document.text)
            for document in documents
        ]
        scores = self._model.predict(pairs)
        ranked_documents = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        result = []

        for document, score in ranked_documents[:top_k]:
            document.metadata["rerank_score"] = float(score)
            result.append(document)

        return result


if __name__ == '__main__':
    from pprint import pprint
    from src.history_agent.config import Config
    from src.history_agent.inf.tools.rag_tool.chroma_baai_retriever import ChromaBAAIRetriever

    query = 'Hồ Chí Minh'

    cbr = ChromaBAAIRetriever(
        path=Config.VECDB,
        collection_name='history',
    )

    print("=== MODEL LOADED ===")

    br = BAAIReranker()

    print("=== RERANKER READY ===")

    docs = cbr.search([query])

    print("=== CHROMA READY ===")

    rerank_docs = br.rerank(
        query=query,
        documents=docs
    )

    print("=== RERANK DONE ===")

    pprint(rerank_docs)
