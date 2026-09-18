"""Helpers compartidos para los tests de concensus (no es un modulo de test:
no coincide con el patron test_*.py de pytest.ini a proposito)."""

from unittest.mock import AsyncMock, MagicMock


def mock_channel_layer():
    """channel_layer falso cuyo group_send es awaitable (async_to_sync lo
    espera con `await`; un MagicMock plano no es awaitable y revienta)."""
    layer = MagicMock()
    layer.group_send = AsyncMock()
    return layer
