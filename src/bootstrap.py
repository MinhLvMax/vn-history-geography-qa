"""Bootstrap - Composition Root khởi tạo các thành phần và tiêm phụ thuộc (Dependency Injection).

File này nằm ngoài 4 tầng (Domain, Application, Infrastructure, Presentation) vì nó là
nơi duy nhất nắm giữ chi tiết của tất cả các tầng để thực hiện việc "nối dây" (wiring)
các dependency trước khi bàn giao quyền điều khiển cho tầng Presentation hoặc Application.
Các file trong `entries_point/` chỉ gọi các hàm `run_*` ở đây để chạy dự án.
"""

import os
import secrets
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from src.application.agent_service import AgentService
from src.application.context_strategy import (
    ContextStrategyPort,
    NoOpContextStrategy,
    ObservationMaskingWindowStrategy,
)
from src.application.model_probe import ModelProbePort
from src.application.rag_service import (
    EmbedderPort,
    RagSearchService,
    RerankerPort,
    VectorRetrieverPort,
)
from src.application.repositories import (
    ConversationRepository,
    MessageRepository,
    ModelRepository,
    SessionRepository,
    UserRepository,
)
from src.application.security import PasswordHasher
from src.application.tool_service import ToolExecutorService
from src.application.usecases import (
    CreateConversationUseCase,
    DeleteConversationUseCase,
    DeleteModelUseCase,
    EnsureAdminUseCase,
    GetConversationMessagesUseCase,
    GetCurrentUserUseCase,
    GetUiStateUseCase,
    ListConversationsUseCase,
    ListModelsUseCase,
    LoginUseCase,
    LogoutUseCase,
    RegisterUseCase,
    RenameConversationUseCase,
    SaveModelUseCase,
    SaveUiStateUseCase,
    SendMessageUseCase,
    TestModelUseCase,
)
from src.domain.exceptions import APIKeyDoesNotExist, AppError
from src.domain.ports import LLMPort, LoggerPort, Tool
from src.infrastructure.config import Config
from src.infrastructure.llm.agy_cli_llm import AgyCLILLM
from src.infrastructure.llm.claude_cli_llm import ClaudeCLILLM
from src.infrastructure.llm.groq_llm import GroqLLM
from src.infrastructure.llm.model_probe import LlmModelProbe
from src.infrastructure.llm.ollama_llm import OllamaLLM
from src.infrastructure.llm.openai_llm import OpenAILLM
from src.infrastructure.logger_service import StandardLoggerService
from src.infrastructure.persistence.sqlalchemy.database import create_database
from src.infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyModelRepository,
    SqlAlchemySessionRepository,
    SqlAlchemyUserRepository,
)
from src.infrastructure.security.scrypt_password_hasher import ScryptPasswordHasher
from src.infrastructure.rag.cross_encoder_reranker import CrossEncoderReranker
from src.infrastructure.rag.huggingface_embedder import HuggingFaceEmbedder
from src.infrastructure.rag.qdrant_retriever import QdrantVectorRetriever
from src.infrastructure.tools.knowledge.read_chunks_by_ids_tool import ReadChunksByIdsTool
from src.infrastructure.tools.knowledge.search_knowledge_tool import SearchKnowledgeTool
from src.presentation.model_catalog import ModelCatalog

# Nhà cung cấp có adapter trong build_llm. Đây là phần duy nhất còn nằm trong code;
# danh sách model và tool built-in do quản trị viên nhập trong bảng `models`.
SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {"agy_cli", "claude_cli", "openai", "groq", "ollama"}
)


class Bootstrap:
    """Composition Root cấu hình và lắp ráp toàn bộ hệ thống Agent."""

    def __init__(self, app_config: Config | None = None):
        self.app_config = app_config or Config()
        self._logger: LoggerPort | None = None
        self._tool_executor: ToolExecutorService | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._embedder: EmbedderPort | None = None
        self._vector_retriever: VectorRetrieverPort | None = None
        self._reranker: RerankerPort | None = None
        self._rag_service: RagSearchService | None = None

    # --- Tài nguyên (tạm thời hard-code, sau này có thể thay bằng file / DB / API) ---

    def build_system_prompt(self) -> str:
        """Khởi tạo system prompt chuẩn kiến trúc Agentic (không phụ thuộc tên tool cụ thể)."""
        return (
            "Bạn là trợ lý AI chuyên gia về Lịch sử và Địa lý Việt Nam, hoạt động theo tiêu chuẩn kiểm chứng học thuật trung thực.\n\n"
            "NGUYÊN TẮC HOẠT ĐỘNG BẮT BUỘC:\n\n"
            "1. QUY TRÌNH TRA CỨU & KHAI THÁC TƯ LIỆU:\n"
            "   - Mọi câu hỏi về sự kiện, nhân vật, trận đánh, địa danh hoặc niên đại lịch sử BẮT BUỘC phải được tra cứu bằng các công cụ tìm kiếm được cung cấp trước khi trả lời.\n"
            "   - Nhận diện trang khuyết: Khi đọc các đoạn tư liệu tìm thấy, nếu thấy văn bản bị ngắt quãng giữa chừng hoặc số trang bị nhảy cóc (ví dụ có trang mở đầu và trang kết thúc nhưng thiếu các trang diễn biến ở giữa), bạn PHẢI chủ động sử dụng công cụ đọc trang theo mã định danh để lấy bổ sung các trang còn thiếu trước khi tổng hợp.\n"
            "   - Tự động tinh chỉnh truy vấn: Nếu kết quả tìm kiếm ban đầu chỉ toàn thông tin phụ lục, tiểu sử danh nhân mà thiếu diễn biến chiến sự, hãy chủ động tìm kiếm tiếp với các từ khóa chuyên sâu hơn về diễn biến trận đánh hoặc chiến dịch đó.\n\n"
            "2. TRUNG THỰC TUYỆT ĐỐI VỚI VĂN BẢN (CẤM SUY DIỄN & BỔ SUNG KIẾN THỨC BÊN NGOÀI):\n"
            "   - CHỈ ĐƯỢC PHÉP trả lời dựa trên những sự kiện, nhân vật, số liệu và nhận định xuất hiện trực tiếp trong các đoạn tư liệu đã thu thập được.\n"
            "   - TUYỆT ĐỐI KHÔNG dùng trí nhớ có sẵn để tự bổ sung các diễn biến, đạo quân, số lượng viện binh, hội thề... nếu các đoạn trích không đề cập.\n"
            "   - Phân định rõ vai trò nhân vật (ai là chủ tướng, ai theo phò tá, ai phản nghịch) dựa đúng từng câu chữ trong văn bản, cấm gán ghép tùy tiện.\n"
            "   - Xử lý thiếu hụt thông tin: Nếu tư liệu thu thập được chưa đủ bao quát toàn bộ sự kiện, chỉ trình bày những phần có trong tư liệu và nêu rõ ràng: 'Tư liệu hiện tại chưa bao gồm diễn biến của giai đoạn/chi tiết này'.\n\n"
            "3. QUY TẮC TRÍCH DẪN NGUỒN CHÍNH XÁC:\n"
            "   - Mọi thông tin, số liệu đưa vào câu trả lời PHẢI kèm mã nguồn ở cuối câu theo định dạng `[Nguồn: <mã_nguồn>]` (lấy chính xác từ trường Nguồn của đoạn tư liệu chứa thông tin đó).\n"
            "   - TUYỆT ĐỐI CẤM gán mã nguồn vào câu văn nếu nội dung câu đó không thực sự nằm trong trang sách tương ứng.\n"
            "   - Trình bày mạch lạc, thuần tiếng Việt học thuật, khách quan, khoa học, dễ nhìn."
        )

    def load_model_catalog(self) -> ModelCatalog:
        """Dựng danh mục {nhà cung cấp: {tên chuẩn: ModelInfo}} từ bảng `models` (chỉ model đang bật).

        Gọi lại mỗi lần cần hiển thị để thay đổi của quản trị viên có hiệu lực ngay.
        """
        catalog: ModelCatalog = {}
        for model in self.build_model_repository().list_all():
            if not model.is_enabled:
                continue
            catalog.setdefault(model.provider, {})[model.model_code] = {
                "display_name": model.display_name,
                "reasoning": list(model.reasoning_modes),
                "default_reasoning": model.default_reasoning,
                "builtin_tools": list(model.builtin_tools),
                "is_default": model.is_default,
            }
        return catalog

    # --- Các thành phần hệ thống ---

    def build_logger(self) -> LoggerPort:
        """Khởi tạo dịch vụ logging dùng chung cho ứng dụng."""
        if self._logger is None:
            log_path = self.app_config.path_folder_log / "app.log"
            self._logger = StandardLoggerService(log_file=log_path)
        return self._logger

    def build_llm(
        self,
        provider: str,
        model_name: str,
        reasoning: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> LLMPort:
        """Khởi tạo LLM adapter theo nhà cung cấp, model, chế độ suy luận và tool built-in chọn từ UI."""
        if provider == "agy_cli":
            return self.build_agy_cli_llm(
                model_name=model_name, effort=reasoning, builtin_tools=builtin_tools
            )
        if provider == "claude_cli":
            return self.build_claude_cli_llm(
                model_name=model_name, effort=reasoning, builtin_tools=builtin_tools
            )
        if provider == "groq":
            return self.build_groq_llm(
                model_name=model_name, reasoning_effort=reasoning, builtin_tools=builtin_tools
            )
        if provider == "openai":
            return self.build_openai_llm(
                model_name=model_name, reasoning_effort=reasoning, builtin_tools=builtin_tools
            )
        if provider == "ollama":
            return self.build_ollama_llm(
                model_name=model_name, reasoning_effort=reasoning, builtin_tools=builtin_tools
            )
        raise AppError(f"Nhà cung cấp LLM không được hỗ trợ: {provider}")

    def build_agy_cli_llm(
        self,
        model_name: str,
        effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> AgyCLILLM:
        """Khởi tạo adapter gọi model qua Antigravity CLI (dùng phiên đăng nhập, không cần API key)."""
        return AgyCLILLM(
            model_name=model_name,
            effort=effort,
            builtin_tools=builtin_tools,
            cwd=self.app_config.agent_workspace,
        )

    def build_claude_cli_llm(
        self,
        model_name: str,
        effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> ClaudeCLILLM:
        """Khởi tạo adapter gọi Claude qua Claude Code CLI (dùng phiên đăng nhập, không cần API key)."""
        return ClaudeCLILLM(
            model_name=model_name,
            effort=effort,
            builtin_tools=builtin_tools,
            cwd=self.app_config.agent_workspace,
        )

    def build_openai_llm(
        self,
        model_name: str,
        reasoning_effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> OpenAILLM:
        """Khởi tạo OpenAI LLM adapter từ cấu hình."""
        apikey = self.app_config.openai_api_key
        if not apikey:
            raise APIKeyDoesNotExist(
                "Chưa thiết lập OPENAI_API_KEY. Vui lòng thêm vào file .env hoặc biến môi trường."
            )
        return OpenAILLM(
            api_key=apikey,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            builtin_tools=builtin_tools,
        )

    def build_groq_llm(
        self,
        model_name: str,
        reasoning_effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> GroqLLM:
        """Khởi tạo Groq LLM adapter từ cấu hình."""
        apikey = self.app_config.groq_api_key
        if not apikey:
            raise APIKeyDoesNotExist(
                "Chưa thiết lập GROQ_API_KEY. Vui lòng thêm vào file .env hoặc biến môi trường."
            )
        return GroqLLM(
            api_key=apikey,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            builtin_tools=builtin_tools,
        )

    def build_ollama_llm(
        self,
        model_name: str,
        reasoning_effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> OllamaLLM:
        """Khởi tạo Ollama LLM adapter từ cấu hình (mặc định http://localhost:11434)."""
        return OllamaLLM(
            model_name=model_name,
            base_url=self.app_config.ollama_base_url,
            api_key=self.app_config.ollama_api_key,
            reasoning_effort=reasoning_effort,
            builtin_tools=builtin_tools,
        )

    # --- Lưu trữ (CSDL) ---

    def build_database_url(self) -> str:
        """URL kết nối CSDL. Đổi sang CSDL khác (PostgreSQL, MySQL...) chỉ cần sửa ở đây."""
        # return self.app_config.sqlite_url
        return self.app_config.postgres_url

    def build_session_factory(self) -> sessionmaker[Session]:
        """Khởi tạo kết nối CSDL (tạo bảng nếu chưa có) và session factory dùng chung."""
        if self._session_factory is None:
            self._session_factory = create_database(self.build_database_url())
        return self._session_factory

    def build_user_repository(self) -> UserRepository:
        """Khởi tạo kho lưu trữ người dùng."""
        return SqlAlchemyUserRepository(self.build_session_factory())

    def build_conversation_repository(self) -> ConversationRepository:
        """Khởi tạo kho lưu trữ hội thoại."""
        return SqlAlchemyConversationRepository(self.build_session_factory())

    def build_message_repository(self) -> MessageRepository:
        """Khởi tạo kho lưu trữ tin nhắn."""
        return SqlAlchemyMessageRepository(self.build_session_factory())

    def build_session_repository(self) -> SessionRepository:
        """Khởi tạo kho lưu trữ phiên đăng nhập."""
        return SqlAlchemySessionRepository(self.build_session_factory())

    def build_password_hasher(self) -> PasswordHasher:
        """Khởi tạo bộ băm mật khẩu."""
        return ScryptPasswordHasher()

    def build_model_repository(self) -> ModelRepository:
        """Khởi tạo kho lưu trữ danh mục model."""
        return SqlAlchemyModelRepository(self.build_session_factory())

    def build_model_probe(self) -> ModelProbePort:
        """Khởi tạo bộ kiểm tra model (gọi API thật qua đúng adapter của build_llm)."""
        return LlmModelProbe(build_llm=self.build_llm)

    def build_list_models_usecase(self) -> ListModelsUseCase:
        return ListModelsUseCase(
            self.build_session_repository(), self.build_user_repository(), self.build_model_repository()
        )

    def build_save_model_usecase(self) -> SaveModelUseCase:
        return SaveModelUseCase(
            self.build_session_repository(),
            self.build_user_repository(),
            self.build_model_repository(),
            SUPPORTED_PROVIDERS,
        )

    def build_delete_model_usecase(self) -> DeleteModelUseCase:
        return DeleteModelUseCase(
            self.build_session_repository(), self.build_user_repository(), self.build_model_repository()
        )

    def build_test_model_usecase(self) -> TestModelUseCase:
        return TestModelUseCase(
            self.build_session_repository(),
            self.build_user_repository(),
            self.build_model_repository(),
            self.build_model_probe(),
            SUPPORTED_PROVIDERS,
        )

    # --- Use cases ---

    def build_ensure_admin_usecase(self) -> EnsureAdminUseCase:
        return EnsureAdminUseCase(self.build_user_repository(), self.build_password_hasher())

    def ensure_admin_account(self) -> None:
        """Bảo đảm có tài khoản admin trước khi khởi chạy ứng dụng (tạo từ ADMIN_USERNAME / ADMIN_PASSWORD nếu cần)."""
        self.build_ensure_admin_usecase().execute(
            self.app_config.admin_username, self.app_config.admin_password
        )

    def build_register_usecase(self) -> RegisterUseCase:
        return RegisterUseCase(self.build_user_repository(), self.build_password_hasher())

    def build_get_ui_state_usecase(self) -> GetUiStateUseCase:
        return GetUiStateUseCase(self.build_session_repository(), self.build_user_repository())

    def build_save_ui_state_usecase(self) -> SaveUiStateUseCase:
        return SaveUiStateUseCase(self.build_session_repository(), self.build_user_repository())

    def build_login_usecase(self) -> LoginUseCase:
        return LoginUseCase(
            self.build_user_repository(),
            self.build_session_repository(),
            self.build_password_hasher(),
        )

    def build_logout_usecase(self) -> LogoutUseCase:
        return LogoutUseCase(self.build_session_repository())

    def build_get_current_user_usecase(self) -> GetCurrentUserUseCase:
        return GetCurrentUserUseCase(self.build_session_repository(), self.build_user_repository())

    def build_list_conversations_usecase(self) -> ListConversationsUseCase:
        return ListConversationsUseCase(
            self.build_session_repository(), self.build_conversation_repository()
        )

    def build_get_conversation_messages_usecase(self) -> GetConversationMessagesUseCase:
        return GetConversationMessagesUseCase(
            self.build_session_repository(),
            self.build_conversation_repository(),
            self.build_message_repository(),
        )

    def build_create_conversation_usecase(self) -> CreateConversationUseCase:
        return CreateConversationUseCase(
            self.build_session_repository(), self.build_conversation_repository()
        )

    def build_delete_conversation_usecase(self) -> DeleteConversationUseCase:
        return DeleteConversationUseCase(
            self.build_session_repository(), self.build_conversation_repository()
        )

    def build_rename_conversation_usecase(self) -> RenameConversationUseCase:
        return RenameConversationUseCase(
            self.build_session_repository(), self.build_conversation_repository()
        )

    def build_context_strategy(self) -> ContextStrategyPort:
        """Chiến lược quản lý bối cảnh hội thoại. Đổi chiến lược hoặc ngưỡng cắt tại đây."""
        # return NoOpContextStrategy()
        return ObservationMaskingWindowStrategy(
            max_turns=3,
            keep_raw_tool_turns=1,
            max_history_chars=14000,
        )

    def build_send_message_usecase(self) -> SendMessageUseCase:
        return SendMessageUseCase(
            sessions=self.build_session_repository(),
            conversations=self.build_conversation_repository(),
            messages=self.build_message_repository(),
            agent_service_factory=self.build_agent_service,
            tools=list(self.build_tool_executor().tools_map.values()),
            system_prompt=self.build_system_prompt(),
            context_strategy=self.build_context_strategy(),
        )

    # --- RAG Pipeline (Embedder -> Qdrant Retriever -> Cross-Encoder Reranker) ---

    def build_embedder(self) -> EmbedderPort:
        """Khởi tạo bộ mã hóa câu hỏi sang vector. Đổi model embedding chỉ cần sửa ở đây."""
        if self._embedder is None:
            self._embedder = HuggingFaceEmbedder(
                model_name="bkai-foundation-models/vietnamese-bi-encoder",
                logger=self.build_logger(),
            )
        return self._embedder

    def build_vector_retriever(self) -> VectorRetrieverPort:
        """Khởi tạo bộ truy xuất Qdrant Vector DB."""
        if self._vector_retriever is None:
            self._vector_retriever = QdrantVectorRetriever(
                url=self.app_config.qdrant_url,
                default_collection=self.app_config.qdrant_collection,
                logger=self.build_logger(),
            )
        return self._vector_retriever

    def build_reranker(self) -> RerankerPort:
        """Khởi tạo bộ xếp hạng lại Cross-Encoder. Đổi model reranker chỉ cần sửa ở đây."""
        if self._reranker is None:
            self._reranker = CrossEncoderReranker(
                model_name="itdainb/PhoRanker",
                max_length=256,
                # model_name="jinaai/jina-reranker-v2-base-multilingual", max_length=1024,
                # model_name="BAAI/bge-reranker-v2-m3", max_length=1024,
                logger=self.build_logger(),
            )
        return self._reranker

    def build_rag_service(self) -> RagSearchService:
        """Khởi tạo dịch vụ tìm kiếm RAG 2 tầng (Retrieve Top-K -> Rerank Top-N)."""
        if self._rag_service is None:
            self._rag_service = RagSearchService(
                embedder=self.build_embedder(),
                retriever=self.build_vector_retriever(),
                reranker=self.build_reranker(),
                logger=self.build_logger(),
                default_retrieve_top_k=20,
                default_rerank_top_n=5,
            )
        return self._rag_service

    def build_tools(self) -> list[Tool]:
        """Danh sách tool của Agent (gồm RAG Vector Search + Reranker và Đọc chunk theo ID)."""
        rag_service = self.build_rag_service()
        return [
            SearchKnowledgeTool(rag_service=rag_service),
            ReadChunksByIdsTool(rag_service=rag_service),
        ]

    def build_tool_executor(self) -> ToolExecutorService:
        """Khởi tạo danh sách các tool và dịch vụ điều phối tool có kèm logger."""
        if self._tool_executor is None:
            self._tool_executor = ToolExecutorService(
                tools=self.build_tools(),
                logger=self.build_logger(),
            )
        return self._tool_executor

    def build_agent_service(
        self,
        provider: str,
        model_name: str,
        reasoning: str | None = None,
        builtin_tools: list[str] | None = None,
    ) -> AgentService:
        """Khởi tạo AgentService với đầy đủ các dependency đã được tiêm vào."""
        return AgentService(
            llm=self.build_llm(
                provider=provider,
                model_name=model_name,
                reasoning=reasoning,
                builtin_tools=builtin_tools,
            ),
            tool_executor=self.build_tool_executor(),
            logger=self.build_logger(),
        )

    # --- Lắp ráp tầng Presentation (được gọi từ entries_point) ---

    def run_cli(self) -> None:
        """Chạy dự án dưới dạng giao diện dòng lệnh."""
        from src.presentation.cli import run_cli

        self.ensure_admin_account()
        run_cli(
            agent_service_factory=self.build_agent_service,
            tools=list(self.build_tool_executor().tools_map.values()),
            system_prompt=self.build_system_prompt(),
            model_catalog=self.load_model_catalog,
            context_strategy=self.build_context_strategy(),
        )

    def run_web(self) -> None:
        """Chạy dự án dưới dạng giao diện web NiceGUI."""
        from src.presentation.web_ui import WebUseCases, run_web_ui

        self.ensure_admin_account()
        run_web_ui(
            usecases=WebUseCases(
                register=self.build_register_usecase(),
                login=self.build_login_usecase(),
                logout=self.build_logout_usecase(),
                get_current_user=self.build_get_current_user_usecase(),
                get_ui_state=self.build_get_ui_state_usecase(),
                save_ui_state=self.build_save_ui_state_usecase(),
                list_conversations=self.build_list_conversations_usecase(),
                get_conversation_messages=self.build_get_conversation_messages_usecase(),
                create_conversation=self.build_create_conversation_usecase(),
                rename_conversation=self.build_rename_conversation_usecase(),
                delete_conversation=self.build_delete_conversation_usecase(),
                send_message=self.build_send_message_usecase(),
                list_models=self.build_list_models_usecase(),
                save_model=self.build_save_model_usecase(),
                delete_model=self.build_delete_model_usecase(),
                test_model=self.build_test_model_usecase(),
            ),
            model_catalog=self.load_model_catalog,
            providers=sorted(SUPPORTED_PROVIDERS),
            storage_secret=self.build_web_storage_secret(),
        )

    def build_web_storage_secret(self) -> str:
        """Khóa ký cookie phiên trình duyệt của NiceGUI.

        Lấy từ WEB_STORAGE_SECRET; nếu chưa đặt thì sinh ngẫu nhiên mỗi lần chạy
        (khi đó khởi động lại app sẽ phải đăng nhập lại).
        """
        return self.app_config.web_storage_secret or secrets.token_urlsafe(32)
