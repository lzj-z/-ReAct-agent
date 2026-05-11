from model.init_llm import deepseekllm
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from agent.tool.tools import (
    get_weather, use_rag_service,
    get_user_location, get_current_time,
    save_user_record, get_user_id,
    get_user_history,
)
from utils.loader_prompt import load_prompt
from agent.tool.midlleware import MonitorMiddleware


class ReactAgent:
    def __init__(self, checkpointer=None):
        self.agent = create_agent(
            model=deepseekllm,
            system_prompt=load_prompt("agent_system_prompt.txt"),
            tools=[
                get_weather, use_rag_service,
                get_user_location, get_current_time,
                save_user_record, get_user_id,
                get_user_history,
            ],
            middleware=[MonitorMiddleware()],
            checkpointer=checkpointer,
        )

    def invoke(self, user_input: str) -> str:
        result = self.agent.invoke({"messages": [HumanMessage(content=user_input)]})
        return result["messages"][-1].content

    def stream(self, user_input: str):
        for chunk in self.agent.stream({"messages": [HumanMessage(content=user_input)]}):
            for node_output in chunk.values():
                msgs = node_output.get("messages", [])
                if msgs:
                    yield msgs[-1].content
