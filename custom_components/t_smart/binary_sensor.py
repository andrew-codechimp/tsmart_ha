"""Binary Sensor platform for t_smart."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import TSmartConfigEntry
from .entity import TSmartEntity
from .tsmart import TSmartMode, TSmartStatus

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TSmartBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes T-Smart binary sensor entity."""

    value_fn: Callable[[TSmartStatus], bool | None]
    count_fn: Callable[[TSmartStatus], int] | None = None


BINARY_SENSORS: tuple[TSmartBinarySensorEntityDescription, ...] = (
    # Error sensors
    TSmartBinarySensorEntityDescription(
        key="e01",
        translation_key="e01",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.e01 and status.mode == TSmartMode.CRITICAL,
        count_fn=lambda status: status.e01_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="e02",
        translation_key="e02",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.e02 and status.mode == TSmartMode.CRITICAL,
        count_fn=lambda status: status.e02_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="e03",
        translation_key="e03",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.e03 and status.mode == TSmartMode.CRITICAL,
        count_fn=lambda status: status.e03_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="e04",
        translation_key="e04",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.e04 and status.mode == TSmartMode.CRITICAL,
        count_fn=lambda status: status.e04_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="e05",
        translation_key="e05",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.e05 and status.mode == TSmartMode.CRITICAL,
        count_fn=lambda status: status.e05_count,
    ),
    # Warning sensors
    TSmartBinarySensorEntityDescription(
        key="w01",
        translation_key="w01",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.w01 and status.mode == TSmartMode.LIMITED,
        count_fn=lambda status: status.w01_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="w02",
        translation_key="w02",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.w02 and status.mode == TSmartMode.LIMITED,
        count_fn=lambda status: status.w02_count,
    ),
    TSmartBinarySensorEntityDescription(
        key="w03",
        translation_key="w03",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.w03 and status.mode == TSmartMode.LIMITED,
        count_fn=lambda status: status.w03_count,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    entities: list[BinarySensorEntity] = [
        TSmartRelayBinarySensorEntity(coordinator),
        TSmartErrorBinarySensorEntity(coordinator),
        TSmartWarningBinarySensorEntity(coordinator),
    ]

    entities.extend(
        TSmartBinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
    )

    async_add_entities(entities)


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
        summary: str = ""
        if self.coordinator.data.mode == TSmartMode.CRITICAL:
            if self.coordinator.data.e01:
                summary += "E01 - Broken sensors, "
            if self.coordinator.data.e02:
                summary += "E02 - Overheating, "
            if self.coordinator.data.e03:
                summary += "E03 - Dry heating, "
            if self.coordinator.data.e04:
                summary += "E04 - Serial Comm ST error, "
            if self.coordinator.data.e05:
                summary += "E05 - Serial Comm ESP error, "

            summary = summary.rstrip(", ")
        else:
            summary = "No errors"

        attrs = {
            "Summary": summary,
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
        summary: str = ""
        if self.coordinator.data.mode == TSmartMode.LIMITED:
            if self.coordinator.data.e01:
                summary += "W01 - Bad High Sensor, "
            if self.coordinator.data.e02:
                summary += "W01 - Count, "
            if self.coordinator.data.e03:
                summary += "W03 - Long heating, "

            summary = summary.rstrip(", ")
        else:
            summary = "No warnings"

        attrs = {
            "Summary": summary,
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


class TSmartBinarySensorEntity(TSmartEntity, BinarySensorEntity):
    """t_smart Binary Sensor class."""

    entity_description: TSmartBinarySensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: TSmartBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_{self.entity_description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the state of the binary sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return the state attributes of the sensor."""
        if self.entity_description.count_fn is None:
            return super().extra_state_attributes

        attrs = {"count": self.entity_description.count_fn(self.coordinator.data)}

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
