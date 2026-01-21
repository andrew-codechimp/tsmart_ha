"""The T-Smart Thermostat integration."""

from __future__ import annotations

import logging

from awesomeversion.awesomeversion import AwesomeVersion

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    Platform,
    __version__ as HA_VERSION,  # noqa: N812
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import ConfigEntryNotReady

from .common import TSmartConfigEntry, TSmartData
from .const import (
    CONF_DEVICE_NAME,
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    MIN_HA_VERSION,
    TEMPERATURE_MODE_AVERAGE,
)
from .coordinator import TSmartCoordinator
from .tsmart import TSmart

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.SENSOR,
]


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


async def async_migrate_entry(hass: HomeAssistant, entry: TSmartConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Version 1 -> 2: Migrate entity unique IDs
        entity_registry = er.async_get(hass)
        device_id = entry.data.get("device_id")

        if device_id:
            # Migration map: old unique_id -> (platform, new unique_id)
            migrations = [
                (Platform.SENSOR, device_id, f"{device_id}_temperature"),
                (Platform.BINARY_SENSOR, device_id, f"{device_id}_relay"),
            ]

            for platform, old_unique_id, new_unique_id in migrations:
                # Find entity with old unique ID
                entity_id = entity_registry.async_get_entity_id(
                    platform, DOMAIN, old_unique_id
                )
                if entity_id:
                    _LOGGER.info(
                        "Migrating entity %s from unique_id %s to %s",
                        entity_id,
                        old_unique_id,
                        new_unique_id,
                    )
                    entity_registry.async_update_entity(
                        entity_id, new_unique_id=new_unique_id
                    )

        # Update entry version
        hass.config_entries.async_update_entry(entry, version=2)

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: TSmartConfigEntry) -> bool:
    """Set up T-Smart Thermostat from a config entry."""

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    device = TSmart(
        entry.data[CONF_IP_ADDRESS],
        entry.data[CONF_DEVICE_ID],
        entry.data[CONF_DEVICE_NAME],
    )

    temperature_mode = (
        entry.data.get(CONF_TEMPERATURE_MODE, TEMPERATURE_MODE_AVERAGE),
    )

    # Get device configuration before first refresh
    configuration = await device.async_get_configuration()
    if not configuration:
        # Attempt discovery on timeout
        discovered_devices: list[TSmart] = await TSmart.async_discover()

        if not discovered_devices:
            raise ConfigEntryNotReady(
                f"Timeout connecting to device {device.name} on {device.ip}"
            )

        for discovered_device in discovered_devices:
            if device.device_id == entry.data[CONF_DEVICE_ID]:
                new_data = entry.data.copy()
                new_data[CONF_IP_ADDRESS] = discovered_device.ip
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.debug(
                    "%s: Changed IP address to %s",
                    device.device_id,
                    device.ip,
                )
                device.ip = discovered_device.ip
                configuration = await device.async_get_configuration()
                break

    if not configuration:
        raise ConfigEntryNotReady(f"Unable to connect to {device.ip}")

    coordinator = TSmartCoordinator(
        hass=hass, config_entry=entry, device=device, temperature_mode=temperature_mode
    )
    entry.runtime_data = TSmartData(device=device, coordinator=coordinator)

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
