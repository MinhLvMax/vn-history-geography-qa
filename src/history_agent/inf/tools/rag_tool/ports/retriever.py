from src.history_agent.inf.tools.rag_tool.models.document import Document


class Retriver:
    def search(
            self,
            queries: list[str],
            number_results: int
    ) -> list[Document]:
        '''Các bộ truy vấn tùy nền tảng, thừa kế về và triển khai lớp này'''
