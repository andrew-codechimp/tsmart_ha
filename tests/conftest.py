"""Shared fixtures for T-Smart tests."""

import asyncio
import socket
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from custom_components.t_smart.const import CONF_DEVICE_NAME, DOMAIN
from custom_components.t_smart.tsmart import (
    TSmartConfiguration,
    TSmartMode,
    TSmartSmartState,
    TSmartStatus,
)
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_json_object_fixture,
)
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_DEVICE_ID, CONF_IP_ADDRESS


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Use Home Assistant's snapshot serializer."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in Home Assistant."""


@pytest.fixture(autouse=True)
def freeze_setup_time(freezer: FrozenDateTimeFactory) -> None:
    """Keep entity timestamps and polling deadlines stable."""
    freezer.move_to("2026-07-01T12:00:00+00:00")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create an entry for a configured water heater."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=3,
        entry_id="tsmart-entry",
        unique_id="1234",
        title="Water heater",
        data={
            CONF_IP_ADDRESS: "192.0.2.10",
            CONF_DEVICE_ID: "1234",
            CONF_DEVICE_NAME: "Water heater",
        },
    )


@dataclass
class MockUDP:
    """Represent the socket and event loop's mocked UDP operations."""

    socket: MagicMock
    connect: AsyncMock
    send: AsyncMock
    recv: AsyncMock
    sendto: AsyncMock
    recvfrom: AsyncMock


@pytest.fixture
async def mock_udp() -> AsyncGenerator[MockUDP]:
    """Mock network I/O while keeping asyncio timeouts and locks real."""
    loop = asyncio.get_running_loop()
    sock = MagicMock(spec=socket.socket)
    sock.__enter__.return_value = sock

    def close_socket(*_args: object) -> None:
        sock.close()

    sock.__exit__.side_effect = close_socket
    socket_module = SimpleNamespace(**vars(socket))
    socket_module.socket = Mock(return_value=sock)
    with (
        patch("custom_components.t_smart.tsmart.socket", socket_module),
        patch.object(loop, "sock_connect", new_callable=AsyncMock) as connect,
        patch.object(loop, "sock_sendall", new_callable=AsyncMock) as send,
        patch.object(loop, "sock_recv", new_callable=AsyncMock) as recv,
        patch.object(loop, "sock_sendto", new_callable=AsyncMock) as sendto,
        patch.object(loop, "sock_recvfrom", new_callable=AsyncMock) as recvfrom,
    ):
        yield MockUDP(sock, connect, send, recv, sendto, recvfrom)


@pytest.fixture
def enable_all_entities() -> Generator[None]:
    """Include diagnostic entities in platform snapshots."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        new_callable=PropertyMock,
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Isolate config flow tests from platform setup."""
    with patch(
        "custom_components.t_smart.async_setup_entry", return_value=True
    ) as setup:
        yield setup


@pytest.fixture
def mock_tsmart(mock_config_entry: MockConfigEntry) -> Generator[MagicMock]:
    """Mock thermostat discovery and connection checks for config flows."""
    with patch("custom_components.t_smart.config_flow.TSmart", autospec=True) as client:
        client.async_discover.return_value = []
        client.return_value.async_get_configuration.return_value = TSmartConfiguration(
            device_id=mock_config_entry.data[CONF_DEVICE_ID],
            name=mock_config_entry.data[CONF_DEVICE_NAME],
            firmware_name="T-Smart",
            firmware_version="1.2.3",
        )
        yield client


@pytest.fixture
def mock_device(mock_config_entry: MockConfigEntry) -> Generator[MagicMock]:
    """Mock device communication while retaining real coordinator and entity setup."""
    status = load_json_object_fixture("status.json")
    with patch("custom_components.t_smart.TSmart", autospec=True) as client:
        device = client.return_value
        device.ip_address = mock_config_entry.data[CONF_IP_ADDRESS]
        device.device_id = mock_config_entry.data[CONF_DEVICE_ID]
        device.name = mock_config_entry.data[CONF_DEVICE_NAME]
        device.firmware_version = "1.2.3"
        device.request_successful = True
        device.async_get_configuration.return_value = TSmartConfiguration(
            device_id=device.device_id,
            name=device.name,
            firmware_name="T-Smart",
            firmware_version=device.firmware_version,
        )
        device.async_get_status.return_value = TSmartStatus(
            **{
                **status,
                "mode": TSmartMode(status["mode"]),
                "smart_state": TSmartSmartState(status["smart_state"]),
            }
        )
        yield device


@pytest.fixture
def mock_discovery(mock_device: MagicMock) -> Generator[AsyncMock]:
    """Share discovery results between the mocked device and its factory."""
    with patch(
        "custom_components.t_smart.TSmart.async_discover", mock_device.async_discover
    ) as discovery:
        discovery.return_value = []
        yield discovery
