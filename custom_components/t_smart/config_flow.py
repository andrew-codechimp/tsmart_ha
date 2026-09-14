"""Config flow for T-Smart Thermostat integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DEVICE_NAME,
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    TEMPERATURE_MODE_AVERAGE,
    TEMPERATURE_MODES,
)
from .tsmart import DiscoveredDevice, TSmart, TSmartConfiguration

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({vol.Required(CONF_IP_ADDRESS): str})

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_TEMPERATURE_MODE,
            default=TEMPERATURE_MODE_AVERAGE,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=TEMPERATURE_MODES,
                translation_key="temperature_mode",
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
        ),
    }
)

CONFIG_VERSION = 3


async def _check_connection(
    ip_address: str,
) -> tuple[dict[str, str], TSmartConfiguration | None]:
    """Check connection to the TSmart thermostat."""

    device = TSmart(ip_address=ip_address)

    try:
        configuration = await device.async_get_configuration()
    except TimeoutError:
        return {"base": "no_thermostat_found"}, None

    return {}, configuration


def _step_user_data_schema(device: DiscoveredDevice | None = None) -> vol.Schema:
    """Generate the user step schema."""
    ip_address = vol.Required(CONF_IP_ADDRESS)
    if device:
        ip_address.description = {"suggested_value": device.ip_address}

    return vol.Schema({ip_address: str})


STEP_USER_DATA_SCHEMA = _step_user_data_schema()


class TSmartConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for TSmart Thermostat."""

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize an instance of the TSmart config flow."""
        self.data_schema = STEP_USER_DATA_SCHEMA

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def _discover(self) -> DiscoveredDevice | None:
        """Discover an unconfigured TSmart thermostat."""
        devices: list[DiscoveredDevice] = await TSmart.async_discover()

        for device in devices:
            existing_entries = [
                entry
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id == device.device_id
            ]
            if existing_entries:
                _LOGGER.debug(
                    "%s: Already setup, skipping new discovery",
                    device.device_id,
                )
                continue

            _LOGGER.debug("Discovered thermostat: %s", device)

            # update with suggested values from discovery
            self.data_schema = _step_user_data_schema(device)
            return device

        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        device = None

        if user_input is not None:
            # Try to connect and do any error checking here
            errors, configuration = await _check_connection(user_input[CONF_IP_ADDRESS])

            # Save instance
            if not errors and configuration:
                await self.async_set_unique_id(configuration.device_id)
                self._abort_if_unique_id_configured()

                user_input[CONF_DEVICE_ID] = configuration.device_id
                user_input[CONF_DEVICE_NAME] = configuration.name
                return self.async_create_entry(
                    title=configuration.device_id, data=user_input
                )
        else:
            # See if we can discover an unconfigured thermostat
            device = await self._discover()
            if device:
                user_input = {}
                user_input[CONF_IP_ADDRESS] = device.ip_address
                user_input[CONF_DEVICE_ID] = device.device_id
                user_input[CONF_DEVICE_NAME] = device.name
                user_input[CONF_TEMPERATURE_MODE] = TEMPERATURE_MODE_AVERAGE
                errors, configuration = await _check_connection(
                    user_input[CONF_IP_ADDRESS]
                )
                if not errors and configuration:
                    await self.async_set_unique_id(configuration.device_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_DEVICE_ID], data=user_input
                    )

        # No discovered devices, show the form for manual entry
        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema if device else STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS,
                    description={
                        "suggested_value": entry.data[CONF_IP_ADDRESS],
                    },
                ): str,
            }
        )
        if user_input:
            user_input[CONF_IP_ADDRESS]
            errors, configuration = await _check_connection(
                user_input[CONF_IP_ADDRESS],
            )
            if not errors and configuration:
                await self.async_set_unique_id(configuration.device_id)
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={
                        CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle TSmart Thermostat options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Transmission options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = vol.Schema(
            {
                vol.Required(
                    CONF_TEMPERATURE_MODE,
                    default=self.config_entry.options.get(
                        CONF_TEMPERATURE_MODE, TEMPERATURE_MODE_AVERAGE
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=TEMPERATURE_MODES,
                        translation_key="temperature_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                )
            }
        )

        return self.async_show_form(step_id="init", data_schema=options)
