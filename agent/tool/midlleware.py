from typing import Callable, Awaitable
from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from utils.logger_handler import logger


class MonitorMiddleware(AgentMiddleware):
    """同时支持 stream()（同步）和 astream()（异步）的监控中间件。"""

    # ── 工具调用监控 ──────────────────────────────────────────────────────────

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
        logger.info(f"[tool monitor]传入参数：{request.tool_call['args']}")
        try:
            result = handler(request)
            logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")
            return result
        except Exception as e:
            logger.error(f"工具{request.tool_call['name']}调用失败，原因：{str(e)}")
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
        logger.info(f"[tool monitor]传入参数：{request.tool_call['args']}")
        try:
            result = await handler(request)
            logger.info(f"[tool monitor]工具{request.tool_call['name']}调用成功")
            return result
        except Exception as e:
            logger.error(f"工具{request.tool_call['name']}调用失败，原因：{str(e)}")
            raise

    # ── 模型调用前日志 ────────────────────────────────────────────────────────

    def before_model(self, state: AgentState, runtime: Runtime):
        logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")
        logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content}")
        logger.debug(f"[log_before_model]当前上下文：{runtime.context}")

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        logger.info(f"[log_before_model]即将调用模型，带有{len(state['messages'])}条消息。")
        logger.debug(f"[log_before_model]{type(state['messages'][-1]).__name__} | {state['messages'][-1].content}")
        logger.debug(f"[log_before_model]当前上下文：{runtime.context}")
