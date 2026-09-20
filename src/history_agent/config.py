import os
import logging
from dotenv import load_dotenv
from pathlib import Path


def get_logger(name: str, path, enable_console=True) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(pathname)s:%(funcName)s:%(lineno)d\n"
        "   %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if enable_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    file = logging.handlers.RotatingFileHandler(
        path,
        maxBytes=1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file.setFormatter(formatter)

    logger.addHandler(file)

    return logger


class Config:
    PROJECT_PATH = Path(__file__).resolve().parents[2]  # Đường dẫn folder chính của dự án
    LOGFILES = PROJECT_PATH / "logfiles"  # Đường dẫn đến folder chứa các file log
    LOGFILES.mkdir(exist_ok=True)
    logger = get_logger(
        'app_logger',
        path=LOGFILES / 'app.log'
    )

    DATA = PROJECT_PATH / "data"  # Đường dẫn đến folder chứa data
    DATA.mkdir(exist_ok=True)

    # DOWNLOADS = PROJECT_PATH / "downloads"  # Đường dẫn đến folder chứa các file log
    # DOWNLOADS.mkdir(exist_ok=True)

    ENV_PATH = Path(PROJECT_PATH) / ".env"
    if not ENV_PATH.exists():
        ENV_PATH.write_text("GROQ_API_KEY=")
        ENV_PATH.write_text("OPENAI_API_KEY=")

    load_dotenv()  # Load các biến môi trường ở file .env
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Load GROQ_API_KEY từ biến môi trường
    OPEN_API_KEY = os.getenv('OPEN_API_KEY')

    VECDB = DATA / "chroma_db"
    # VECDB = DATA / '.vecdb'


if __name__ == '__main__':
    print(Config.OPEN_API_KEY)
