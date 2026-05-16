from typing import Optional, Dict, Any
import httpx
import base64


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
        if provider == "openai":
            return await self._generate_openai(prompt, api_key, model, size, **kwargs)
        elif provider == "stability":
            return await self._generate_stability(prompt, api_key, model, **kwargs)
        else:
            raise ValueError(f"Unsupported image provider: {provider}")

    async def _generate_openai(
        self, prompt: str, api_key: str, model: str, size: str, **kwargs
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "prompt": prompt, "size": size, "n": 1, "response_format": "b64_json"},
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            return {
                "image_b64": data["data"][0]["b64_json"],
                "revised_prompt": data["data"][0].get("revised_prompt"),
                "provider": "openai",
                "model": model,
            }

    async def _generate_stability(
        self, prompt: str, api_key: str, model: str, **kwargs
    ) -> Dict[str, Any]:
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
            return {
                "image_b64": data["artifacts"][0]["base64"],
                "provider": "stability",
                "model": model,
            }


image_adapter = ImageAdapter()
