"""Tests for app.config env parsing helpers."""
from __future__ import annotations

import importlib

import pytest

import app.config as config_module


def test_int_env_returns_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DUMMY_INT_FOR_TESTS", raising=False)
    assert config_module._int_env("DUMMY_INT_FOR_TESTS", 99) == 99


def test_int_env_parses_valid_value(monkeypatch) -> None:
    monkeypatch.setenv("DUMMY_INT_FOR_TESTS", "5000")
    assert config_module._int_env("DUMMY_INT_FOR_TESTS", 99) == 5000


def test_int_env_enforces_minimum(monkeypatch) -> None:
    monkeypatch.setenv("DUMMY_INT_FOR_TESTS", "10")
    assert config_module._int_env("DUMMY_INT_FOR_TESTS", 99, minimum=100) == 100


def test_int_env_invalid_value_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("DUMMY_INT_FOR_TESTS", "not-a-number")
    assert config_module._int_env("DUMMY_INT_FOR_TESTS", 42) == 42


def test_int_env_empty_string_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("DUMMY_INT_FOR_TESTS", "")
    assert config_module._int_env("DUMMY_INT_FOR_TESTS", 42) == 42


def test_known_paths_resolve() -> None:
    assert config_module.PROJECT_ROOT.exists()
    assert config_module.APP_DIR.exists()
    assert config_module.TEMPLATES_DIR.exists()
    assert config_module.STATIC_DIR.exists()
    assert config_module.RESULTS_DIR.exists()
    assert config_module.PREFERENCES_FILE.name == "job_requirements.md"


def test_search_context_size_invalid_defaults_to_low(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_SEARCH_CONTEXT_SIZE", "extreme")
    try:
        reloaded = importlib.reload(config_module)
        assert reloaded.OPENAI_SEARCH_CONTEXT_SIZE == "low"
    finally:
        monkeypatch.delenv("OPENAI_SEARCH_CONTEXT_SIZE", raising=False)
        importlib.reload(config_module)


def test_search_context_size_high_uppercase(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_SEARCH_CONTEXT_SIZE", "HIGH")
    try:
        reloaded = importlib.reload(config_module)
        assert reloaded.OPENAI_SEARCH_CONTEXT_SIZE == "high"
    finally:
        monkeypatch.delenv("OPENAI_SEARCH_CONTEXT_SIZE", raising=False)
        importlib.reload(config_module)


def test_search_context_size_default_low(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_SEARCH_CONTEXT_SIZE", raising=False)
    reloaded = importlib.reload(config_module)
    assert reloaded.OPENAI_SEARCH_CONTEXT_SIZE == "low"


def test_resolve_model_defaults_when_empty(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "OPENAI_MODEL_OPTIONS", ("a", "b", "c"))
    monkeypatch.setattr(config_module, "OPENAI_MODEL", "b")
    assert config_module.resolve_model(None) == "b"
    assert config_module.resolve_model("") == "b"


def test_resolve_model_accepts_override(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "OPENAI_MODEL_OPTIONS", ("x1", "x2", "x3"))
    monkeypatch.setattr(config_module, "OPENAI_MODEL", "x2")
    assert config_module.resolve_model(" x3 ") == "x3"


def test_resolve_model_unknown_raises(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "OPENAI_MODEL_OPTIONS", ("a", "b", "c"))
    monkeypatch.setattr(config_module, "OPENAI_MODEL", "a")
    with pytest.raises(ValueError, match="Unsupported model"):
        config_module.resolve_model("z")
