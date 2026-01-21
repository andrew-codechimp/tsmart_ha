"""Climate platform for t_smart."""

import asyncio
import logging

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp

from .common import TSmartConfigEntry
from .const import (
    ATTR_TEMPERATURE_AVERAGE,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_LOW,
    PRESET_MANUAL,
    PRESET_SMART,
    PRESET_TIMER,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
)
from .entity import TSmartEntity
from .tsmart import TSmartMode

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

PRESET_MAP = {
    PRESET_MANUAL: TSmartMode.MANUAL,
    PRESET_ECO: TSmartMode.ECO,
    PRESET_SMART: TSmartMode.SMART,
    PRESET_TIMER: TSmartMode.TIMER,
    PRESET_AWAY: TSmartMode.TRAVEL,
    PRESET_BOOST: TSmartMode.BOOST,
}

AFTER_SET_SLEEP = 2  # Seconds


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TSmartConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform."""
    coordinator = config_entry.runtime_data.coordinator
    async_add_entities([TSmartClimateEntity(coordinator)])


class TSmartClimateEntity(TSmartEntity, ClimateEntity):
    """t_smart Climate class."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    # Setting the new TURN_ON / TURN_OFF features isn't enough to make stop the
    # warning message about not setting them
    _enable_turn_on_off_backwards_compatibility = False
    _attr_supported_features = (
        ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = list(PRESET_MAP.keys())
    _attr_icon = "mdi:water-boiler"
    _attr_max_temp = 75
    _attr_min_temp = 10
    _attr_target_temperature_step = 5

    # Inherit name from DeviceInfo, which is obtained from actual device
    _attr_name = None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return str(self.device.device_id)

    @property
    def hvac_mode(self):
        """Get the current mode."""
        return HVACMode.HEAT if self.coordinator.data.power else HVACMode.OFF

    @property
    def hvac_action(self):
        """Get the current action."""
        if self.coordinator.data.power:
            if self.coordinator.data.relay:
                return HVACAction.HEATING
            return HVACAction.IDLE
        return HVACAction.OFF

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""

        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return

        await self.device.async_control_set(
            hvac_mode == HVACMode.HEAT,
            PRESET_MAP[self.preset_mode],
            self.target_temperature,
        )

        await asyncio.sleep(AFTER_SET_SLEEP)
        await self.coordinator.async_request_refresh()

    @property
    def current_temperature(self):
        """Get the current temperature."""
        if self.coordinator.temperature_mode == TEMPERATURE_MODE_HIGH:
            return self.coordinator.data.temperature_high

        if self.coordinator.temperature_mode == TEMPERATURE_MODE_LOW:
            return self.coordinator.data.temperature_low

        return self.coordinator.data.temperature_average

    @property
    def target_temperature(self):
        """Get the target temperature."""
        return self.coordinator.data.setpoint

    async def async_set_temperature(self, **kwargs):
        """Set the target temperature."""
        if temperature := kwargs.get(ATTR_TEMPERATURE):
            self._attr_target_temperature = temperature

        hvac_mode = kwargs.get(ATTR_HVAC_MODE, self.hvac_mode)

        if temperature:
            await self.device.async_control_set(
                hvac_mode == HVACMode.HEAT,
                PRESET_MAP[self.preset_mode],
                temperature,
            )
            await asyncio.sleep(AFTER_SET_SLEEP)
            await self.coordinator.async_request_refresh()

        # Write updated temperature to HA state to avoid flapping
        self.async_write_ha_state()

    @property
    def preset_mode(self):
        """Get the preset mode."""
        return next(
            (k for k, v in PRESET_MAP.items() if v == self.coordinator.data.mode), None
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        await self.device.async_control_set(
            self.hvac_mode == HVACMode.HEAT,
            PRESET_MAP[preset_mode],
            self.target_temperature,
        )
        await asyncio.sleep(AFTER_SET_SLEEP)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the immersion heater."""

        # Temperature related attributes
        attrs = {
            ATTR_TEMPERATURE_LOW: display_temp(
                self.hass,
                self.coordinator.data.temperature_low,
                self._attr_temperature_unit,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_HIGH: display_temp(
                self.hass,
                self.coordinator.data.temperature_high,
                self._attr_temperature_unit,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_AVERAGE: display_temp(
                self.hass,
                self.coordinator.data.temperature_average,
                self._attr_temperature_unit,
                PRECISION_TENTHS,
            ),
        }

        super_attrs = super().extra_state_attributes
        if super_attrs:
            attrs.update(super_attrs)
        return attrs
