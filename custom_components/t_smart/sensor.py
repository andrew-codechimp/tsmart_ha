"""Sensor platform for t_smart."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp as show_temp

from .common import TSmartConfigEntry
from .const import (
    ATTR_TEMPERATURE_AVERAGE,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_LOW,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from .entity import TSmartCoordinatorEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        [
            TSmartTemperatureSensorEntity(coordinator),
            TSmartStatusSensorEntity(coordinator),
        ]
    )


class TSmartTemperatureSensorEntity(TSmartCoordinatorEntity, SensorEntity):
    """t_smart Temperature Sensor class."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_has_entity_name = True
    _attr_translation_key = "current_temperature"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._tsmart.device_id}_temperature"

    @property
    def native_value(self) -> int | None:
        """Return the value reported by the sensor."""
        if self.coordinator.temperature_mode == TEMPERATURE_MODE_HIGH:
            new_value = self._tsmart.temperature_high
        elif self.coordinator.temperature_mode == TEMPERATURE_MODE_LOW:
            new_value = self._tsmart.temperature_low
        else:
            new_value = self._tsmart.temperature_average

        return show_temp(
            self.hass,
            new_value,
            self._attr_native_unit_of_measurement,
            PRECISION_TENTHS,
        )

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the sensor."""

        # Temperature related attributes
        attrs = {
            ATTR_TEMPERATURE_LOW: show_temp(
                self.hass,
                self._tsmart.temperature_low,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_HIGH: show_temp(
                self.hass,
                self._tsmart.temperature_high,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_AVERAGE: show_temp(
                self.hass,
                self._tsmart.temperature_average,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs


class TSmartStatusSensorEntity(TSmartCoordinatorEntity, SensorEntity):
    """t_smart Status Sensor class."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self._tsmart.device_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return the status of the device."""
        if self._tsmart.error_status is None:
            return None
        return "problem" if self._tsmart.error_status else "ok"

    @property
    def extra_state_attributes(self) -> dict[str, bool] | None:
        """Return the state attributes of the sensor."""
        attrs = {
            "E01 - Broken sensors": self._tsmart.error_e01,
            "E02 - Overheating": self._tsmart.error_e02,
            "E03 - Dry heating": self._tsmart.error_e03,
            "E04 - Serial Comm ST": self._tsmart.error_e04,
            "E05 - Serial Comm ESP": self._tsmart.error_e05,
            "W01 - Bad High Sensor": self._tsmart.error_w01,
            "W02 - Bad Low Sensor": self._tsmart.error_w02,
            "W03 - Long heating": self._tsmart.error_w03,
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
