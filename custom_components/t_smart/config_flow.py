"""Config flow for T-Smart Thermostat integration."""

from __future__ import annotations

import copy
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_IP_ADDRESS,
)
from homeassistant.helpers import selector
from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    TEMPERATURE_MODES,
    CONF_TEMPERATURE_MODE,
    TEMPERATURE_MODE_AVERAGE,
)
from .tsmart import TSmart

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
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

CONFIG_VERSION = 1

TIMEOUT = 2


def _base_schema(discovery_info=None) -> vol.Schema:
    """Generate base schema."""
    base_schema = {}
    if discovery_info and CONF_IP_ADDRESS in discovery_info:
        base_schema.update(
            {
                vol.Required(
                    CONF_IP_ADDRESS,
                    description={"suggested_value": discovery_info[CONF_IP_ADDRESS]},
                ): str,
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
    else:
        base_schema.update({vol.Required(CONF_IP_ADDRESS): str})

    return vol.Schema(base_schema)


class TSmartConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for TSmart Thermostat."""

    VERSION = CONFIG_VERSION

    def __init__(self) -> None:
        """Initialize an instance of the TSmart config flow."""
        self.data_schema = _base_schema()
        self.discovery_info = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def _discover(self):
        """Discover an unconfigured TSmart thermostat."""
        self.discovery_info = None

        devices = await TSmart.async_discover()

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

            self.discovery_info = {
                CONF_IP_ADDRESS: device.ip,
                CONF_DEVICE_ID: device.device_id,
                CONF_DEVICE_NAME: device.name,
            }
            _LOGGER.debug("Discovered thermostat: %s", self.discovery_info)

            # update with suggested values from discovery
            self.data_schema = _base_schema(self.discovery_info)

    async def _validate_input(self, data) -> str | None:
        """Validate the user input allows us to connect.

        Abort if device_id already configured.
        """
        device = TSmart(ip=data[CONF_IP_ADDRESS])

        try:
            async with asyncio.timeout(TIMEOUT):
                await device.async_get_configuration()
        except TimeoutError:
            return "no_thermostat_found"

        if device.device_id:
            await self.async_set_unique_id(device.device_id)
            self._abort_if_unique_id_configured()
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            # Try to connect and do any error checking here
            device = TSmart(ip=user_input[CONF_IP_ADDRESS])

            try:
                async with asyncio.timeout(TIMEOUT):
                    await device.async_get_configuration()
            except TimeoutError:
                errors["base"] = "no_thermostat_found"

            user_input[CONF_DEVICE_ID] = device.device_id
            user_input[CONF_DEVICE_NAME] = device.name

            # Save instance
            if not errors:
                return self.async_create_entry(title=device.device_id, data=user_input)

        # no device specified, see if we can discover an unconfigured thermostat
        await self._discover()
        if self.discovery_info:
            await self.async_set_unique_id(self.discovery_info[CONF_DEVICE_ID])
            user_input = {}
            user_input[CONF_IP_ADDRESS] = self.discovery_info[CONF_IP_ADDRESS]
            user_input[CONF_DEVICE_ID] = self.discovery_info[CONF_DEVICE_ID]
            user_input[CONF_DEVICE_NAME] = self.discovery_info[CONF_DEVICE_NAME]
            user_input[CONF_TEMPERATURE_MODE] = TEMPERATURE_MODE_AVERAGE
            return await self.async_step_edit(user_input)

        # no discovered devices, show the form for manual entry
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_edit(self, user_input=None):
        """Edit a discovered or manually inputted thermostat."""
        errors = {}
        if user_input:
            error = await self._validate_input(user_input)
            if not error:
                return self.async_create_entry(
                    title=user_input[CONF_DEVICE_ID], data=user_input
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="edit", data_schema=self.data_schema, errors=errors
        )


class OptionsFlowHandler(OptionsFlow):
    """Handle an option flow for TSmart Thermostat."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle options flow."""
        errors = {}

        self.current_config: dict = dict(self.config_entry.data)
        self.ip: str = self.current_config.get(CONF_IP_ADDRESS)
        self.device_id: str = self.current_config.get(CONF_DEVICE_ID)
        self.device_name: str = self.current_config.get(CONF_DEVICE_NAME)

        schema = self.build_options_schema()

        if user_input is not None:
            # Try to connect and do any error checking here
            device = TSmart(ip=user_input[CONF_IP_ADDRESS])

            try:
                async with asyncio.timeout(TIMEOUT):
                    await device.async_get_configuration()
            except TimeoutError:
                errors["base"] = "no_thermostat_found"

            if not errors:
                user_input[CONF_DEVICE_ID] = device.device_id
                user_input[CONF_DEVICE_NAME] = device.name

                errors = await self.save_options(user_input, schema)
                if not errors:
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    async def save_options(
        self,
        user_input: dict[str, Any],
        schema: vol.Schema,
    ) -> dict:
        """Save options, and return errors when validation fails."""

        self._process_user_input(user_input, schema)
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=self.current_config,
        )
        return {}

    def _process_user_input(
        self,
        user_input: dict[str, Any],
        schema: vol.Schema,
    ) -> None:
        """Process the provided user input against the schema."""
        for key in schema.schema:
            if isinstance(key, vol.Marker):
                key = key.schema
            if key in user_input:
                self.current_config[key] = user_input.get(key)
            elif key in self.current_config:
                self.current_config.pop(key)

    def build_options_schema(self) -> vol.Schema:
        """Build the options schema."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT),
                ),
                vol.Required(CONF_TEMPERATURE_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=TEMPERATURE_MODES,
                        translation_key="temperature_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            }
        )

        return _fill_schema_defaults(
            data_schema,
            self.current_config,
        )


def _fill_schema_defaults(
    data_schema: vol.Schema,
    options: dict[str, str],
) -> vol.Schema:
    """Make a copy of the schema with suggested values set to saved options."""
    schema = {}
    for key, val in data_schema.schema.items():
        new_key = key
        if key in options and isinstance(key, vol.Marker):
            if (
                isinstance(key, vol.Optional)
                and callable(key.default)
                and key.default()
            ):
                new_key = vol.Optional(key.schema, default=options.get(key))  # type: ignore
            else:
                new_key = copy.copy(key)
                new_key.description = {"suggested_value": options.get(key)}  # type: ignore
        schema[new_key] = val
    return vol.Schema(schema)
