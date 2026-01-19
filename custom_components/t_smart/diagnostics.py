"""Diagnostics support for T-Smart."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .common import TSmartConfigEntry

TO_REDACT = {"ip_address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TSmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    device = coordinator.device

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "version": entry.version,
        },
        "device": {
            "firmware_name": device.firmware_name,
            "firmware_version": device.firmware_version,
            "power": device.power,
            "mode": device.mode.name if device.mode is not None else None,
            "setpoint": device.setpoint,
            "temperature_average": device.temperature_average,
            "temperature_high": device.temperature_high,
            "temperature_low": device.temperature_low,
            "relay": device.relay,
            "error_status": device.error_status,
            "error_e01": device.error_e01,
            "error_e02": device.error_e02,
            "error_e03": device.error_e03,
            "error_e04": device.error_e04,
            "error_e05": device.error_e05,
            "error_w01": device.error_w01,
            "error_w02": device.error_w02,
            "error_w03": device.error_w03,
            "request_successful": device.request_successful,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "temperature_mode": coordinator.temperature_mode,
        },
    }
