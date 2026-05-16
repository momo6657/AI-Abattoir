from typing import Optional, Dict, Any
import httpx


class TTSAdapter:
    """TTS/STT 适配层，支持 OpenAI TTS、ElevenLabs 等"""

    async def synthesize(
        self,
        provider: str,
        text: str,
        api_key: Optional[str] = None,
        voice: str = "alloy",
        model: str = "tts-1",
        **kwargs,
    ) -> bytes:
        if provider == "openai":
            return await self._synthesize_openai(text, api_key, voice, model)
        elif provider == "elevenlabs":
            return await self._synthesize_elevenlabs(text, api_key, voice)
        else:
            raise ValueError(f"Unsupported TTS provider: {provider}")

    async def _synthesize_openai(
        self, text: str, api_key: str, voice: str, model: str
    ) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "input": text, "voice": voice},
                timeout=60,
            )
            response.raise_for_status()
            return response.content

    async def _synthesize_elevenlabs(
        self, text: str, api_key: str, voice_id: str
    ) -> bytes:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": api_key},
                json={"text": text, "model_id": "eleven_monolingual_v1"},
                timeout=60,
            )
            response.raise_for_status()
            return response.content


tts_adapter = TTSAdapter()
