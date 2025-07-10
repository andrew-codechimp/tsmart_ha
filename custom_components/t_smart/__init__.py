"""The T-Smart Thermostat integration."""

from __future__ import annotations

from awesomeversion.awesomeversion import AwesomeVersion

from homeassistant.const import __version__ as HA_VERSION  # noqa: N812
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import ConfigEntryNotReady

from .const import (
    DOMAIN,
    COORDINATORS,
    MIN_HA_VERSION,
)
from .coordinator import DeviceDataUpdateCoordinator

import logging

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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][COORDINATORS] = {}

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up T-Smart Thermostat from a config entry."""

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    coordinator = DeviceDataUpdateCoordinator(hass=hass, config_entry=entry)

    hass.data[DOMAIN][COORDINATORS][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    if coordinator.device.request_successful is False:
        raise ConfigEntryNotReady(f"Unable to connect to {coordinator.device.ip}")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN][COORDINATORS].pop(entry.entry_id, None)

    return unload_ok
