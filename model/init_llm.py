from typing import Any

import requests
from langchain.chat_models import init_chat_model
from langchain_deepseek import ChatDeepSeek
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.prompt_values import PromptValue
from model.loadenv_utils import get_llm_config
from langchain_community.embeddings import DashScopeEmbeddings

config = get_llm_config()
deepseek_api_key = config['deepseek_api_key']
deepseek_base_url = config['deepseek_base_url']
dashscope_api_key = config['dashscope_api_key']
dashscope_base_url = config['dashscope_base_url']
unsplash_access_key = config['unsplash_access_key']
gaode_api_key = config['gaode_api_key']


class ChatDeepSeekThinking(ChatDeepSeek):
    # DeepSeek 的 thinking 模式要求历史 assistant 消息回传 reasoning_content，
    # 但 langchain-deepseek 1.0.1 只读不写，导致 Agent 在工具调用后第二轮请求 400。
    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages = self._convert_input(input_).to_messages()
        for original, serialized in zip(messages, payload.get("messages", [])):
            if (
                isinstance(original, AIMessage)
                and serialized.get("role") == "assistant"
            ):
                reasoning = original.additional_kwargs.get("reasoning_content")
                if reasoning:
                    serialized["reasoning_content"] = reasoning
        return payload



deepseekllm = ChatDeepSeekThinking(
    model='deepseek-v4-pro',
    api_key=deepseek_api_key,
    api_base=deepseek_base_url,
)

qwenllm = init_chat_model(
    model='qwen3.5-plus',
    model_provider='openai',
    api_key=dashscope_api_key,
    base_url=dashscope_base_url
)

qwenembedding = DashScopeEmbeddings(
    model="text-embedding-v3",
    dashscope_api_key=dashscope_api_key,
    max_retries=3
)


def test_unsplash(access_key: str) -> bool:
    """测试 Unsplash Access Key 是否有效"""
    url = "https://api.unsplash.com/photos"
    resp = requests.get(url, headers={"Authorization": f"Client-ID {access_key}"}, timeout=10)
    return resp.status_code == 200


def test_gaode(api_key: str) -> bool:
    """测试高德地图 API Key 是否有效（IP 定位接口）"""
    url = "https://restapi.amap.com/v3/ip"
    resp = requests.get(url, params={"key": api_key}, timeout=10)
    data = resp.json()
    # status='1' 表示成功
    return data.get("status") == "1"


if __name__ == "__main__":
    print("=== LLM 初始化状态 ===")
    print(f"DeepSeek LLM:    {deepseekllm}")
    print(f"Qwen LLM:        {qwenllm}")
    print(f"Qwen Embedding:  {qwenembedding}")

    print("\n=== Unsplash 可用性测试 ===")
    if test_unsplash(unsplash_access_key):
        print("Unsplash Access Key: OK")
    else:
        print("Unsplash Access Key: FAILED")

    print("\n=== 高德地图 API 可用性测试 ===")
    if test_gaode(gaode_api_key):
        print("GAODE_APIKEY: OK")
    else:
        print("GAODE_APIKEY: FAILED")
