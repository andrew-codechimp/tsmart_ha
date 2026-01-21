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
from .tsmart import TSmartMode

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
            TSmartErrorBinarySensorEntity(coordinator),
            TSmartWarningBinarySensorEntity(coordinator),
        ]
    )


class TSmartRelayBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Relay Binary Sensor class."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_translation_key = "relay"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_relay"

    @property
    def is_on(self) -> bool | None:
        """Is the relay on."""
        return self.coordinator.data.relay


class TSmartErrorBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Error Binary Sensor class."""

    _attr_translation_key = "error"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_error"

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a problem."""
        return self.coordinator.data.mode == TSmartMode.CRITICAL

    @property
    def extra_state_attributes(self) -> dict[str, bool | int] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "E01 - Broken sensors": self.coordinator.data.e01,
            "E01 - Count": self.coordinator.data.e01_count,
            "E02 - Overheating": self.coordinator.data.e02,
            "E02 - Count": self.coordinator.data.e02_count,
            "E03 - Dry heating": self.coordinator.data.e03,
            "E03 - Count": self.coordinator.data.e03_count,
            "E04 - Serial Comm ST error": self.coordinator.data.e04,
            "E04 - Count": self.coordinator.data.e04_count,
            "E05 - Serial Comm ESP error": self.coordinator.data.e05,
            "E05 - Count": self.coordinator.data.e05_count,
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs


class TSmartWarningBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Warning Binary Sensor class."""

    _attr_translation_key = "warning"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_warning"

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a problem."""
        return self.coordinator.data.mode == TSmartMode.LIMITED

    @property
    def extra_state_attributes(self) -> dict[str, bool | int] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "W01 - Bad High Sensor": self.coordinator.data.w01,
            "W01 - Count": self.coordinator.data.w01_count,
            "W02 - Bad Low Sensor": self.coordinator.data.w02,
            "W02 - Count": self.coordinator.data.w02_count,
            "W03 - Long heating": self.coordinator.data.w03,
            "W03 - Count": self.coordinator.data.w03_count,
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
