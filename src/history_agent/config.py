import os
from dotenv import load_dotenv
from pathlib import Path


class Config:
    PROJECT_PATH = Path(__file__).resolve().parents[2]  # Đường dẫn folder chính của dự án

    LOGFILES = PROJECT_PATH / "logfiles"  # Đường dẫn đến folder chứa các file log
    LOGFILES.mkdir(exist_ok=True)

    DATA = PROJECT_PATH / "data"  # Đường dẫn đến folder chứa data
    DATA.mkdir(exist_ok=True)

    INPUT = DATA / "input"
    INPUT.mkdir(exist_ok=True)

    OUTPUT = DATA / "output"
    OUTPUT.mkdir(exist_ok=True)

    # DOWNLOADS = PROJECT_PATH / "downloads"  # Đường dẫn đến folder chứa các file log
    # DOWNLOADS.mkdir(exist_ok=True)

    ENV_PATH = Path(PROJECT_PATH) / ".env"
    if not ENV_PATH.exists():
        ENV_PATH.write_text("GROQ_API_KEY=")
        ENV_PATH.write_text("OPENAI_API_KEY=")

    load_dotenv()  # Load các biến môi trường ở file .env
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # Load GROQ_API_KEY từ biến môi trường

    PROMPTS = DATA / "prompts"
    PROMPTS.mkdir(exist_ok=True)

    VECDB = DATA / ".vecdb"



if __name__ == '__main__':
    print(Config.PROJECT_PATH)
