"""Sensor platform for t_smart."""

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.const import (
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    COORDINATORS,
    ATTR_TEMPERATURE_LOW,
    TEMPERATURE_MODE_LOW,
    ATTR_TEMPERATURE_HIGH,
    TEMPERATURE_MODE_HIGH,
    ATTR_TEMPERATURE_AVERAGE,
)
from .entity import TSmartCoordinatorEntity

SCAN_INTERVAL = timedelta(seconds=5)


class TSmartSensorEntity(TSmartCoordinatorEntity, SensorEntity):
    """t_smart Sensor class."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    # Inherit name from DeviceInfo, which is obtained from actual device
    _attr_has_entity_name = True
    _attr_name = "Current Temperature"

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][COORDINATORS][config_entry.entry_id]
    async_add_entities([TSmartSensorEntity(coordinator)])
