import pytest
from unittest.mock import MagicMock

from app.services.agent_service import AgentService, AGENT_TEMPLATES


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


class TestTemplates:
    def test_all_templates_have_required_fields(self):
        required_keys = {"name", "description", "profile"}
        required_profile_keys = {"persona", "personality", "speaking_style", "background_story", "strengths"}

        for key, tpl in AGENT_TEMPLATES.items():
            for rk in required_keys:
                assert rk in tpl, f"Template '{key}' missing '{rk}'"
            for rpk in required_profile_keys:
                assert rpk in tpl["profile"], f"Template '{key}' profile missing '{rpk}'"
            assert isinstance(tpl["profile"]["strengths"], list), (
                f"Template '{key}' strengths should be a list"
            )

    def test_list_templates_returns_all(self):
        db = MagicMock()
        service = AgentService(db)
        templates = service.list_templates()
        assert len(templates) == len(AGENT_TEMPLATES)
        template_keys = {t["template_key"] for t in templates}
        assert template_keys == set(AGENT_TEMPLATES.keys())

    def test_template_names_non_empty(self):
        for key, tpl in AGENT_TEMPLATES.items():
            assert tpl["name"], f"Template '{key}' has empty name"
            assert tpl["description"], f"Template '{key}' has empty description"
