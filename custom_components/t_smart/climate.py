import logging

from homeassistant.const import (
    UnitOfTemperature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    HVACMode,
    ClimateEntityFeature,
    HVACAction,
)
from homeassistant.const import (
    UnitOfTemperature,
    PRECISION_TENTHS,
)
from .tsmart import TSmartMode
from .const import (
    DOMAIN,
    PRESET_MANUAL,
    PRESET_SMART,
    PRESET_TIMER,
    COORDINATORS,
    ATTR_TEMPERATURE_LOW,
    ATTR_TEMPERATURE_HIGH,
    ATTR_TEMPERATURE_AVERAGE,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
    TEMPERATURE_MODE_AVERAGE,
)

from .entity import TSmartCoordinatorEntity

from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)

PRESET_MAP = {
    PRESET_MANUAL: TSmartMode.MANUAL,
    PRESET_ECO: TSmartMode.ECO,
    PRESET_SMART: TSmartMode.SMART,
    PRESET_TIMER: TSmartMode.TIMER,
    PRESET_AWAY: TSmartMode.TRAVEL,
    PRESET_BOOST: TSmartMode.BOOST,
}


class TSmartClimateEntity(TSmartCoordinatorEntity, ClimateEntity):
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
    _attr_max_temp = 70
    _attr_min_temp = 15
    _attr_target_temperature_step = 5

    # Inherit name from DeviceInfo, which is obtained from actual device
    _attr_has_entity_name = True
    _attr_name = None

    async def async_update(self):
        await self._tsmart._async_get_status()

    @property
    def hvac_mode(self):
        return HVACMode.HEAT if self._tsmart.power else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode):
        await self._tsmart.async_control_set(
            hvac_mode == HVACMode.HEAT,
            PRESET_MAP[self.preset_mode],
            self.target_temperature,
        )
        await self.coordinator.async_request_refresh()

    @property
    def hvac_action(self):
        if self._tsmart.power:
            if self._tsmart.relay:
                return HVACAction.HEATING
            else:
                return HVACAction.IDLE
        return HVACAction.OFF

    @property
    def current_temperature(self):
        if self.coordinator.temperature_mode == TEMPERATURE_MODE_HIGH:
            return self._tsmart.temperature_high

        if self.coordinator.temperature_mode == TEMPERATURE_MODE_LOW:
            return self._tsmart.temperature_low

        return self._tsmart.temperature_average

    @property
    def target_temperature(self):
        return self._tsmart.setpoint

    async def async_set_temperature(self, temperature, **kwargs):
        await self._tsmart.async_control_set(
            self.hvac_mode == HVACMode.HEAT, PRESET_MAP[self.preset_mode], temperature
        )
        await self.coordinator.async_request_refresh()

    def _climate_preset(self, tsmart_mode):
        return next((k for k, v in PRESET_MAP.items() if v == tsmart_mode), None)

    @property
    def preset_mode(self):
        return self._climate_preset(self._tsmart.mode)

    async def async_set_preset_mode(self, preset_mode):
        await self._tsmart.async_control_set(
            self.hvac_mode == HVACMode.HEAT,
            PRESET_MAP[preset_mode],
            self.target_temperature,
        )
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return the state attributes of the battery type."""

        # Temperature related attributes
        attrs = {
            ATTR_TEMPERATURE_LOW: show_temp(
                self.hass,
                self._tsmart.temperature_low,
                self._attr_temperature_unit,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_HIGH: show_temp(
                self.hass,
                self._tsmart.temperature_high,
                self._attr_temperature_unit,
                PRECISION_TENTHS,
            ),
            ATTR_TEMPERATURE_AVERAGE: show_temp(
                self.hass,
                self._tsmart.temperature_average,
                self._attr_temperature_unit,
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
    coordinator = hass.data[DOMAIN][COORDINATORS][config_entry.entry_id]
    async_add_entities([TSmartClimateEntity(coordinator)])
