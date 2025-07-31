"""Constants for the T-Smart Thermostat integration."""

MIN_HA_VERSION = "2025.4"

DOMAIN = "t_smart"
DATA_DISCOVERY_SERVICE = "tsmart_discovery"
COORDINATORS = "coordinators"

PRESET_MANUAL = "Manual"
PRESET_SMART = "Smart"
PRESET_TIMER = "Timer"

CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_TEMPERATURE_MODE = "temperature_mode"

TEMPERATURE_MODE_HIGH = "temperature_mode_high"
TEMPERATURE_MODE_LOW = "temperature_mode_low"
TEMPERATURE_MODE_AVERAGE = "temperature_mode_average"

TEMPERATURE_MODES = [
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
    TEMPERATURE_MODE_AVERAGE,
]

ATTR_TEMPERATURE_LOW = "temperature_low"
ATTR_TEMPERATURE_HIGH = "temperature_high"
ATTR_TEMPERATURE_AVERAGE = "temperature_average"
