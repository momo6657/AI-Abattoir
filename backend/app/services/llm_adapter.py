from typing import Optional, List, Dict, Any
import litellm
from litellm import acompletion


class LLMAdapter:
    """统一的 LLM 调用适配层，基于 LiteLLM 支持 100+ 种模型"""

    def __init__(self):
        litellm.drop_params = True

    async def chat(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        params = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        if api_key:
            params["api_key"] = api_key
        if api_base:
            params["api_base"] = api_base

        response = await acompletion(**params)
        return {
            "content": response.choices[0].message.content,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_with_vision(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        return await self.chat(
            model_id=model_id,
            messages=messages,
            api_key=api_key,
            api_base=api_base,
            **kwargs,
        )


llm_adapter = LLMAdapter()
