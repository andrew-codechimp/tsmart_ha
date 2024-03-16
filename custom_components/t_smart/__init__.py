"""The T-Smart Thermostat integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DEVICE_IDS,
    DATA_DISCOVERY_SERVICE,
)
from .discovery import DiscoveryService

import logging

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up T-Smart Thermostat from a config entry."""

    # hass.data.setdefault(DOMAIN, {}).setdefault(DEVICE_IDS, set())
    # tsmart_discovery = DiscoveryService(hass)
    # hass.data[DATA_DISCOVERY_SERVICE] = tsmart_discovery
    # await tsmart_discovery.async_discover_devices()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.pop(DOMAIN, None)

    return unload_ok
