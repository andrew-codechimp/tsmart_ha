"""Binary Sensor platform for t_smart."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import TSmartConfigEntry
from .entity import TSmartEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        [
            TSmartRelayBinarySensorEntity(coordinator),
            TSmartStatusBinarySensorEntity(coordinator),
        ]
    )


class TSmartRelayBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Relay Binary Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_translation_key = "relay"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._tsmart.device_id}_relay"

    @property
    def is_on(self) -> bool | None:
        """Is the relay on."""
        return self._tsmart.relay


class TSmartStatusBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Status Binary Sensor class."""

    _attr_translation_key = "status"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._tsmart.device_id}_status"

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a problem."""
        return self._tsmart.error_status

    @property
    def extra_state_attributes(self) -> dict[str, bool] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "E01 - Broken sensors": self._tsmart.error_e01,
            "E02 - Overheating": self._tsmart.error_e02,
            "E03 - Dry heating": self._tsmart.error_e03,
            "E04 - Serial Comm ST error": self._tsmart.error_e04,
            "E05 - Serial Comm ESP error": self._tsmart.error_e05,
            "W01 - Bad High Sensor": self._tsmart.error_w01,
            "W02 - Bad Low Sensor": self._tsmart.error_w02,
            "W03 - Long heating": self._tsmart.error_w03,
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
