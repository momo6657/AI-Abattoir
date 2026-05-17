import pytest
from unittest.mock import MagicMock

from app.services.agent_service import AgentService


def _make_agent(name="TestAgent", description="A test agent"):
    agent = MagicMock()
    agent.name = name
    agent.description = description
    return agent


def _make_profile(**kwargs):
    profile = MagicMock()
    profile.persona = kwargs.get("persona")
    profile.personality = kwargs.get("personality")
    profile.speaking_style = kwargs.get("speaking_style")
    profile.background_story = kwargs.get("background_story")
    profile.strengths = kwargs.get("strengths")
    profile.system_prompt = kwargs.get("system_prompt")
    profile.custom_config = kwargs.get("custom_config", {})
    return profile


class TestBuildSystemPrompt:
    def test_build_system_prompt_basic(self):
        agent = _make_agent(name="Alpha", description="A helpful assistant")
        prompt = AgentService.build_system_prompt(agent, profile=None)
        assert "Alpha" in prompt
        assert "A helpful assistant" in prompt

    def test_build_system_prompt_no_description(self):
        agent = _make_agent(name="Beta", description=None)
        prompt = AgentService.build_system_prompt(agent, profile=None)
        assert "Beta" in prompt

    def test_build_system_prompt_full(self):
        agent = _make_agent(name="Gamma")
        profile = _make_profile(
            persona="You are a wise sage",
            personality="calm and thoughtful",
            speaking_style="poetic and metaphorical",
            background_story="Born in the mountains",
            strengths=["wisdom", "patience", "foresight"],
        )
        prompt = AgentService.build_system_prompt(agent, profile)
        assert "Gamma" in prompt
        assert "You are a wise sage" in prompt
        assert "calm and thoughtful" in prompt
        assert "poetic and metaphorical" in prompt
        assert "Born in the mountains" in prompt
        assert "wisdom" in prompt
        assert "patience" in prompt
        assert "foresight" in prompt

    def test_build_system_prompt_custom(self):
        agent = _make_agent(name="Delta")
        profile = _make_profile(system_prompt="You are a custom bot. Follow these rules strictly.")
        prompt = AgentService.build_system_prompt(agent, profile)
        assert prompt == "You are a custom bot. Follow these rules strictly."

    def test_build_system_prompt_partial_profile(self):
        agent = _make_agent(name="Epsilon")
        profile = _make_profile(persona="A scientist", strengths=["analysis"])
        prompt = AgentService.build_system_prompt(agent, profile)
        assert "Epsilon" in prompt
        assert "A scientist" in prompt
        assert "analysis" in prompt
        # Fields not set should not appear
        assert "性格特点" not in prompt
        assert "说话风格" not in prompt
