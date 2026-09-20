from src.history_agent.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner
from src.history_agent.inf.tools.ddgs_tool import DDGSTool
from src.history_agent.inf.tools.open_url_tool import OpenURLTool
from src.history_agent.inf.tools.rag_tool import RAGTool
from src.history_agent.inf.tools.rag_tool.baai_reranker import BAAIReranker
from src.history_agent.inf.tools.rag_tool.chroma_baai_retriever import ChromaBAAIRetriever
from src.history_agent.app.tool_manager import ToolManager
from src.history_agent.app.agent import Agent
from src.history_agent.pre.agent.agent_controller import AgentController
from src.history_agent.config import Config

def build_agent_controller():

    reasoner = OpenAIModelReasoner(
        api_key=Config.OPEN_API_KEY,
        model="gpt-5.6-luna",
    )
    '''Khai báo bộ suy luộn sử dụng trong agent'''

    tool_manager = ToolManager(
        tools=[
            # DDGSTool(),
            # OpenURLTool(),
            RAGTool(
                retriever=ChromaBAAIRetriever(
                    path=Config.VECDB,
                    collection_name='history'
                ),
                reranker=BAAIReranker()
            ),
        ]
    )
    '''Khai báo các tool sử dụng trong agent'''

    agent = Agent(
        model_reasoner=reasoner,
        tool_manager=tool_manager,
    )

    return AgentController(
        agent=agent
    )
