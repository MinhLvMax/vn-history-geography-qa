from pathlib import Path
import re
from helper import *


# ========== Business logic

class BookStructurer:
    def __init__(self, book_path: str):
        self.book_path = book_path
        self.data_to_save: list[dict] = []

    @property
    def _book_content(self):
        return read_text_file(self.book_path)

    def _find_chapters(self):
        chapter_partern = (
            r"^#?\s*(?:\*\*)?"
            r"(?:"
            r"lời\s*nói\s*đầu"
            r"|(?:chương|chuong|chng|chươg|chươngg)"
            r"\s+(?:\d+|[IVXLCDM]+)\b"
            r")"
            r".*"
        )

        chapter_matches = list(re.finditer(
            pattern=chapter_partern,
            string=self._book_content,
            flags=re.MULTILINE | re.IGNORECASE
        ))

        print("Book:", self.book_path)
        print("Content length:", len(self._book_content))
        print("Chapters found:", len(chapter_matches))

        return chapter_matches

    def split_to_paragraph(self, chapter_content):
        return [
            paragraph.strip()
            for paragraph in chapter_content.splitlines()
            if paragraph.strip()
        ]

    def split_to_sentence(self, paragraph_content, sentence_order):
        sentences = re.split(r'(?<=[.!?])\s+', paragraph_content)

        result = [
            {
                'sentence_id': generate_id(),
                'sentence': sentence,
                'sentence_order': order,
                'sentence_length': len(sentence)
            }
            for order, sentence in enumerate(sentences, start=sentence_order)
        ]

        next_sentence_order = sentence_order + len(sentences)

        return result, next_sentence_order

    def parse_book_metadata(self) -> dict:
        filename = Path(self.book_path).stem

        pattern = (
            r"^(?P<title>.+?)"
            r"-(?P<author>[^-]+)"
            r"-(?P<publication_year>\d{4})$"
        )

        match = re.match(pattern, filename)

        if not match:
            raise ValueError(f"Invalid filename format: {filename}")

        title = match.group("title")

        volume_match = re.search(
            r"tập\s+(\d+)",
            title,
            re.IGNORECASE
        )

        period_match = re.search(
            r"\btừ\s+(.+)$",
            title,
            re.IGNORECASE
        )

        volume = int(volume_match.group(1)) if volume_match else None
        period = period_match.group(1).strip() if period_match else None

        return {
            "topic": "Lịch sử Việt Nam",
            "volume": volume,
            "period": period,
            "title": title,
            "author": match.group("author").strip(),
            "publication_year": int(match.group("publication_year")),
        }

    def structure(self):
        chapter_matches = self._find_chapters()
        book_metadata = self.parse_book_metadata()

        for chapter_order, match in enumerate(chapter_matches):
            # Lấy chỉ số đầu chương
            chapter_start = match.start()
            # Lấy chỉ số cuối chương
            chapter_end = chapter_matches[chapter_order + 1].start() if chapter_order + 1 < len(
                chapter_matches) else len(
                self._book_content)

            # Cắt lấy nội dung chương
            chapter_content = self._book_content[chapter_start:chapter_end]
            # Cắt chương thành các đoạn
            paragraphs = self.split_to_paragraph(chapter_content)
            chapter_id = generate_id()
            chapter_length = len(chapter_content)
            sentence_order = 0
            for paragraph_order, paragraph in enumerate(paragraphs):
                if len(paragraph) <= 4:
                    continue
                sentences, new_sentence_order = self.split_to_sentence(paragraph, sentence_order)
                sentence_order = new_sentence_order
                data = {
                    **book_metadata,
                    'chapter_id': chapter_id,
                    "chapter_order": chapter_order,
                    'chapter_title': match.group().strip(),
                    'chapter_start': chapter_start,
                    'chapter_end': chapter_end,
                    'chapter_length': chapter_length,
                    'paragraph_id': generate_id(),
                    "paragraph_order": paragraph_order,
                    'paragraph_length': len(paragraph),
                    'paragraph_content': paragraph,
                    # Nên thêm 2 key là danh sách câu và danh từ nữa
                    'sentences': sentences
                }
                self.data_to_save.append(data)

    def save(self, output_dir: Path):
        output_path = output_dir / f"{Path(self.book_path).stem}.json"
        save_json(self.data_to_save, str(output_path))


def structure_books(book_dir: Path) -> list[dict]:
    all_books = []

    for book_path in get_file_paths(book_dir):
        book = BookStructurer(book_path)
        book.structure()
        all_books.extend(book.data_to_save)

    return all_books


if __name__ == '__main__':
    input_config = read_json_file(file_path='config.json')
    BOOK_DIR = input_config['books']
    HISTORY_STRUCTURE_DATA = Path(input_config['structured'])

    all_books = structure_books(Path(BOOK_DIR))
    save_json(all_books, str(HISTORY_STRUCTURE_DATA))
    pass
