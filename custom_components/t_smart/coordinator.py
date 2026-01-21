"""DataUpdateCoordinator for thermostats."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN
from .tsmart import TSmart, TSmartStatus

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
        temperature_mode: str,
    ) -> None:
        """Initialize the data update coordinator."""

        self.device = device
        self._attr_unique_id = self.device.device_id

        self.temperature_mode = temperature_mode

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
        status = await self.device.async_get_status()
        if not status:
            raise UpdateFailed(f"Unsuccessful request to device {self.device.name}")
        return status
