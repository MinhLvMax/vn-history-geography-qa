import chromadb
from src.history_agent.config import Config


class ChromaVectorDB:
    def __init__(self, path=None):
        self.path = path or Config.VECDB
        self.client = chromadb.PersistentClient(self.path)
        self.history_collection = self.client.get_collection('lich_su_chung')
        pass

    def keyword_queries(self, queries):
        return

    def vector_query(self, queries, n_results: int = 3):
        data = self.history_collection.query(
            query_texts=queries,
            n_results=n_results,
        )

        results = []

        for query, ids, documents, metadatas, distances in zip(
                queries,
                data["ids"],
                data["documents"],
                data["metadatas"],
                data['distances'],
        ):
            results.append({
                "query": query,
                "results": [
                    {
                        "id": id,
                        "document": doc,
                        "metadata": meta,
                        "distance": distance
                    }
                    for id, doc, meta, distance in zip(ids, documents, metadatas, distances)
                ],
            })

        return results

    def print_list_collections(self):
        collections = self.client.list_collections()
        return collections


if __name__ == '__main__':
    from pprint import pprint

    chroma_vectordb = ChromaVectorDB()
    print(chroma_vectordb.print_list_collections())

    print(chroma_vectordb.history_collection.configuration)

    queries = [
        "Hồ Gươm có liên quan đến những sự kiện lịch sử nào?",
        "Những dấu mốc lịch sử nào gắn liền với Hồ Hoàn Kiếm?",
    ]
    # pprint(chroma_vectordb.vector_query(queries))
