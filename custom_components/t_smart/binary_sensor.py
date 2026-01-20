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
        return f"{self._tsmart.device_id}_relay"

    @property
    def is_on(self) -> bool | None:
        """Is the relay on."""
        return self._tsmart.relay


class TSmartErrorBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Error Binary Sensor class."""

    _attr_translation_key = "error"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._tsmart.device_id}_error"

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a problem."""
        return self._tsmart.mode == TSmartMode.CRITICAL

    @property
    def extra_state_attributes(self) -> dict[str, bool | int] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "E01 - Broken sensors": self._tsmart.error_e01,
            "E01 - Count": self._tsmart.error_e01_count,
            "E02 - Overheating": self._tsmart.error_e02,
            "E02 - Count": self._tsmart.error_e02_count,
            "E03 - Dry heating": self._tsmart.error_e03,
            "E03 - Count": self._tsmart.error_e03_count,
            "E04 - Serial Comm ST error": self._tsmart.error_e04,
            "E04 - Count": self._tsmart.error_e04_count,
            "E05 - Serial Comm ESP error": self._tsmart.error_e05,
            "E05 - Count": self._tsmart.error_e05_count,
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
        return f"{self._tsmart.device_id}_warning"

    @property
    def is_on(self) -> bool | None:
        """Return true if there is a problem."""
        return self._tsmart.mode == TSmartMode.LIMITED

    @property
    def extra_state_attributes(self) -> dict[str, bool | int] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "W01 - Bad High Sensor": self._tsmart.warning_w01,
            "W01 - Count": self._tsmart.warning_w01_count,
            "W02 - Bad Low Sensor": self._tsmart.warning_w02,
            "W02 - Count": self._tsmart.warning_w02_count,
            "W03 - Long heating": self._tsmart.warning_w03,
            "W03 - Count": self._tsmart.warning_w03_count,
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
