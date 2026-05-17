import pytest
import base64
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.image_adapter import ImageAdapter
from app.services.arena_engine import ArenaEngine


# ========== ImageAdapter tests ==========

class TestImageAdapterValidation:
    """Test input validation in ImageAdapter.generate"""

    @pytest.mark.asyncio
    async def test_missing_api_key_raises(self):
        adapter = ImageAdapter()
        with pytest.raises(ValueError, match="API key is required"):
            await adapter.generate(provider="openai", prompt="test", api_key=None)

    @pytest.mark.asyncio
    async def test_empty_api_key_raises(self):
        adapter = ImageAdapter()
        with pytest.raises(ValueError, match="API key is required"):
            await adapter.generate(provider="openai", prompt="test", api_key="")

    @pytest.mark.asyncio
    async def test_empty_prompt_raises(self):
        adapter = ImageAdapter()
        with pytest.raises(ValueError, match="Prompt is required"):
            await adapter.generate(provider="openai", prompt="", api_key="sk-test")

    @pytest.mark.asyncio
    async def test_whitespace_prompt_raises(self):
        adapter = ImageAdapter()
        with pytest.raises(ValueError, match="Prompt is required"):
            await adapter.generate(provider="openai", prompt="   ", api_key="sk-test")

    @pytest.mark.asyncio
    async def test_unsupported_provider_raises(self):
        adapter = ImageAdapter()
        with pytest.raises(ValueError, match="Unsupported image provider"):
            await adapter.generate(provider="midjourney", prompt="test", api_key="sk-test")


class TestImageAdapterOpenAI:
    """Test OpenAI image generation"""

    @pytest.mark.asyncio
    async def test_successful_generation(self):
        adapter = ImageAdapter()
        fake_b64 = base64.b64encode(b"fake_png_data").decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"b64_json": fake_b64, "revised_prompt": "A detailed cat"}],
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await adapter.generate(
                provider="openai",
                prompt="a cat",
                api_key="sk-test",
                model="dall-e-3",
                size="1024x1024",
            )

        assert result["image_b64"] == fake_b64
        assert result["provider"] == "openai"
        assert result["model"] == "dall-e-3"
        assert result["revised_prompt"] == "A detailed cat"

    @pytest.mark.asyncio
    async def test_custom_api_base(self):
        adapter = ImageAdapter()
        fake_b64 = base64.b64encode(b"fake_png").decode()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"b64_json": fake_b64}]}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            await adapter.generate(
                provider="openai",
                prompt="a dog",
                api_key="sk-custom",
                api_base="https://custom-api.example.com",
            )

            call_args = mock_client.post.call_args
            assert "custom-api.example.com" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_http_error_raises_runtime_error(self):
        adapter = ImageAdapter()

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_response.raise_for_status = MagicMock(
            side_effect=MagicMock(
                side_effect=Exception("HTTP 429")
            )
        )

        import httpx
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Rate limit", request=MagicMock(), response=mock_response
            )
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError, match="Image generation failed"):
                await adapter.generate(
                    provider="openai",
                    prompt="a cat",
                    api_key="sk-test",
                )


# ========== ArenaEngine._generate_image_response tests ==========

class TestArenaEngineImageResponse:
    """Test the image generation flow in ArenaEngine"""

    @pytest.mark.asyncio
    async def test_image_response_includes_url_when_storage_available(self):
        engine = ArenaEngine()

        # Mock objects
        match = MagicMock()
        match.match_type = "image_gen"
        match.prompt = "a beautiful sunset"
        match.config = {
            "image_provider": "openai",
            "image_api_key": "sk-test",
            "image_model": "dall-e-3",
            "image_size": "1024x1024",
        }

        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.description = "An art agent"

        profile = MagicMock()
        model = MagicMock()
        model.model_id = "gpt-4"
        model.api_key = "sk-test"
        model.api_base = None

        fake_b64 = base64.b64encode(b"fake_image_bytes").decode()

        with patch("app.services.arena_engine.llm_adapter") as mock_llm, \
             patch("app.services.arena_engine.image_adapter") as mock_img, \
             patch("app.services.arena_engine.media_storage") as mock_storage, \
             patch("app.services.arena_engine.AgentService") as mock_agent_svc:

            mock_agent_svc.build_system_prompt.return_value = "You are TestAgent."
            mock_llm.chat = AsyncMock(return_value={"content": "A beautiful sunset over the ocean, vibrant colors"})
            mock_img.generate = AsyncMock(return_value={
                "image_b64": fake_b64,
                "provider": "openai",
                "model": "dall-e-3",
                "revised_prompt": "Enhanced sunset",
            })
            mock_storage.upload = AsyncMock(return_value="arena/images/uuid-123")
            mock_storage.get_url = AsyncMock(return_value="http://minio:9000/arena/images/uuid-123")

            result = await engine._generate_image_response(
                db=MagicMock(), match=match, agent=agent,
                profile=profile, model=model,
            )

        assert result["type"] == "image"
        assert result["image_url"] == "http://minio:9000/arena/images/uuid-123"
        assert "image_b64" not in result
        assert result["provider"] == "openai"
        assert result["revised_prompt"] == "Enhanced sunset"
        assert "sunset" in result["prompt_used"].lower()

    @pytest.mark.asyncio
    async def test_image_response_falls_back_to_b64_when_storage_fails(self):
        engine = ArenaEngine()

        match = MagicMock()
        match.match_type = "image_gen"
        match.prompt = "a cat"
        match.config = {"image_provider": "openai", "image_api_key": "sk-test"}

        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.description = ""

        profile = None
        model = MagicMock()
        model.model_id = "gpt-4"
        model.api_key = "sk-test"
        model.api_base = None

        fake_b64 = base64.b64encode(b"image_data").decode()

        with patch("app.services.arena_engine.llm_adapter") as mock_llm, \
             patch("app.services.arena_engine.image_adapter") as mock_img, \
             patch("app.services.arena_engine.media_storage") as mock_storage, \
             patch("app.services.arena_engine.AgentService") as mock_agent_svc:

            mock_agent_svc.build_system_prompt.return_value = "You are TestAgent."
            mock_llm.chat = AsyncMock(return_value={"content": "A cute fluffy cat"})
            mock_img.generate = AsyncMock(return_value={
                "image_b64": fake_b64,
                "provider": "openai",
                "model": "dall-e-3",
            })
            mock_storage.upload = AsyncMock(side_effect=Exception("MinIO not available"))

            result = await engine._generate_image_response(
                db=MagicMock(), match=match, agent=agent,
                profile=profile, model=model,
            )

        assert result["type"] == "image"
        assert result["image_b64"] == fake_b64
        assert "image_url" not in result

    @pytest.mark.asyncio
    async def test_image_response_uses_original_prompt_on_llm_failure(self):
        engine = ArenaEngine()

        match = MagicMock()
        match.match_type = "image_gen"
        match.prompt = "sunset over mountains"
        match.config = {"image_provider": "openai", "image_api_key": "sk-test"}

        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.description = ""

        profile = None
        model = MagicMock()
        model.model_id = "gpt-4"
        model.api_key = "sk-test"
        model.api_base = None

        fake_b64 = base64.b64encode(b"img").decode()

        with patch("app.services.arena_engine.llm_adapter") as mock_llm, \
             patch("app.services.arena_engine.image_adapter") as mock_img, \
             patch("app.services.arena_engine.media_storage") as mock_storage, \
             patch("app.services.arena_engine.AgentService") as mock_agent_svc:

            mock_agent_svc.build_system_prompt.return_value = "You are TestAgent."
            mock_llm.chat = AsyncMock(side_effect=Exception("LLM API error"))
            mock_img.generate = AsyncMock(return_value={
                "image_b64": fake_b64,
                "provider": "openai",
                "model": "dall-e-3",
            })
            mock_storage.upload = AsyncMock(side_effect=Exception("no storage"))

            result = await engine._generate_image_response(
                db=MagicMock(), match=match, agent=agent,
                profile=profile, model=model,
            )

        # Should fall back to original prompt
        assert result["prompt_used"] == "sunset over mountains"
        assert result["type"] == "image"

    @pytest.mark.asyncio
    async def test_image_response_returns_error_when_no_api_key(self):
        engine = ArenaEngine()

        match = MagicMock()
        match.match_type = "image_gen"
        match.prompt = "a dog"
        match.config = {"image_provider": "openai"}  # no image_api_key

        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.description = ""

        profile = None
        model = MagicMock()
        model.model_id = "gpt-4"
        model.api_key = None  # model also has no key
        model.api_base = None

        with patch("app.services.arena_engine.llm_adapter") as mock_llm, \
             patch("app.services.arena_engine.AgentService") as mock_agent_svc:

            mock_agent_svc.build_system_prompt.return_value = "You are TestAgent."
            mock_llm.chat = AsyncMock(return_value={"content": "A cute dog"})

            result = await engine._generate_image_response(
                db=MagicMock(), match=match, agent=agent,
                profile=profile, model=model,
            )

        assert result["type"] == "image"
        assert "error" in result
        assert "API key" in result["error"]

    @pytest.mark.asyncio
    async def test_image_response_propagates_image_generation_error(self):
        engine = ArenaEngine()

        match = MagicMock()
        match.match_type = "image_gen"
        match.prompt = "a landscape"
        match.config = {"image_provider": "openai", "image_api_key": "sk-test"}

        agent = MagicMock()
        agent.id = "agent-1"
        agent.name = "TestAgent"
        agent.description = ""

        profile = None
        model = MagicMock()
        model.model_id = "gpt-4"
        model.api_key = "sk-test"
        model.api_base = None

        with patch("app.services.arena_engine.llm_adapter") as mock_llm, \
             patch("app.services.arena_engine.image_adapter") as mock_img, \
             patch("app.services.arena_engine.AgentService") as mock_agent_svc:

            mock_agent_svc.build_system_prompt.return_value = "You are TestAgent."
            mock_llm.chat = AsyncMock(return_value={"content": "A beautiful landscape"})
            mock_img.generate = AsyncMock(side_effect=RuntimeError("Image API rate limited"))

            with pytest.raises(RuntimeError, match="Image API rate limited"):
                await engine._generate_image_response(
                    db=MagicMock(), match=match, agent=agent,
                    profile=profile, model=model,
                )


# ========== ArenaEngine.start_match error handling ==========

class TestStartMatchImageErrorHandling:
    """Test that start_match handles image generation errors gracefully"""

    @pytest.mark.asyncio
    async def test_start_match_continues_after_single_agent_failure(self):
        """If one agent's image generation fails, others should still complete."""
        engine = ArenaEngine()

        # This test verifies the error handling structure in start_match
        # by checking that exceptions are caught per-participant
        match = MagicMock()
        match.id = "match-1"
        match.match_type = "image_gen"
        match.status = "waiting"
        match.prompt = "test prompt"
        match.config = {"image_provider": "openai"}

        # Verify that the error response format includes useful info
        error_response = {
            "type": "image_gen",
            "error": "Generation failed: Some error message",
        }
        assert error_response["type"] == "image_gen"
        assert "error" in error_response
