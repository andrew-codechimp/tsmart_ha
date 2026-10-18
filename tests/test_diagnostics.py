"""Regression tests for diagnostics without runtime data."""

from unittest import IsolatedAsyncioTestCase
from unittest.mock import Mock

from custom_components.t_smart.diagnostics import async_get_config_entry_diagnostics

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant


class TestDiagnostics(IsolatedAsyncioTestCase):
    """Check diagnostics before setup and after runtime data is removed."""

    async def test_before_setup(self) -> None:
        """Return the setup failure state without accessing runtime data."""
        entry = Mock(spec=ConfigEntry, state=ConfigEntryState.SETUP_RETRY)

        result = await async_get_config_entry_diagnostics(
            Mock(spec=HomeAssistant), entry
        )

        assert result == {"state": ConfigEntryState.SETUP_RETRY.value}

    async def test_after_unload(self) -> None:
        """Return the unloaded state after runtime data is deleted."""
        entry = Mock(spec=ConfigEntry, state=ConfigEntryState.NOT_LOADED)
        entry.runtime_data = object()
        del entry.runtime_data

        result = await async_get_config_entry_diagnostics(
            Mock(spec=HomeAssistant), entry
        )

        assert result == {"state": ConfigEntryState.NOT_LOADED.value}
