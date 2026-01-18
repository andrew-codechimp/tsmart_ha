"""The T-Smart Thermostat integration."""

from __future__ import annotations

import logging

from awesomeversion.awesomeversion import AwesomeVersion

from homeassistant.const import (
    Platform,
    __version__ as HA_VERSION,  # noqa: N812
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import ConfigEntryNotReady

from .common import TSmartConfigEntry
from .const import MIN_HA_VERSION
from .coordinator import TSmartCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Integration setup."""

    if AwesomeVersion(HA_VERSION) < AwesomeVersion(MIN_HA_VERSION):  # pragma: no cover
        msg = (
            "This integration requires at least Home Assistant version "
            f" {MIN_HA_VERSION}, you are running version {HA_VERSION}."
            " Please upgrade Home Assistant to continue using this integration."
        )
        _LOGGER.critical(msg)
        return False

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TSmartConfigEntry) -> bool:
    """Set up T-Smart Thermostat from a config entry."""

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    coordinator = TSmartCoordinator(hass=hass, config_entry=entry)
    entry.runtime_data.coordinator = coordinator

    # Get device configuration before first refresh
    await coordinator.async_initialize()
    if coordinator.device.request_successful is False:
        raise ConfigEntryNotReady(f"Unable to connect to {coordinator.device.ip}")

    await coordinator.async_config_entry_first_refresh()
    if coordinator.device.request_successful is False:
        raise ConfigEntryNotReady(f"Unable to connect to {coordinator.device.ip}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: TSmartConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: TSmartConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
