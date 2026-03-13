"""
Model Factory for GEIA OpenAI-Compatible API Integration.

Copied from parent project, unchanged — provides LangChain Chat model creation
via GEIA, OpenAI, or Anthropic endpoints.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

load_dotenv()


class ModelConfigurationError(Exception):
    pass


class GEIAConnectionError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class ModelFactory:
    """Factory class for creating AI models with GEIA routing support."""

    @staticmethod
    def create_model(
        endpoint: str = "geia",
        model_name: str = "vertex_ai/gemini-2.5-pro",
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout: int = 120,
    ) -> ChatOpenAI | ChatAnthropic:
        if endpoint == "geia":
            return ModelFactory._create_geia_model(model_name, temperature, max_retries, timeout)
        elif endpoint == "openai":
            return ModelFactory._create_openai_model(model_name, temperature, max_retries, timeout)
        elif endpoint == "anthropic":
            return ModelFactory._create_anthropic_model(model_name, temperature, max_retries, timeout)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}. Supported: geia, openai, anthropic")

    @staticmethod
    def _create_geia_model(model_name: str, temperature: float, max_retries: int, timeout: int) -> ChatOpenAI:
        api_key = os.environ.get("GEIA_API_KEY")
        if not api_key:
            raise ModelConfigurationError("GEIA_API_KEY environment variable is required for GEIA endpoint.")

        base_url = os.environ.get("GEIA_API_BASE", "https://api.saia.ai/").strip()
        if not base_url.endswith("/"):
            base_url += "/"

        if not ModelFactory._is_valid_geia_model(model_name):
            raise ModelNotFoundError(f"Invalid GEIA model name: {model_name}. Must be in format 'provider/model-name'.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    @staticmethod
    def _create_openai_model(model_name: str, temperature: float, max_retries: int, timeout: int) -> ChatOpenAI:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ModelConfigurationError("OPENAI_API_KEY environment variable is required.")

        return ChatOpenAI(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    @staticmethod
    def _create_anthropic_model(
        model_name: str, temperature: float, max_retries: int, timeout: int
    ) -> ChatAnthropic:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ModelConfigurationError("ANTHROPIC_API_KEY environment variable is required.")

        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    @staticmethod
    def get_available_models() -> dict:
        return {
            "geia": {
                "vertex_ai": ["vertex_ai/gemini-2.5-pro", "vertex_ai/gemini-1.5-pro", "vertex_ai/gemini-1.5-flash"],
                "openai": ["openai/gpt-4o", "openai/gpt-4o-mini"],
                "anthropic": ["anthropic/claude-3-5-sonnet", "anthropic/claude-3-haiku"],
            },
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        }

    @staticmethod
    def _is_valid_geia_model(model_name: str) -> bool:
        if not model_name or "/" not in model_name:
            return False
        provider, model = model_name.split("/", 1)
        return provider in ["vertex_ai", "openai", "anthropic"] and len(model) > 0

    @staticmethod
    def validate_environment(endpoint: str) -> tuple[bool, list[str]]:
        missing_vars: list[str] = []
        if endpoint == "geia":
            if not os.environ.get("GEIA_API_KEY"):
                missing_vars.append("GEIA_API_KEY")
        elif endpoint == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                missing_vars.append("OPENAI_API_KEY")
        elif endpoint == "anthropic":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                missing_vars.append("ANTHROPIC_API_KEY")
        return len(missing_vars) == 0, missing_vars


def create_model(
    endpoint: str = "geia", model_name: str = "vertex_ai/gemini-2.5-pro", **kwargs
) -> ChatOpenAI | ChatAnthropic:
    return ModelFactory.create_model(endpoint, model_name, **kwargs)
