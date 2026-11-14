"""Tests for T-Smart discovery, manual setup, reconfiguration, and options."""

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from custom_components.t_smart.const import (
    CONF_DEVICE_NAME,
    CONF_TEMPERATURE_MODE,
    DOMAIN,
    TEMPERATURE_MODE_AVERAGE,
    TEMPERATURE_MODE_HIGH,
    TEMPERATURE_MODE_LOW,
    TEMPERATURE_MODES,
)
from custom_components.t_smart.tsmart import (
    DiscoveredDevice,
    TSmartInvalidResponseError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_tsmart", "mock_setup_entry")

HOST = "192.0.2.10"
NEW_HOST = "192.0.2.20"
DISCOVERED_DEVICE = DiscoveredDevice(
    ip_address=HOST, device_id="1234", name="Water heater"
)


async def test_manual_setup(
    hass: HomeAssistant, mock_tsmart: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Show a manual form when discovery is empty and store validated device data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert result["data_schema"]({CONF_IP_ADDRESS: HOST}) == {CONF_IP_ADDRESS: HOST}
    mock_tsmart.async_discover.assert_awaited_once_with()
    mock_tsmart.return_value.async_get_configuration.assert_not_awaited()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: HOST}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1234"
    assert result["data"] == {
        CONF_IP_ADDRESS: HOST,
        CONF_DEVICE_ID: "1234",
        CONF_DEVICE_NAME: "Water heater",
    }
    assert result["result"].unique_id == "1234"
    assert result["result"].version == 3
    mock_tsmart.assert_called_once_with(ip_address=HOST)
    mock_setup_entry.assert_awaited_once()


async def test_discovered_setup(
    hass: HomeAssistant, mock_tsmart: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Create an entry automatically after discovering and validating a thermostat."""
    mock_tsmart.async_discover.return_value = [DISCOVERED_DEVICE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "1234"
    assert result["data"] == {
        CONF_IP_ADDRESS: HOST,
        CONF_DEVICE_ID: "1234",
        CONF_DEVICE_NAME: "Water heater",
    }
    assert result["result"].unique_id == "1234"
    assert result["result"].version == 3
    mock_tsmart.assert_called_once_with(ip_address=HOST)
    mock_tsmart.return_value.async_get_configuration.assert_awaited_once_with()
    mock_setup_entry.assert_awaited_once()


async def test_discovery_skips_configured_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsmart: MagicMock,
) -> None:
    """Offer manual setup if every discovered thermostat is already configured."""
    mock_config_entry.add_to_hass(hass)
    mock_tsmart.async_discover.return_value = [DISCOVERED_DEVICE]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    mock_tsmart.return_value.async_get_configuration.assert_not_awaited()


async def test_discovery_selects_unconfigured_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsmart: MagicMock,
) -> None:
    """Skip an existing device and configure the next newly discovered thermostat."""
    mock_config_entry.add_to_hass(hass)
    mock_tsmart.async_discover.return_value = [
        DISCOVERED_DEVICE,
        DiscoveredDevice(ip_address=NEW_HOST, device_id="5678", name="Second heater"),
    ]
    client = mock_tsmart.return_value
    client.async_get_configuration.return_value = replace(
        client.async_get_configuration.return_value,
        device_id="5678",
        name="Second heater",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "5678"
    assert result["result"].unique_id == "5678"
    assert result["data"] == {
        CONF_IP_ADDRESS: NEW_HOST,
        CONF_DEVICE_ID: "5678",
        CONF_DEVICE_NAME: "Second heater",
    }
    mock_tsmart.assert_called_once_with(ip_address=NEW_HOST)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_manual_connection_error(
    hass: HomeAssistant, mock_tsmart: MagicMock, exception: Exception
) -> None:
    """Keep the form open on connection errors and allow a successful retry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    client = mock_tsmart.return_value
    client.async_get_configuration.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_thermostat_found"}
    assert hass.config_entries.async_entries(DOMAIN) == []

    client.async_get_configuration.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: HOST}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1234"


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_discovered_connection_error(
    hass: HomeAssistant, mock_tsmart: MagicMock, exception: Exception
) -> None:
    """Suggest the discovered IP when its configuration cannot be read."""
    mock_tsmart.async_discover.return_value = [DISCOVERED_DEVICE]
    mock_tsmart.return_value.async_get_configuration.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_thermostat_found"}
    assert {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    } == {CONF_IP_ADDRESS: HOST}
    assert hass.config_entries.async_entries(DOMAIN) == []


async def test_duplicate_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Reject a manual connection to the same device even at another IP address."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_IP_ADDRESS: NEW_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_IP_ADDRESS] == HOST
    mock_setup_entry.assert_not_awaited()


async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsmart: MagicMock,
) -> None:
    """Update the IP address while preserving identity, device name, and options."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW}
    )
    original_data = dict(mock_config_entry.data)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}
    assert {
        key.schema: key.description["suggested_value"]
        for key in result["data_schema"].schema
    } == {CONF_IP_ADDRESS: HOST}

    with patch.object(hass.config_entries, "async_reload", return_value=True) as reload:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: NEW_HOST}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {**original_data, CONF_IP_ADDRESS: NEW_HOST}
    assert mock_config_entry.unique_id == "1234"
    assert mock_config_entry.options == {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW}
    mock_tsmart.assert_called_once_with(ip_address=NEW_HOST)
    reload.assert_awaited_once_with(mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(ConnectionRefusedError(), id="refused"),
        pytest.param(TSmartInvalidResponseError(), id="invalid-response"),
    ],
)
async def test_reconfigure_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsmart: MagicMock,
    exception: Exception,
) -> None:
    """Keep the original address when reconfiguration cannot reach the device."""
    mock_config_entry.add_to_hass(hass)
    mock_tsmart.return_value.async_get_configuration.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: NEW_HOST}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "no_thermostat_found"}
    assert mock_config_entry.data[CONF_IP_ADDRESS] == HOST


async def test_reconfigure_wrong_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsmart: MagicMock,
) -> None:
    """Reject an address belonging to a different thermostat."""
    mock_config_entry.add_to_hass(hass)
    client = mock_tsmart.return_value
    client.async_get_configuration.return_value = replace(
        client.async_get_configuration.return_value, device_id="5678"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": mock_config_entry.entry_id},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IP_ADDRESS: NEW_HOST}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_IP_ADDRESS] == HOST
    assert mock_config_entry.unique_id == "1234"


@pytest.mark.parametrize(
    ("options", "expected_default"),
    [
        pytest.param({}, TEMPERATURE_MODE_HIGH, id="default-high"),
        pytest.param(
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_LOW},
            TEMPERATURE_MODE_LOW,
            id="saved-low",
        ),
        pytest.param(
            {CONF_TEMPERATURE_MODE: TEMPERATURE_MODE_AVERAGE},
            TEMPERATURE_MODE_AVERAGE,
            id="saved-average",
        ),
    ],
)
async def test_options_defaults(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    options: dict[str, str],
    expected_default: str,
) -> None:
    """Suggest the saved mode or default to the high temperature sensor."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert {key.schema: key.default() for key in result["data_schema"].schema} == {
        CONF_TEMPERATURE_MODE: expected_default
    }
    assert result["data_schema"].schema[CONF_TEMPERATURE_MODE].config["options"] == (
        TEMPERATURE_MODES
    )


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(TEMPERATURE_MODE_HIGH, id="high"),
        pytest.param(TEMPERATURE_MODE_LOW, id="low"),
        pytest.param(TEMPERATURE_MODE_AVERAGE, id="average"),
    ],
)
async def test_options_save(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mode: str
) -> None:
    """Save each supported temperature mode without altering device data."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    options = {CONF_TEMPERATURE_MODE: mode}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], options
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == options
    assert mock_config_entry.data == original_data
    assert mock_config_entry.title == "Water heater"
