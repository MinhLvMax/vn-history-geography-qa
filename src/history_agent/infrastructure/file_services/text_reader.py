
class TextReader():
    def read(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            noi_dung = f.read()
            return noi_dung