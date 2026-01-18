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
    async_add_entities([TSmartSensorEntity(coordinator)])


class TSmartSensorEntity(TSmartCoordinatorEntity, SensorEntity):
    """t_smart Sensor class."""

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
    def native_value(self) -> int:
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
