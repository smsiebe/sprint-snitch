"""AuraRouter ComputeFabric wrapper.

Provides a gracefully-degrading bridge to AuraRouter's ComputeFabric.
When aurarouter is not installed or the config file is missing, the bridge
operates in a disabled state and all execute() calls return None.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class FabricBridge:
    """Thin wrapper around AuraRouter's ComputeFabric with token tracking.

    Parameters
    ----------
    config_path : str | None
        Path to an ``auraconfig.yaml`` file.  ``None`` uses the AuraRouter
        default (``~/.auracore/aurarouter/auraconfig.yaml``).
    """

    def __init__(self, config_path: str | None = None) -> None:
        self._fabric = None
        self._token_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
        }

        try:
            from aurarouter.config import ConfigLoader
            from aurarouter.fabric import ComputeFabric

            config = ConfigLoader(config_path)
            self._fabric = ComputeFabric(config)
            logger.info("AuraRouter ComputeFabric initialised successfully.")
        except (ImportError, FileNotFoundError, Exception) as exc:  # noqa: BLE001
            logger.warning("AuraRouter unavailable (%s). LLM features disabled.", exc)
            self._fabric = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True when the underlying ComputeFabric is ready."""
        return self._fabric is not None

    def execute(
        self,
        prompt: str,
        on_model_tried=None,
    ) -> str | None:
        """Send *prompt* to the ``reasoning`` role and return the response.

        Parameters
        ----------
        prompt : str
            The prompt text to send to the LLM.
        on_model_tried : callable | None
            Optional user callback forwarded after internal token tracking.
            Receives ``(role, model_id, success, elapsed)`` -- the 4-param
            form is always safe.

        Returns
        -------
        str | None
            The model response text, or ``None`` when the fabric is
            unavailable or the call fails.
        """
        if not self.is_available():
            return None

        def _tracking_callback(
            role: str,
            model_id: str,
            success: bool,
            elapsed: float,
            input_tokens: int = 0,
            output_tokens: int = 0,
        ) -> None:
            if success:
                self._token_usage["input_tokens"] += input_tokens
                self._token_usage["output_tokens"] += output_tokens
                self._token_usage["calls"] += 1

            if on_model_tried is not None:
                try:
                    on_model_tried(role, model_id, success, elapsed)
                except TypeError:
                    # Caller's callback may not accept our signature -- swallow.
                    pass

        return self._fabric.execute(
            "reasoning",
            prompt,
            on_model_tried=_tracking_callback,
        )

    def get_token_usage(self) -> dict[str, int]:
        """Return a *copy* of the accumulated token-usage counters."""
        return dict(self._token_usage)

    def reset_token_usage(self) -> None:
        """Zero all token-usage counters."""
        self._token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "calls": 0,
        }


class AuraGridBridge(FabricBridge):
    """Placeholder for future AuraGrid integration via UnifiedRouterService.

    This class is intentionally non-functional.  Instantiating it raises
    ``NotImplementedError`` to signal that the AuraGrid pathway has not
    been implemented yet.
    """

    def __init__(self, **kwargs) -> None:  # noqa: ARG002
        raise NotImplementedError(
            "AuraGrid integration pending -- TODO: use UnifiedRouterService "
            "from aurarouter.auragrid.services"
        )
