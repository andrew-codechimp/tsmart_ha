"""Button platform for t_smart."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import TSmartConfigEntry
from .entity import TSmartEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities([TSmartRestartButtonEntity(coordinator)])


class TSmartRestartButtonEntity(TSmartEntity, ButtonEntity):
    """t_smart Restart Button class."""

    _attr_has_entity_name = True
    _attr_translation_key = "restart"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:restart"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_restart"

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Restart button pressed for %s", self.device.name)
        await self.device.async_restart(1000)
