"""Tests for VLM module."""

import json

import pytest

from images2slides.vlm import VLMConfig, get_extraction_prompt, get_system_prompt
from images2slides.vlm.extract import (
    AnthropicVLMClient,
    GoogleVLMClient,
    OpenAIVLMClient,
    OpenRouterVLMClient,
    VLMExtractionError,
    get_vlm_client,
)


class TestVLMConfig:
    """Tests for VLMConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = VLMConfig()
        assert config.provider == "google"
        assert config.model is None
        assert config.api_key is None
        assert config.temperature == 0.1
        assert config.max_tokens == 16384

    def test_google_default_model(self) -> None:
        """Test Google provider default model."""
        config = VLMConfig(provider="google")
        assert config.get_model() == "gemini-3-pro-preview"

    def test_openai_default_model(self) -> None:
        """Test OpenAI provider default model."""
        config = VLMConfig(provider="openai")
        assert config.get_model() == "gpt-5.2"

    def test_anthropic_default_model(self) -> None:
        """Test Anthropic provider default model."""
        config = VLMConfig(provider="anthropic")
        assert config.get_model() == "claude-opus-4-5"

    def test_openrouter_default_model(self) -> None:
        """Test OpenRouter provider default model."""
        config = VLMConfig(provider="openrouter")
        assert config.get_model() == "qwen/qwen3-vl-235b-a22b-instruct"

    def test_custom_model(self) -> None:
        """Test custom model override."""
        config = VLMConfig(provider="google", model="gemini-1.5-pro")
        assert config.get_model() == "gemini-1.5-pro"

    def test_api_key_from_config(self) -> None:
        """Test API key from config."""
        config = VLMConfig(api_key="test-key")
        assert config.get_api_key() == "test-key"

    def test_api_key_missing_raises(self, monkeypatch) -> None:
        """Test missing API key raises error."""
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        config = VLMConfig(provider="google")
        with pytest.raises(VLMExtractionError, match="API key not found"):
            config.get_api_key()


class TestGetVLMClient:
    """Tests for get_vlm_client function."""

    def test_google_client(self) -> None:
        """Test getting Google client."""
        config = VLMConfig(provider="google")
        client = get_vlm_client(config)
        assert isinstance(client, GoogleVLMClient)

    def test_openai_client(self) -> None:
        """Test getting OpenAI client."""
        config = VLMConfig(provider="openai")
        client = get_vlm_client(config)
        assert isinstance(client, OpenAIVLMClient)

    def test_anthropic_client(self) -> None:
        """Test getting Anthropic client."""
        config = VLMConfig(provider="anthropic")
        client = get_vlm_client(config)
        assert isinstance(client, AnthropicVLMClient)

    def test_openrouter_client(self) -> None:
        """Test getting OpenRouter client."""
        config = VLMConfig(provider="openrouter")
        client = get_vlm_client(config)
        assert isinstance(client, OpenRouterVLMClient)


class TestPrompts:
    """Tests for VLM prompts."""

    def test_system_prompt_not_empty(self) -> None:
        """Test system prompt is not empty."""
        prompt = get_system_prompt()
        assert len(prompt) > 100
        assert "infographic" in prompt.lower()

    def test_extraction_prompt_not_empty(self) -> None:
        """Test extraction prompt is not empty."""
        prompt = get_extraction_prompt()
        assert len(prompt) > 200
        assert "image_px" in prompt
        assert "regions" in prompt
        assert "bbox_px" in prompt

    def test_extraction_prompt_has_json_schema(self) -> None:
        """Test extraction prompt contains JSON schema."""
        prompt = get_extraction_prompt()
        assert '"type": "text" | "image"' in prompt
        assert '"confidence"' in prompt


class TestJSONParsing:
    """Tests for JSON response parsing."""

    def test_parse_clean_json(self) -> None:
        """Test parsing clean JSON."""
        config = VLMConfig(api_key="test")
        client = GoogleVLMClient(config)

        json_str = json.dumps({
            "image_px": {"width": 800, "height": 600},
            "regions": []
        })
        result = client._parse_json_response(json_str)
        assert result["image_px"]["width"] == 800

    def test_parse_json_with_markdown(self) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""
        config = VLMConfig(api_key="test")
        client = GoogleVLMClient(config)

        json_str = """```json
{
    "image_px": {"width": 800, "height": 600},
    "regions": []
}
```"""
        result = client._parse_json_response(json_str)
        assert result["image_px"]["width"] == 800

    def test_parse_json_with_bare_fence(self) -> None:
        """Test parsing JSON with bare markdown fence."""
        config = VLMConfig(api_key="test")
        client = GoogleVLMClient(config)

        json_str = """```
{
    "image_px": {"width": 1024, "height": 768},
    "regions": []
}
```"""
        result = client._parse_json_response(json_str)
        assert result["image_px"]["width"] == 1024

    def test_parse_invalid_json_raises(self) -> None:
        """Test parsing invalid JSON raises error."""
        config = VLMConfig(api_key="test")
        client = GoogleVLMClient(config)

        with pytest.raises(VLMExtractionError, match="Failed to parse JSON"):
            client._parse_json_response("not valid json at all")

    def test_parse_extracts_embedded_json(self) -> None:
        """Test extracting JSON from surrounding text."""
        config = VLMConfig(api_key="test")
        client = GoogleVLMClient(config)

        response = """Here is the analysis:
{
    "image_px": {"width": 640, "height": 480},
    "regions": []
}
Some trailing text."""
        result = client._parse_json_response(response)
        assert result["image_px"]["width"] == 640
