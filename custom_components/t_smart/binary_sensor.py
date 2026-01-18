"""Binary Sensor platform for t_smart."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import TSmartConfigEntry
from .entity import TSmartCoordinatorEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities([TSmartBinarySensorEntity(coordinator)])


class TSmartBinarySensorEntity(TSmartCoordinatorEntity, BinarySensorEntity):
    """t_smart Binary Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.POWER

    # Inherit name from DeviceInfo, which is obtained from actual device
    _attr_has_entity_name = True
    _attr_name = "Relay"

    @property
    def is_on(self):
        """Is the relay on."""
        return self._tsmart.relay
