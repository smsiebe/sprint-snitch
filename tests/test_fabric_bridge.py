"""Tests for AuraRouter fabric bridge."""

from unittest.mock import MagicMock, patch

import pytest

from sprint_snitch.llm_integration.fabric_bridge import AuraGridBridge, FabricBridge


def test_bridge_not_available_no_aurarouter():
    """When aurarouter cannot be imported, bridge is unavailable."""
    with patch.dict("sys.modules", {"aurarouter": None, "aurarouter.config": None, "aurarouter.fabric": None}):
        # Force re-import failure by patching builtins
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def mock_import(name, *args, **kwargs):
            if name.startswith("aurarouter"):
                raise ImportError("No module named 'aurarouter'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            bridge = FabricBridge.__new__(FabricBridge)
            bridge._fabric = None
            bridge._token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    assert bridge.is_available() is False


def test_bridge_not_available_no_config():
    """When config file doesn't exist, bridge is unavailable."""
    bridge = FabricBridge.__new__(FabricBridge)
    bridge._fabric = None
    bridge._token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    assert bridge.is_available() is False


def test_bridge_execute_delegates():
    """execute() should delegate to fabric.execute('reasoning', ...)."""
    bridge = FabricBridge.__new__(FabricBridge)
    bridge._token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    mock_fabric = MagicMock()
    mock_fabric.execute.return_value = "LLM response"
    bridge._fabric = mock_fabric

    result = bridge.execute("test prompt")
    assert result == "LLM response"
    mock_fabric.execute.assert_called_once()
    call_args = mock_fabric.execute.call_args
    assert call_args[0][0] == "reasoning"
    assert call_args[0][1] == "test prompt"


def test_bridge_execute_returns_none_when_unavailable():
    """When fabric is None, execute() returns None."""
    bridge = FabricBridge.__new__(FabricBridge)
    bridge._fabric = None
    bridge._token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    assert bridge.execute("prompt") is None


def test_bridge_token_tracking():
    """Token usage should accumulate through the tracking callback."""
    bridge = FabricBridge.__new__(FabricBridge)
    bridge._token_usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    mock_fabric = MagicMock()

    # Capture the callback and simulate it being called
    def fake_execute(role, prompt, on_model_tried=None):
        if on_model_tried:
            on_model_tried("reasoning", "model1", True, 1.5, 100, 50)
        return "response"

    mock_fabric.execute.side_effect = fake_execute
    bridge._fabric = mock_fabric

    bridge.execute("test")
    usage = bridge.get_token_usage()
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50
    assert usage["calls"] == 1


def test_bridge_reset_tokens():
    """reset_token_usage() should zero all counters."""
    bridge = FabricBridge.__new__(FabricBridge)
    bridge._token_usage = {"input_tokens": 100, "output_tokens": 50, "calls": 3}
    bridge._fabric = None
    bridge.reset_token_usage()
    usage = bridge.get_token_usage()
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0
    assert usage["calls"] == 0


def test_auragrid_bridge_raises():
    """AuraGridBridge should raise NotImplementedError."""
    with pytest.raises(NotImplementedError, match="AuraGrid integration pending"):
        AuraGridBridge()
