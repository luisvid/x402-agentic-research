"""Tests for tier config builder."""

import pytest

from src.config import build_engine_config


def test_build_basic_config():
    config = build_engine_config("basic")
    assert config["max_queries"] == 8
    assert config["include_report"] is False
    assert config["include_causal_chain"] is False


def test_build_pro_config():
    config = build_engine_config("pro")
    assert config["max_queries"] == 15
    assert config["include_report"] is True
    assert config["include_causal_chain"] is True


def test_build_deep_config():
    config = build_engine_config("deep")
    assert config["max_queries"] == 25
    assert config["include_report"] is True


def test_invalid_tier_raises():
    with pytest.raises(ValueError, match="Invalid tier"):
        build_engine_config("premium")
