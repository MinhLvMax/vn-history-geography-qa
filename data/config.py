from pathlib import Path
import os
from dotenv import load_dotenv


class Config:
    DATA_PATH = Path(__file__).parent

    BOOK_DIR = DATA_PATH / 'book_dir'
    BOOK_DIR.mkdir(parents=True, exist_ok=True)

    load_dotenv()
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Load GROQ_API_KEY từ biến môi trường
