"""DataUpdateCoordinator for thermostats."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import CONF_TEMPERATURE_MODE, DOMAIN, TEMPERATURE_MODE_AVERAGE
from .tsmart import TSmart, TSmartInvalidResponseError, TSmartStatus

_LOGGER = logging.getLogger(__name__)


class TSmartCoordinator(DataUpdateCoordinator[TSmartStatus]):
    """Manages polling for state changes from the device."""

    device: TSmart
    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: TSmart,
    ) -> None:
        """Initialize the data update coordinator."""

        self.device = device
        self._attr_unique_id = self.device.device_id

        self.temperature_mode = config_entry.options.get(
            CONF_TEMPERATURE_MODE, TEMPERATURE_MODE_AVERAGE
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self.device.device_id}",
            update_interval=timedelta(seconds=10),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> TSmartStatus:
        """Update the state of the device."""
        # Get device status
        try:
            status = await self.device.async_get_status()
        except ConnectionRefusedError as err:
            message = f"Connection refused by device {self.device.name}"
            raise UpdateFailed(message) from err
        except TimeoutError as err:
            message = f"Timeout trying to fetch status from {self.device.name}"
            raise UpdateFailed(message) from err
        except TSmartInvalidResponseError as err:
            message = f"Invalid response received from {self.device.name}"
            raise UpdateFailed(message) from err
        return status
