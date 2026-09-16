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
from homeassistant.helpers.temperature import display_temp

from .common import TSmartConfigEntry
from .const import (
    ATTR_TEMPERATURE_AVERAGE,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_LOW,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from .entity import TSmartEntity
from .tsmart import TSmartSmartState

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities(
        [
            TSmartTemperatureSensorEntity(coordinator),
            TSmartSmartStateSensorEntity(coordinator),
        ]
    )


class TSmartTemperatureSensorEntity(TSmartEntity, SensorEntity):
    """t_smart Temperature Sensor class."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_translation_key = "current_temperature"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_temperature"

    @property
    def native_value(self) -> float | None:
        """Return the value reported by the sensor."""
        if self.coordinator.temperature_mode == TEMPERATURE_MODE_HIGH:
            new_value = self.coordinator.data.temperature_high
        elif self.coordinator.temperature_mode == TEMPERATURE_MODE_LOW:
            new_value = self.coordinator.data.temperature_low
        else:
            new_value = self.coordinator.data.temperature_average

        return display_temp(
            self.hass,
            new_value,
            self._attr_native_unit_of_measurement,
            PRECISION_TENTHS,
        )

    @property
    def extra_state_attributes(self) -> dict[str, float | None] | None:
        """Return the state attributes of the sensor."""

        # Temperature related attributes
        attrs = {
            ATTR_TEMPERATURE_LOW: display_temp(
                self.hass,
                self.coordinator.data.temperature_low,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_HIGH: display_temp(
                self.hass,
                self.coordinator.data.temperature_high,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_AVERAGE: display_temp(
                self.hass,
                self.coordinator.data.temperature_average,
                self._attr_native_unit_of_measurement,
                PRECISION_TENTHS,
            ),
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs


class TSmartSmartStateSensorEntity(TSmartEntity, SensorEntity):
    """t_smart Smart State Sensor class."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "smart_state"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.device.device_id}_smart_state"

    @property
    def native_value(self) -> str | None:
        """Return the smart state reported by the device."""
        smart_state = self.coordinator.data.smart_state
        if smart_state is TSmartSmartState.UNKNOWN:
            return None
        return smart_state.name.lower()
