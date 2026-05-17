import asyncio
import logging
from typing import Optional, List, Dict, Any
import litellm
from litellm import acompletion

logger = logging.getLogger(__name__)


class LLMAdapter:
    """统一的 LLM 调用适配层，基于 LiteLLM 支持 100+ 种模型"""

    def __init__(self):
        litellm.drop_params = True
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

    async def chat(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 60.0,
        **kwargs,
    ) -> Dict[str, Any]:
        params = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": timeout,
            **kwargs,
        }
        if api_key:
            params["api_key"] = api_key
        if api_base:
            params["api_base"] = api_base

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await acompletion(**params)
                usage = response.usage
                return {
                    "content": response.choices[0].message.content or "",
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": usage.prompt_tokens if usage else 0,
                        "completion_tokens": usage.completion_tokens if usage else 0,
                        "total_tokens": (usage.prompt_tokens + usage.completion_tokens) if usage else 0,
                    },
                }
            except Exception as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt)
                logger.warning(
                    "LLM call failed (attempt %d/%d) for model=%s: %s. Retrying in %.1fs...",
                    attempt + 1, self.max_retries, model_id, str(e)[:200], delay,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(delay)

        logger.error(
            "LLM call failed after %d attempts for model=%s: %s",
            self.max_retries, model_id, str(last_error)[:200],
        )
        raise last_error

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
