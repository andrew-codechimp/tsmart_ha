"""Base entity for t_smart."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TSmartCoordinator


class TSmartEntity(CoordinatorEntity[TSmartCoordinator]):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: TSmartCoordinator) -> None:
        """Init the base entity."""
        super().__init__(coordinator)
        self._tsmart = coordinator.device

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within our domain
                (DOMAIN, self._tsmart.device_id)
            },
            name=self._tsmart.name,
            manufacturer="Tesla Ltd.",
            model="T-Smart",
            sw_version=self._tsmart.firmware_version,
        )
