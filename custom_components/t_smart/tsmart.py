import socket
import struct
import asyncio
import logging
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


class TSmart:
    """Representation of a T-Smart device."""

    firmware_name: str
    firmware_version: str

    def __init__(self, ip, device_id=None, name=None):
        self.ip = ip
        self.device_id = device_id
        self.name = name
        self.power = None
        self.temperature_average = None
        self.temperature_high = None
        self.temperature_low = None
        self.mode = None
        self.setpoint = None
        self.relay = None
        self.request_successful = False

    async def async_discover(stop_on_first=False, tries=2, timeout=2):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # Internet, UDP

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", 1337))

        _LOGGER.info("Performing discovery")

        stream = await asyncio_dgram.from_socket(sock)
        response_struct = struct.Struct("=BBBHL32sBB")

        devices = dict()

        data = None
        for i in range(tries):
            message = struct.pack("=BBBB", 0x01, 0, 0, 0x01 ^ 0x55)

            await stream.send(message, ("255.255.255.255", UDP_PORT))

            _LOGGER.info("Discovery message sent")

            while True:
                try:
                    data, remote_addr = await asyncio.wait_for(stream.recv(), timeout)
                    if len(data) == len(message):
                        # Got our own broadcast
                        continue

                    if len(data) != response_struct.size:
                        _LOGGER.warn(
                            "Unexpected packet length (got: %d, expected: %d)"
                            % (len(data), response_struct.size)
                        )
                        continue

                    if data[0] == 0:
                        _LOGGER.warn("Got error response (code %d)" % (data[0]))
                        continue

                    if (
                        data[0] != message[0]
                        or data[1] != data[1]
                        or data[2] != data[2]
                    ):
                        _LOGGER.warn(
                            "Unexpected response type (%02X %02X %02X)"
                            % (data[0], data[1], data[2])
                        )
                        continue

                    t = 0
                    for b in data[:-1]:
                        t = t ^ b
                    if t ^ 0x55 != data[-1]:
                        _LOGGER.warn("Received packet checksum failed")
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
                        devices[remote_addr[0]] = TSmart(
                            remote_addr[0], device_id_str, device_name
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
                    _LOGGER.warn(
                        "Unexpected packet length (got: %d, expected: %d)"
                        % (len(data), response_struct.size)
                    )
                    continue

                if data[0] == 0:
                    _LOGGER.warn("Got error response (code %d)" % (data[0]))
                    continue

                if data[0] != request[0] or data[1] != data[1] or data[2] != data[2]:
                    _LOGGER.warn(
                        "Unexpected response type (%02X %02X %02X)"
                        % (data[0], data[1], data[2])
                    )
                    continue

                t = 0
                for b in data[:-1]:
                    t = t ^ b
                if t ^ 0x55 != data[-1]:
                    _LOGGER.warn("Received packet checksum failed")

            except asyncio.exceptions.TimeoutError:
                continue

            break

        stream.close()

        if data is None:
            _LOGGER.warn("Timed-out fetching status from %s" % self.ip)
            return None

        self.request_successful = True
        return data

    async def async_get_configuration(self):
        _LOGGER.info("Async get configuration")
        request = struct.pack("=BBBB", 0x21, 0, 0, 0)

        response_struct = struct.Struct("=BBBHL32sBBBBB32s28s32s64s124s")
        response = await self._async_request(request, response_struct)

        if response is None:
            return

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
        self.firmware_version = f"{firmware_version_major}.{firmware_version_minor}.{firmware_version_deployment}"
        self.firmware_name = firmware_name.decode("utf-8").split("\x00")[0]

        _LOGGER.info("Received configuration from %s" % self.ip)

    async def async_get_status(self):
        _LOGGER.info("Async get status")
        request = struct.pack("=BBBB", 0xF1, 0, 0, 0)

        response_struct = struct.Struct("=BBBBHBHBBH16sB")
        response = await self._async_request(request, response_struct)

        if response is None:
            return

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

        self.temperature_average = (t_high + t_low) / 20
        self.temperature_high = t_high / 10
        self.temperature_low = t_low / 10
        self.setpoint = setpoint / 10
        self.power = bool(power)
        self.mode = TSmartMode(mode)
        self.relay = bool(relay)

        _LOGGER.info("Received status from %s" % self.ip)

    async def async_control_set(self, power, mode, setpoint):
        _LOGGER.info("Async control set %d %d %0.2f" % (power, mode, setpoint))

        if mode < 0 or mode > 5:
            raise ValueError("Invalid mode")

        request = struct.pack(
            "=BBBBHBB", 0xF2, 0, 0, int(power), int(setpoint * 10), mode, 0
        )

        response_struct = struct.Struct("=BBBB")
        response = await self._async_request(request, response_struct)
