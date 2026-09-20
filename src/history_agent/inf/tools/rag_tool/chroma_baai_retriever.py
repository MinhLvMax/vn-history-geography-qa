import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction,
)
from src.history_agent.inf.tools.rag_tool.ports.retriever import Retriver
from src.history_agent.inf.tools.rag_tool.models.document import Document


class ChromaBAAIRetriever(Retriver):
    def __init__(
            self,
            path: str,
            collection_name: str,
    ):
        self.client = chromadb.PersistentClient(
            path=path
        )
        self.embedding_function = SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-m3",
            device="cpu",
            normalize_embeddings=False,
        )
        self.collection = self.client.get_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
        )

    def search(
            self,
            queries: list[str],
            number_results=7
    ) -> list[Document]:

        results = self.collection.query(
            query_texts=queries,
            n_results=number_results,
        )

        ids = results["ids"]
        texts = results["documents"]
        metadatas = results["metadatas"]

        documents: list[Document] = []
        seen_ids: set[str] = set()

        for query_ids, query_texts, query_metadatas in zip(
                ids,
                texts,
                metadatas,
        ):
            for id_, text, metadata in zip(
                    query_ids,
                    query_texts,
                    query_metadatas,
            ):
                if id_ in seen_ids:
                    continue

                seen_ids.add(id_)

                documents.append(
                    Document(
                        id=id_,
                        text=text,
                        metadata=metadata,
                    )
                )
        return documents


if __name__ == '__main__':
    from src.history_agent.config import Config
    from pprint import pprint

    '''Test logic tìm kiếm'''
    cr = ChromaBAAIRetriever(
        path=Config.VECDB,
        collection_name='history',
    )
    result = cr.search(['Hồ Chí Minh'])
    pprint(result)

    # '''Xem các bảng của csdl'''
    # import sqlite3
    #
    # conn = sqlite3.connect(f"{Config.VECDB}/chroma.sqlite3")
    #
    # cursor = conn.execute("""
    #                       SELECT name
    #                       FROM sqlite_master
    #                       WHERE type = 'table'
    #                       """)
    #
    # for row in cursor:
    #     print(row[0])

    # '''Xem metadata của Collection'''
    # import sqlite3
    #
    # conn = sqlite3.connect(f"{Config.VECDB}/chroma.sqlite3")
    #
    # print("=== COLLECTIONS ===")
    #
    # for row in conn.execute("SELECT * FROM collections"):
    #     print(row)
    #
    # print("\n=== COLLECTION METADATA ===")
    #
    # for row in conn.execute("SELECT * FROM collection_metadata"):
    #     print(row)
