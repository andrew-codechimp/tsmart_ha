import asyncio
import logging
import socket
import struct
import time
from dataclasses import dataclass
from enum import IntEnum

import asyncio_dgram

UDP_PORT = 1337

_LOGGER = logging.getLogger(__name__)


class TSmartMode(IntEnum):
    """Operating modes for TSmart devices."""

    MANUAL = 0x00
    ECO = 0x01
    SMART = 0x02
    TIMER = 0x03
    TRAVEL = 0x04
    BOOST = 0x05
    LIMITED = 0x21
    CRITICAL = 0x22


@dataclass(frozen=True, slots=True, kw_only=True)
class TSmartConfiguration:
    device_id: str
    name: str
    firmware_name: str
    firmware_version: str


@dataclass(frozen=True, slots=True, kw_only=True)
class TSmartStatus:
    power: bool
    temperature_average: float
    temperature_high: float
    temperature_low: float
    setpoint: float
    mode: TSmartMode
    relay: bool
    e01: bool
    e01_count: int
    e02: bool
    e02_count: int
    e03: bool
    e03_count: int
    e04: bool
    e04_count: int
    e05: bool
    e05_count: int
    w01: bool
    w01_count: int
    w02: bool
    w02_count: int
    w03: bool
    w03_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class DiscoveredDevice:
    ip: str
    device_id: str
    name: str


class TSmart:
    """Representation of a T-Smart device."""

    ip: str
    device_id: str | None = None
    name: str | None = None
    firmware_name: str = ""
    firmware_version: str = ""

    def __init__(self, ip: str, device_id: str | None = None, name: str | None = None):
        self.ip = ip
        self.device_id = device_id
        self.name = name

    async def async_discover(
        stop_on_first=False, tries=2, timeout=2
    ) -> list[DiscoveredDevice]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 1337))

        stream = await asyncio_dgram.from_socket(sock)
        response_struct = struct.Struct("=BBBHL32sBB")

        devices: dict[str, DiscoveredDevice] = {}

        data = None
        for i in range(tries):
            message = struct.pack("=BBBB", 0x01, 0, 0, 0x01 ^ 0x55)

            await stream.send(message, ("255.255.255.255", UDP_PORT))

            while True:
                try:
                    data, remote_addr = await asyncio.wait_for(stream.recv(), timeout)
                    if len(data) == len(message):
                        # Got our own broadcast
                        continue

                    if len(data) != response_struct.size:
                        _LOGGER.warning(
                            "Unexpected packet length (got: %d, expected: %d)"
                            % (len(data), response_struct.size)
                        )
                        continue

                    if data[0] == 0:
                        _LOGGER.warning("Got error response (code %d)" % (data[0]))
                        continue

                    if (
                        data[0] != message[0]
                        or data[1] != data[1]
                        or data[2] != data[2]
                    ):
                        _LOGGER.warning(
                            "Unexpected response type (%02X %02X %02X)"
                            % (data[0], data[1], data[2])
                        )
                        continue

                    t = 0
                    for b in data[:-1]:
                        t = t ^ b
                    if t ^ 0x55 != data[-1]:
                        _LOGGER.warning("Received packet checksum failed")
                        continue

                    _LOGGER.info("Got response from %s" % remote_addr[0])

                    if remote_addr[0] not in devices:
                        (
                            cmd,
                            sub,
                            sub2,
                            device_type,
                            device_id,
                            name,
                            tz,
                            checksum,
                        ) = response_struct.unpack(data)
                        device_name = name.decode("utf-8").split("\x00")[0]
                        device_id_str = "%4X" % device_id
                        _LOGGER.info("Discovered %s %s" % (device_id_str, device_name))
                        devices[remote_addr[0]] = DiscoveredDevice(
                            ip=remote_addr[0],
                            device_id=device_id_str,
                            name=device_name,
                        )
                        if stop_on_first:
                            break

                except asyncio.exceptions.TimeoutError:
                    break

            if stop_on_first and len(devices) > 0:
                break

        stream.close()

        return devices.values()

    async def _async_request(self, request, response_struct):
        self.request_successful = False

        t = 0
        request = bytearray(request)
        for b in request[:-1]:
            t = t ^ b
        request[-1] = t ^ 0x55

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 1337))
        sock.connect((self.ip, UDP_PORT))

        stream = await asyncio_dgram.from_socket(sock)

        data = None
        for i in range(2):
            await stream.send(request)

            _LOGGER.info("Message sent to %s" % self.ip)

            try:
                data, remote_addr = await asyncio.wait_for(stream.recv(), 2)
                if len(data) != response_struct.size:
                    _LOGGER.warning(
                        "Unexpected packet length (got: %d, expected: %d)"
                        % (len(data), response_struct.size)
                    )
                    continue

                if data[0] == 0:
                    _LOGGER.warning("Got error response (code %d)" % (data[0]))
                    continue

                if data[0] != request[0] or data[1] != data[1] or data[2] != data[2]:
                    _LOGGER.warning(
                        "Unexpected response type (%02X %02X %02X)"
                        % (data[0], data[1], data[2])
                    )
                    continue

                t = 0
                for b in data[:-1]:
                    t = t ^ b
                if t ^ 0x55 != data[-1]:
                    _LOGGER.warning("Received packet checksum failed")

            except asyncio.exceptions.TimeoutError:
                continue

            break

        stream.close()

        if data is None:
            _LOGGER.warning("Timed-out fetching status from %s" % self.ip)
            return None

        self.request_successful = True
        return data

    async def async_get_configuration(self) -> TSmartConfiguration | None:
        request = struct.pack("=BBBB", 0x21, 0, 0, 0)

        response_struct = struct.Struct("=BBBHL32sBBBBB32s28s32s64s124s")
        response = await self._async_request(request, response_struct)

        if response is None:
            return None

        (
            cmd,
            sub,
            sub2,
            device_type,
            device_id,
            device_name,
            tz,
            userbin,
            firmware_version_major,
            firmware_version_minor,
            firmware_version_deployment,
            firmware_name,
            legacy,
            wifi_ssid,
            wifi_password,
            unused,
        ) = response_struct.unpack(response)

        self.device_id = "%4X" % device_id
        self.name = device_name.decode("utf-8").split("\x00")[0]
        self.firmware_name = firmware_name.decode("utf-8").split("\x00")[0]
        self.firmware_version = f"{firmware_version_major}.{firmware_version_minor}.{firmware_version_deployment}"

        configuration = TSmartConfiguration(
            device_id=self.device_id,
            name=self.name,
            firmware_name=self.firmware_name,
            firmware_version=self.firmware_version,
        )

        _LOGGER.info("Received configuration from %s" % self.ip)

        return configuration

    async def async_get_status(self) -> TSmartStatus | None:
        request = struct.pack("=BBBB", 0xF1, 0, 0, 0)

        response_struct = struct.Struct("=BBBBHBHBBH16sB")
        response = await self._async_request(request, response_struct)

        if response is None:
            return None

        (
            cmd,
            sub,
            sub2,
            power,
            setpoint,
            mode,
            t_high,
            relay,
            smart_state,
            t_low,
            error_buffer,
            checksum,
        ) = response_struct.unpack(response)

        # Extract 16-bit values (flag in bit 15, counter in bits 0-14)
        e01_value = error_buffer[0] | (error_buffer[1] << 8)
        e02_value = error_buffer[2] | (error_buffer[3] << 8)
        e03_value = error_buffer[4] | (error_buffer[5] << 8)
        e04_value = error_buffer[6] | (error_buffer[7] << 8)
        w01_value = error_buffer[8] | (error_buffer[9] << 8)
        w02_value = error_buffer[10] | (error_buffer[11] << 8)
        w03_value = error_buffer[12] | (error_buffer[13] << 8)
        e05_value = error_buffer[14] | (error_buffer[15] << 8)

        status = TSmartStatus(
            power=bool(power),
            temperature_average=(t_high + t_low) / 20,
            temperature_high=t_high / 10,
            temperature_low=t_low / 10,
            setpoint=setpoint / 10,
            mode=TSmartMode(mode),
            relay=bool(relay),
            e01=(e01_value >> 15) & 1 == 1,
            e01_count=e01_value & 0x7FFF,
            e02=(e02_value >> 15) & 1 == 1,
            e02_count=e02_value & 0x7FFF,
            e03=(e03_value >> 15) & 1 == 1,
            e03_count=e03_value & 0x7FFF,
            e04=(e04_value >> 15) & 1 == 1,
            e04_count=e04_value & 0x7FFF,
            e05=(e05_value >> 15) & 1 == 1,
            e05_count=e05_value & 0x7FFF,
            w01=(w01_value >> 15) & 1 == 1,
            w01_count=w01_value & 0x7FFF,
            w02=(w02_value >> 15) & 1 == 1,
            w02_count=w02_value & 0x7FFF,
            w03=(w03_value >> 15) & 1 == 1,
            w03_count=w03_value & 0x7FFF,
        )

        _LOGGER.info("Received status from %s" % self.ip)
        return status

    async def async_control_set(self, power, mode, setpoint):
        _LOGGER.info("Async control set %d %d %0.2f" % (power, mode, setpoint))

        if mode < 0 or mode > 5:
            raise ValueError("Invalid mode")

        request = struct.pack(
            "=BBBBHBB", 0xF2, 0, 0, int(power), int(setpoint * 10), mode, 0
        )

        response_struct = struct.Struct("=BBBB")
        response = await self._async_request(request, response_struct)

    async def async_restart(self, offset_ms: int = 1000) -> None:
        """Restart the device after specified offset time in milliseconds."""
        if not 100 <= offset_ms <= 10000:
            raise ValueError("Offset must be between 100ms and 10000ms")

        _LOGGER.info("Restarting device %s after %dms" % (self.ip, offset_ms))

        # Split offset into low and high bytes for sub-command
        sub = offset_ms & 0xFF  # Low byte
        sub2 = (offset_ms >> 8) & 0xFF  # High byte

        request = struct.pack("=BBBB", 0x02, sub, sub2, 0)

        response_struct = struct.Struct("=BBBB")
        # Device may not respond if offset is very short
        response = await self._async_request(request, response_struct)
        if response:
            _LOGGER.info("Restart command acknowledged by %s" % self.ip)

    async def async_timesync(self) -> None:
        """Set the device time using UTC timestamp in milliseconds."""
        timestamp_ms = int(time.time() * 1000)

        _LOGGER.info("Setting time on device %s to %d" % (self.ip, timestamp_ms))

        request = struct.pack("=BBBIB", 0x03, 0, 0, timestamp_ms, 0)

        response_struct = struct.Struct("=BBBB")
        response = await self._async_request(request, response_struct)
        if response:
            _LOGGER.info("Time set command acknowledged by %s" % self.ip)
