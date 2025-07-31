"""DataUpdateCoordinator for thermostats."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    TEMPERATURE_MODE_AVERAGE,
)
from .tsmart import TSmart

_LOGGER = logging.getLogger(__name__)


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

    async def _async_update_data(self):
        """Update the state of the device."""
        await self.device.async_get_status()
