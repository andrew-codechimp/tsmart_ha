"""Regression tests for diagnostics without runtime data."""

import pytest
from custom_components.t_smart.diagnostics import async_get_config_entry_diagnostics
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ConfigEntryState.SETUP_RETRY, id="before-setup"),
        pytest.param(ConfigEntryState.NOT_LOADED, id="after-unload"),
    ],
)
async def test_without_runtime_data(
    hass: HomeAssistant,
    state: ConfigEntryState,
) -> None:
    """Return the setup state without accessing missing runtime data."""
    entry = MockConfigEntry(domain="t_smart", state=state)

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "state": state.value
    }
