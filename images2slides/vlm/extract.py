"""VLM extraction for infographic region analysis."""

import base64
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from PIL import Image

from ..models import Layout
from ..validator import validate_layout
from .prompt import get_extraction_prompt, get_system_prompt

logger = logging.getLogger(__name__)

VLMProvider = Literal["google", "openai", "anthropic", "openrouter"]


class VLMExtractionError(Exception):
    """Raised when VLM extraction fails."""

    pass


@dataclass
class VLMConfig:
    """Configuration for VLM provider."""

    provider: VLMProvider = "google"
    model: str | None = None
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 16384

    def get_model(self) -> str:
        """Get model name with provider-specific defaults."""
        if self.model:
            return self.model
        defaults = {
            "google": "gemini-3-pro-preview",
            "openai": "gpt-5.2",
            "anthropic": "claude-opus-4-5",
            "openrouter": "qwen/qwen3-vl-235b-a22b-instruct",
        }
        return defaults.get(self.provider, "gemini-3-pro-preview")

    def get_api_key(self) -> str:
        """Get API key from config or environment."""
        if self.api_key:
            return self.api_key
        env_vars = {
            "google": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        env_var = env_vars.get(self.provider, "GOOGLE_API_KEY")
        key = os.environ.get(env_var)
        if not key:
            raise VLMExtractionError(f"API key not found. Set {env_var} environment variable.")
        return key


class VLMClient(Protocol):
    """Protocol for VLM client implementations."""

    def extract_layout(self, image_path: Path) -> dict:
        """Extract layout from image and return raw JSON dict."""
        ...


class GoogleVLMClient:
    """Google Gemini VLM client."""

    def __init__(self, config: VLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy initialization of Google GenAI client."""
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.config.get_api_key())
        return self._client

    def extract_layout(self, image_path: Path) -> dict:
        """Extract layout from image using Google Gemini."""
        from google.genai import types

        client = self._get_client()
        model = self.config.get_model()

        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        # Get actual image dimensions
        with Image.open(image_path) as img:
            width, height = img.size

        prompt = get_extraction_prompt()
        prompt_with_dims = f"{prompt}\n\nNote: This image is {width}x{height} pixels."

        logger.info(f"Calling {model} for image {image_path.name} ({width}x{height})")

        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=image_data, mime_type=mime_type),
                            types.Part.from_text(text=prompt_with_dims),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=get_system_prompt(),
                    temperature=self.config.temperature,
                    max_output_tokens=self.config.max_tokens,
                ),
            )

            response_text = response.text
            return self._parse_json_response(response_text)

        except Exception as e:
            raise VLMExtractionError(f"Google Gemini API error: {e}") from e

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from VLM response, handling markdown code blocks."""
        text = text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```"):
            # Find the end of the opening fence
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Check if response appears truncated (doesn't end with closing brace)
            truncation_hint = ""
            if not text.rstrip().endswith("}"):
                truncation_hint = "\n[Response appears truncated - may need to increase max_tokens or simplify the image]"

            # Show last 200 chars to see where it cut off
            response_preview = text[:300] + "\n...\n" + text[-200:] if len(text) > 500 else text
            raise VLMExtractionError(
                f"Failed to parse JSON response: {e}{truncation_hint}\n"
                f"Response length: {len(text)} chars\n"
                f"Response preview:\n{response_preview}"
            ) from e


class OpenAIVLMClient:
    """OpenAI GPT-4V VLM client."""

    def __init__(self, config: VLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.config.get_api_key())
        return self._client

    def extract_layout(self, image_path: Path) -> dict:
        """Extract layout from image using OpenAI GPT-4V."""
        client = self._get_client()
        model = self.config.get_model()

        # Read and encode image as base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        # Get actual image dimensions
        with Image.open(image_path) as img:
            width, height = img.size

        prompt = get_extraction_prompt()
        prompt_with_dims = f"{prompt}\n\nNote: This image is {width}x{height} pixels."

        logger.info(f"Calling {model} for image {image_path.name} ({width}x{height})")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}",
                                },
                            },
                            {"type": "text", "text": prompt_with_dims},
                        ],
                    },
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            response_text = response.choices[0].message.content
            return self._parse_json_response(response_text)

        except Exception as e:
            raise VLMExtractionError(f"OpenAI API error: {e}") from e

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from VLM response."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise VLMExtractionError(
                f"Failed to parse JSON response: {e}\nResponse: {text[:500]}"
            ) from e


class AnthropicVLMClient:
    """Anthropic Claude VLM client."""

    def __init__(self, config: VLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.config.get_api_key())
        return self._client

    def extract_layout(self, image_path: Path) -> dict:
        """Extract layout from image using Anthropic Claude."""
        client = self._get_client()
        model = self.config.get_model()

        # Read and encode image as base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        # Get actual image dimensions
        with Image.open(image_path) as img:
            width, height = img.size

        prompt = get_extraction_prompt()
        prompt_with_dims = f"{prompt}\n\nNote: This image is {width}x{height} pixels."

        logger.info(f"Calling {model} for image {image_path.name} ({width}x{height})")

        try:
            response = client.messages.create(
                model=model,
                system=get_system_prompt(),
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": image_data,
                                },
                            },
                            {"type": "text", "text": prompt_with_dims},
                        ],
                    }
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            response_text = response.content[0].text
            return self._parse_json_response(response_text)

        except Exception as e:
            raise VLMExtractionError(f"Anthropic API error: {e}") from e

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from VLM response."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise VLMExtractionError(
                f"Failed to parse JSON response: {e}\nResponse: {text[:500]}"
            ) from e


class OpenRouterVLMClient:
    """OpenRouter VLM client (uses OpenAI-compatible API)."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, config: VLMConfig) -> None:
        self.config = config
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client with OpenRouter base URL."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self.config.get_api_key(),
                base_url=self.OPENROUTER_BASE_URL,
            )
        return self._client

    def extract_layout(self, image_path: Path) -> dict:
        """Extract layout from image using OpenRouter."""
        client = self._get_client()
        model = self.config.get_model()

        # Read and encode image as base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # Determine mime type
        suffix = image_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(suffix, "image/png")

        # Get actual image dimensions
        with Image.open(image_path) as img:
            width, height = img.size

        prompt = get_extraction_prompt()
        prompt_with_dims = f"{prompt}\n\nNote: This image is {width}x{height} pixels."

        logger.info(f"Calling OpenRouter {model} for image {image_path.name} ({width}x{height})")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": get_system_prompt()},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{image_data}",
                                },
                            },
                            {"type": "text", "text": prompt_with_dims},
                        ],
                    },
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
            )

            response_text = response.choices[0].message.content
            return self._parse_json_response(response_text)

        except Exception as e:
            raise VLMExtractionError(f"OpenRouter API error: {e}") from e

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from VLM response."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            raise VLMExtractionError(
                f"Failed to parse JSON response: {e}\nResponse: {text[:500]}"
            ) from e


def get_vlm_client(config: VLMConfig) -> VLMClient:
    """Get VLM client for the configured provider."""
    clients = {
        "google": GoogleVLMClient,
        "openai": OpenAIVLMClient,
        "anthropic": AnthropicVLMClient,
        "openrouter": OpenRouterVLMClient,
    }
    client_class = clients.get(config.provider)
    if not client_class:
        raise VLMExtractionError(f"Unknown VLM provider: {config.provider}")
    return client_class(config)


def extract_layout_from_image(
    image_path: str | Path,
    config: VLMConfig | None = None,
) -> Layout:
    """Extract layout from an infographic image using VLM.

    Args:
        image_path: Path to the infographic image.
        config: VLM configuration. Defaults to Google Gemini.

    Returns:
        Validated Layout object.

    Raises:
        VLMExtractionError: If extraction fails.
        LayoutValidationError: If the response fails validation.
    """
    if config is None:
        config = VLMConfig()

    path = Path(image_path)
    if not path.exists():
        raise VLMExtractionError(f"Image not found: {path}")

    client = get_vlm_client(config)
    raw_layout = client.extract_layout(path)

    # Validate and convert to Layout object
    layout = validate_layout(raw_layout)
    logger.info(f"Extracted {len(layout.regions)} regions from {path.name}")

    return layout


def extract_layouts_from_images(
    image_paths: list[str | Path],
    config: VLMConfig | None = None,
) -> list[Layout]:
    """Extract layouts from multiple infographic images.

    Args:
        image_paths: List of paths to infographic images.
        config: VLM configuration. Defaults to Google Gemini.

    Returns:
        List of Layout objects in the same order as input.

    Raises:
        VLMExtractionError: If extraction fails for any image.
    """
    if config is None:
        config = VLMConfig()

    layouts = []
    for i, path in enumerate(image_paths):
        logger.info(f"Processing image {i + 1}/{len(image_paths)}: {path}")
        layout = extract_layout_from_image(path, config)
        layouts.append(layout)

    return layouts
