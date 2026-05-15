"""
LLM Model Factory — supports OpenAI and Anthropic providers.

Provider is selected at call time via the `endpoint` parameter.
Add new providers by implementing `_create_<provider>_model()` and
registering it in `create_model()`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

load_dotenv()


class ModelConfigurationError(Exception):
    pass


class ModelNotFoundError(Exception):
    pass


class ModelFactory:
    """Factory for creating LangChain chat models across providers."""

    @staticmethod
    def create_model(
        endpoint: str = "openai",
        model_name: str = "gpt-4o",
        temperature: float = 0.2,
        max_retries: int = 3,
        timeout: int = 120,
    ) -> ChatOpenAI | ChatAnthropic:
        if endpoint == "openai":
            return ModelFactory._create_openai_model(model_name, temperature, max_retries, timeout)
        elif endpoint == "anthropic":
            return ModelFactory._create_anthropic_model(model_name, temperature, max_retries, timeout)
        else:
            raise ValueError(f"Unsupported endpoint: {endpoint}. Supported: openai, anthropic")

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
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            "anthropic": ["claude-sonnet-4-6", "claude-haiku-4-5", "claude-opus-4-7"],
        }

    @staticmethod
    def validate_environment(endpoint: str) -> tuple[bool, list[str]]:
        missing_vars: list[str] = []
        if endpoint == "openai":
            if not os.environ.get("OPENAI_API_KEY"):
                missing_vars.append("OPENAI_API_KEY")
        elif endpoint == "anthropic":
            if not os.environ.get("ANTHROPIC_API_KEY"):
                missing_vars.append("ANTHROPIC_API_KEY")
        return len(missing_vars) == 0, missing_vars


def create_model(
    endpoint: str = "openai", model_name: str = "gpt-4o", **kwargs
) -> ChatOpenAI | ChatAnthropic:
    return ModelFactory.create_model(endpoint, model_name, **kwargs)
