"""Tests for UDP requests, discovery, and socket cleanup."""

import asyncio
import socket
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from custom_components.t_smart.tsmart import (
    UDP_PORT,
    DiscoveredDevice,
    TSmart,
    TSmartInvalidResponseError,
)
from pytest_homeassistant_custom_component.common import load_json_object_fixture

from .conftest import MockUDP


@pytest.fixture
def status_response() -> bytes:
    """Return a checksummed status response from the device fixture."""
    return bytes.fromhex(load_json_object_fixture("device.json")["status"])


@pytest.fixture
def discovery_response() -> bytes:
    """Return a checksummed discovery response from the device fixture."""
    return bytes.fromhex(load_json_object_fixture("device.json")["discovery"])


async def test_request(mock_udp: MockUDP, status_response: bytes) -> None:
    """Send a checksummed datagram and decode the matching reply."""
    mock_udp.recv.return_value = status_response
    device = TSmart("192.0.2.10")

    status = await device.async_get_status()

    assert status.temperature_high == 55.0
    assert status.temperature_low == 45.0
    assert device.request_successful
    mock_udp.socket.setblocking.assert_called_once_with(False)
    mock_udp.socket.bind.assert_called_once_with(("", UDP_PORT))
    mock_udp.socket.setsockopt.assert_called_once_with(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )
    mock_udp.connect.assert_awaited_once_with(mock_udp.socket, ("192.0.2.10", UDP_PORT))
    mock_udp.send.assert_awaited_once_with(mock_udp.socket, b"\xf1\x00\x00\xa4")
    mock_udp.recv.assert_awaited_once_with(mock_udp.socket, 65536)
    mock_udp.socket.close.assert_called_once()


@pytest.mark.parametrize(
    "first_response",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(b"invalid", id="invalid-length"),
        pytest.param(bytes(30), id="device-error"),
        pytest.param(b"\xf1" + bytes(29), id="checksum"),
        pytest.param(b"\x21" + bytes(29), id="response-type"),
    ],
)
async def test_request_retry(
    mock_udp: MockUDP, status_response: bytes, first_response: bytes | Exception
) -> None:
    """Retry a timeout or invalid response and accept the next valid reply."""
    mock_udp.recv.side_effect = [first_response, status_response]
    device = TSmart("192.0.2.10")

    await device.async_get_status()

    assert device.request_successful
    assert mock_udp.send.await_count == 2
    mock_udp.socket.close.assert_called_once()


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        pytest.param(TimeoutError(), TimeoutError, id="timeout"),
        pytest.param(b"invalid", TSmartInvalidResponseError, id="invalid-response"),
        pytest.param(ConnectionRefusedError(), ConnectionRefusedError, id="refused"),
    ],
)
async def test_request_failure(
    mock_udp: MockUDP, response: bytes | Exception, expected: type[Exception]
) -> None:
    """Preserve failure types and close the socket after an unsuccessful request."""
    mock_udp.recv.side_effect = [response, response]
    device = TSmart("192.0.2.10")

    with pytest.raises(expected):
        await device.async_get_status()

    assert not device.request_successful
    mock_udp.socket.close.assert_called_once()


async def test_send_failure(mock_udp: MockUDP, status_response: bytes) -> None:
    """Release the port lock after a send failure so a later request can succeed."""
    mock_udp.send.side_effect = ConnectionRefusedError
    device = TSmart("192.0.2.10")
    with pytest.raises(ConnectionRefusedError):
        await device.async_get_status()
    mock_udp.socket.close.assert_called_once()

    mock_udp.send.side_effect = None
    mock_udp.recv.return_value = status_response
    await device.async_get_status()
    assert device.request_successful


@pytest.mark.parametrize(
    ("stop_on_first", "expected_sends"),
    [
        pytest.param(True, 1, id="first-device"),
        pytest.param(False, 2, id="all-devices"),
    ],
)
async def test_discovery(
    mock_udp: MockUDP,
    discovery_response: bytes,
    stop_on_first: bool,
    expected_sends: int,
) -> None:
    """Broadcast discovery and deduplicate replies across both attempts."""
    reply = (discovery_response, ("192.0.2.10", UDP_PORT))
    mock_udp.recvfrom.side_effect = [
        reply,
        reply,
        TimeoutError(),
        reply,
        TimeoutError(),
    ]

    assert await TSmart.async_discover(stop_on_first=stop_on_first) == [
        DiscoveredDevice(ip_address="192.0.2.10", device_id="1234", name="Water heater")
    ]

    assert mock_udp.sendto.await_count == expected_sends
    mock_udp.sendto.assert_awaited_with(
        mock_udp.socket, b"\x01\x00\x00\x54", ("255.255.255.255", UDP_PORT)
    )
    mock_udp.socket.setsockopt.assert_any_call(
        socket.SOL_SOCKET, socket.SO_BROADCAST, 1
    )
    mock_udp.socket.setblocking.assert_called_once_with(False)
    mock_udp.socket.bind.assert_called_once_with(("", UDP_PORT))
    mock_udp.socket.close.assert_called_once()


@pytest.mark.parametrize(
    "invalid_response",
    [
        pytest.param(b"\x01\x00\x00\x54", id="own-broadcast"),
        pytest.param(b"invalid", id="invalid-length"),
        pytest.param(bytes(43), id="device-error"),
        pytest.param(b"\x21" + bytes(42), id="response-type"),
        pytest.param(b"\x01" + bytes(42), id="checksum"),
    ],
)
async def test_discovery_ignores_invalid_reply(
    mock_udp: MockUDP, discovery_response: bytes, invalid_response: bytes
) -> None:
    """Ignore unrelated or corrupt datagrams while continuing discovery."""
    mock_udp.recvfrom.side_effect = [
        (invalid_response, ("192.0.2.10", UDP_PORT)),
        (discovery_response, ("192.0.2.10", UDP_PORT)),
    ]
    assert len(await TSmart.async_discover(stop_on_first=True)) == 1


async def test_discovery_timeout(mock_udp: MockUDP) -> None:
    """Return no devices after both discovery attempts time out."""
    mock_udp.recvfrom.side_effect = TimeoutError
    assert await TSmart.async_discover() == []
    assert mock_udp.sendto.await_count == 2
    mock_udp.socket.close.assert_called_once()


@pytest.mark.parametrize(
    "operation",
    [
        pytest.param("async_get_status", id="request"),
        pytest.param("async_discover", id="discovery"),
    ],
)
async def test_cancel_receive(mock_udp: MockUDP, operation: str) -> None:
    """Cancellation closes the socket and releases the shared UDP lock."""
    receiving = asyncio.Event()

    async def wait_for_response(*_args: object) -> bytes:
        receiving.set()
        await asyncio.Future()
        return b""

    mock_udp.recv.side_effect = wait_for_response
    mock_udp.recvfrom.side_effect = wait_for_response
    task = asyncio.create_task(getattr(TSmart("192.0.2.10"), operation)())
    await receiving.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    mock_udp.socket.close.assert_called_once()

    mock_udp.recvfrom.side_effect = TimeoutError
    assert await TSmart.async_discover() == []


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        pytest.param("async_get_status", TimeoutError, id="request"),
        pytest.param("async_discover", list, id="discovery"),
    ],
)
async def test_receive_timeout(
    mock_udp: MockUDP, operation: str, expected: type[object]
) -> None:
    """An expired asyncio timeout cancels pending I/O and closes the socket."""

    async def wait_for_response(*_args: object) -> bytes:
        await asyncio.Future()
        return b""

    mock_udp.recv.side_effect = wait_for_response
    mock_udp.recvfrom.side_effect = wait_for_response
    with patch("custom_components.t_smart.tsmart.TIMEOUT", 0):
        result = await asyncio.gather(
            getattr(TSmart("192.0.2.10"), operation)(), return_exceptions=True
        )

    assert len(result) == 1
    assert isinstance(result[0], expected)
    assert mock_udp.send.await_count + mock_udp.sendto.await_count == 2
    mock_udp.socket.close.assert_called_once()


@pytest.mark.usefixtures("socket_enabled")
async def test_request_over_udp(status_response: bytes) -> None:
    """Exchange real UDP datagrams with a local thermostat stand-in."""
    loop = asyncio.get_running_loop()
    clients: list[socket.socket] = []

    class LocalSocket(socket.socket):
        """Bind the client to an ephemeral port for the loopback test."""

        def bind(self, _address: tuple[str, int]) -> None:
            super().bind(("127.0.0.1", 0))
            clients.append(self)

    socket_module = SimpleNamespace(**vars(socket))
    socket_module.socket = LocalSocket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.setblocking(False)
        server.bind(("127.0.0.1", 0))

        async def respond() -> None:
            request, remote = await loop.sock_recvfrom(server, 65536)
            assert request == b"\xf1\x00\x00\xa4"
            await loop.sock_sendto(server, status_response, remote)

        responder = asyncio.create_task(respond())
        try:
            with (
                patch("custom_components.t_smart.tsmart.socket", socket_module),
                patch(
                    "custom_components.t_smart.tsmart.UDP_PORT", server.getsockname()[1]
                ),
            ):
                status = await TSmart("127.0.0.1").async_get_status()
            await responder
        finally:
            responder.cancel()
            await asyncio.gather(responder, return_exceptions=True)

    assert status.temperature_high == 55.0
    assert len(clients) == 1
    assert clients[0].fileno() == -1
