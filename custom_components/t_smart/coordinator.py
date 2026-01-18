"""DataUpdateCoordinator for thermostats."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.const import (
    CONF_IP_ADDRESS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import (
    UpdateFailed,
    DataUpdateCoordinator,
)

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_TEMPERATURE_MODE,
    TEMPERATURE_MODE_AVERAGE,
)
from .tsmart import TSmart

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 10  # Timeout in seconds for device communication


class DeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """Manages polling for state changes from the device."""

    device: TSmart
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the data update coordinator."""

        self.config_entry = config_entry
        self.device = TSmart(
            config_entry.data[CONF_IP_ADDRESS],
            config_entry.data[CONF_DEVICE_ID],
            config_entry.data[CONF_DEVICE_NAME],
        )
        self._attr_unique_id = self.device.device_id
        self._error_count = 0

        self.temperature_mode = config_entry.data.get(
            CONF_TEMPERATURE_MODE, TEMPERATURE_MODE_AVERAGE
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.device.device_id}",
            update_interval=timedelta(seconds=10),
            config_entry=config_entry,
        )

    async def async_initialize(self) -> None:
        """Initialize the device configuration."""
        try:
            async with asyncio.timeout(TIMEOUT):
                await self.device.async_get_configuration()
            _LOGGER.debug("Device configuration loaded for %s", self.device.name)
        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout loading configuration for device {self.device.name}"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                f"Error loading configuration for device {self.device.name}: {err}"
            ) from err

    async def _async_update_data(self):
        """Update the state of the device."""
        try:
            # Get device status
            async with asyncio.timeout(TIMEOUT):
                await self.device.async_get_status()

        except TimeoutError as err:
            raise UpdateFailed(
                f"Timeout communicating with device {self.device.name}"
            ) from err
        except Exception as err:
            raise UpdateFailed(
                f"Error communicating with device {self.device.name}: {err}"
            ) from err
