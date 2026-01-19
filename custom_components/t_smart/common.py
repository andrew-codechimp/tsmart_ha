"""Common definitions for T-Smart integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import TSmartCoordinator


@dataclass
class TSmartData:
    """T-Smart data type."""

    coordinator: TSmartCoordinator


type TSmartConfigEntry = ConfigEntry[TSmartData]
