"""Infrastructure Config - Quản lý cấu hình môi trường và các đường dẫn hệ thống.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Cấu hình toàn bộ ứng dụng Agent v2."""

    project_path: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent
    )
    groq_api_key: str | None = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY")
    )
    openai_api_key: str | None = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
    )
    openrouter_api_key: str | None = field(
        default_factory=lambda: os.getenv("OPENROUTER_API_KEY")
    )
    ollama_base_url: str = field(
        default_factory=lambda: (
                os.getenv("OLLAMA_BASE_URL")
                or os.getenv("OLLAMA_HOST")
                or "http://localhost:11434"
        )
    )
    ollama_api_key: str | None = field(
        default_factory=lambda: os.getenv("OLLAMA_API_KEY")
    )
    web_storage_secret: str | None = field(
        default_factory=lambda: os.getenv("WEB_STORAGE_SECRET")
    )
    admin_username: str | None = field(
        default_factory=lambda: os.getenv("ADMIN_USERNAME")
    )
    admin_password: str | None = field(
        default_factory=lambda: os.getenv("ADMIN_PASSWORD")
    )

    # --- Cấu hình PostgreSQL từ .env ---
    db_name: str = field(
        default_factory=lambda: os.getenv("DB_NAME", "vnhisgeoqa")
    )
    db_user: str = field(
        default_factory=lambda: os.getenv("DB_USER", "postgres")
    )
    db_password: str = field(
        default_factory=lambda: os.getenv("DB_PASSWORD", "")
    )
    db_host: str = field(
        default_factory=lambda: os.getenv("DB_HOST", "localhost")
    )
    db_port: str = field(
        default_factory=lambda: os.getenv("DB_PORT", "5432")
    )

    # --- Cấu hình Neo4j & Qdrant từ .env ---
    neo4j_uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
    )
    neo4j_user: str = field(
        default_factory=lambda: os.getenv("NEO4J_USER", "neo4j")
    )
    neo4j_password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "")
    )
    qdrant_url: str = field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    qdrant_collection: str = field(
        default_factory=lambda: os.getenv("QDRANT_COLLECTION", "vnhis")
    )

    @property
    def path_folder_log(self) -> Path:
        """Thư mục lưu trữ log."""
        path = self.project_path / "logfiles"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data(self) -> Path:
        """Thư mục lưu trữ dữ liệu chung."""
        path = self.project_path / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def database_path(self) -> Path:
        """Đường dẫn file CSDL SQLite."""
        return self.data / "agent.sqlite3"

    @property
    def sqlite_url(self) -> str:
        """URL kết nối CSDL SQLite."""
        return f"sqlite:///{self.database_path.as_posix()}"

    @property
    def postgres_url(self) -> str:
        """URL kết nối CSDL PostgreSQL (đã encode mật khẩu chứa ký tự đặc biệt)."""
        encoded_pw = quote_plus(self.db_password)
        return (
            f"postgresql+psycopg2://{self.db_user}:{encoded_pw}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def agent_workspace(self) -> Path:
        """Thư mục làm việc của agent (được giới hạn cho các tool ghi/đọc file)."""
        path = self.data / "agent_workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path


if __name__ == '__main__':
    # from platformdirs import user_cache_dir, user_data_dir
    #
    # print(user_cache_dir("MyApp"))
    # print(user_data_dir("MyApp"))
    print(Config().project_path)
