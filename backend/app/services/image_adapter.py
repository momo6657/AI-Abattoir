import logging
from typing import Optional, Dict, Any
import httpx
import base64

logger = logging.getLogger(__name__)


class ImageAdapter:
    """图像生成适配层，支持 DALL-E、Stable Diffusion 等"""

    async def generate(
        self,
        provider: str,
        prompt: str,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model: str = "dall-e-3",
        size: str = "1024x1024",
        **kwargs,
    ) -> Dict[str, Any]:
        if not api_key:
            raise ValueError(f"API key is required for image provider '{provider}'")
        if not prompt or not prompt.strip():
            raise ValueError("Prompt is required for image generation")

        logger.info("Generating image: provider=%s model=%s size=%s", provider, model, size)

        if provider == "openai":
            return await self._generate_openai(prompt, api_key, api_base, model, size, **kwargs)
        elif provider == "stability":
            return await self._generate_stability(prompt, api_key, model, **kwargs)
        else:
            raise ValueError(f"Unsupported image provider: {provider}")

    async def _generate_openai(
        self, prompt: str, api_key: str, api_base: Optional[str], model: str, size: str, **kwargs
    ) -> Dict[str, Any]:
        base_url = (api_base or "https://api.openai.com").rstrip("/")
        url = f"{base_url}/v1/images/generations"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "prompt": prompt, "size": size, "n": 1, "response_format": "b64_json"},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()

                image_b64 = data["data"][0]["b64_json"]
                logger.info("Image generated successfully via OpenAI-compatible API, model=%s", model)

                return {
                    "image_b64": image_b64,
                    "revised_prompt": data["data"][0].get("revised_prompt"),
                    "provider": "openai",
                    "model": model,
                }
        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenAI image API error: status=%d body=%s",
                e.response.status_code, e.response.text[:500],
            )
            raise RuntimeError(
                f"Image generation failed (HTTP {e.response.status_code}): {e.response.text[:200]}"
            ) from e
        except httpx.RequestError as e:
            logger.error("OpenAI image API request error: %s", str(e)[:200])
            raise RuntimeError(f"Image generation request failed: {str(e)[:200]}") from e

    async def _generate_stability(
        self, prompt: str, api_key: str, model: str, **kwargs
    ) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"text_prompts": [{"text": prompt}], "cfg_scale": 7, "steps": 30},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()

                image_b64 = data["artifacts"][0]["base64"]
                logger.info("Image generated successfully via Stability AI, model=%s", model)

                return {
                    "image_b64": image_b64,
                    "provider": "stability",
                    "model": model,
                }
        except httpx.HTTPStatusError as e:
            logger.error(
                "Stability AI image API error: status=%d body=%s",
                e.response.status_code, e.response.text[:500],
            )
            raise RuntimeError(
                f"Image generation failed (HTTP {e.response.status_code}): {e.response.text[:200]}"
            ) from e
        except httpx.RequestError as e:
            logger.error("Stability AI image API request error: %s", str(e)[:200])
            raise RuntimeError(f"Image generation request failed: {str(e)[:200]}") from e


image_adapter = ImageAdapter()
