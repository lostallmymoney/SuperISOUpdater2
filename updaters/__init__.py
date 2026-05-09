"""Package exports for updater modules.

This file dynamically imports updater classes so that missing/errored
submodules don't break importing the package. Imported classes are
exported via __all__.
"""
from __future__ import annotations

import logging
from importlib import import_module
from typing import Dict
from typing import TYPE_CHECKING

# Always import the GenericUpdater base class from the generic subpackage
try:
    from .generic.GenericUpdater import GenericUpdater  # type: ignore
except Exception as e:
    logging.debug(f"Could not import GenericUpdater: {e}")

# Mapping of module filename (without .py) -> exported class name
_UPDATERS: Dict[str, str] = {
    "ArchLinux": "ArchLinux",
    "ChromeOS": "ChromeOS",
    "Clonezilla": "Clonezilla",
    "Debian": "Debian",
    "Fedora": "Fedora",
    "FreeDOS": "FreeDOS",
    "GPartedLive": "GPartedLive",
    "HDAT2": "HDAT2",
    "HirensBootCDPE": "HirensBootCDPE",
    "KaliLinux": "KaliLinux",
    "LinuxMint": "LinuxMint",
    "Manjaro": "Manjaro",
    "MemTest86Plus": "MemTest86Plus",
    "OpenSUSE": "OpenSUSE",
    "OpenSUSERolling": "OpenSUSERolling",
    "OPNsense": "OPNsense",
    "Proxmox": "Proxmox",
    "Rescuezilla": "Rescuezilla",
    "RockyLinux": "RockyLinux",
    "ShredOS": "ShredOS",
    "SuperGrub2": "SuperGrub2",
    "SystemRescue": "SystemRescue",
    "Tails": "Tails",
    "TempleOS": "TempleOS",
    "TrueNAS": "TrueNAS",
    "UltimateBootCD": "UltimateBootCD",
    "Ubuntu": "Ubuntu",
    "Windows10": "Windows10",
    "Windows11": "Windows11",
}

if TYPE_CHECKING:
    # Expose updater class names to static type checkers without importing at runtime
    from .ArchLinux import ArchLinux  # type: ignore
    from .ChromeOS import ChromeOS  # type: ignore
    from .Clonezilla import Clonezilla  # type: ignore
    from .Debian import Debian  # type: ignore
    from .Fedora import Fedora  # type: ignore
    from .FreeDOS import FreeDOS  # type: ignore
    from .GPartedLive import GPartedLive  # type: ignore
    from .HDAT2 import HDAT2  # type: ignore
    from .HirensBootCDPE import HirensBootCDPE  # type: ignore
    from .KaliLinux import KaliLinux  # type: ignore
    from .LinuxMint import LinuxMint  # type: ignore
    from .Manjaro import Manjaro  # type: ignore
    from .MemTest86Plus import MemTest86Plus  # type: ignore
    from .OpenSUSE import OpenSUSE  # type: ignore
    from .OpenSUSERolling import OpenSUSERolling  # type: ignore
    from .OPNsense import OPNsense  # type: ignore
    from .Proxmox import Proxmox  # type: ignore
    from .Rescuezilla import Rescuezilla  # type: ignore
    from .RockyLinux import RockyLinux  # type: ignore
    from .ShredOS import ShredOS  # type: ignore
    from .SuperGrub2 import SuperGrub2  # type: ignore
    from .SystemRescue import SystemRescue  # type: ignore
    from .Tails import Tails  # type: ignore
    from .TempleOS import TempleOS  # type: ignore
    from .TrueNAS import TrueNAS  # type: ignore
    from .UltimateBootCD import UltimateBootCD  # type: ignore
    from .Ubuntu import Ubuntu  # type: ignore
    from .Windows10 import Windows10  # type: ignore
    from .Windows11 import Windows11  # type: ignore

# Dynamically import available updater classes. Failures are logged
# at debug level so package import still succeeds even if a submodule
# has an error or missing dependency. We still compute a static
# __all__ for linters and deterministic exports.
for _mod_name, _cls_name in _UPDATERS.items():
    try:
        _mod = import_module(f".{_mod_name}", __package__)
        _cls = getattr(_mod, _cls_name)
        globals()[_cls_name] = _cls
    except Exception as _exc:  # pragma: no cover - runtime import failures
        logging.debug(f"updaters: failed to import {_mod_name}.{_cls_name}: {_exc}")

# Static, deterministic export list
__all__ = [
    "GenericUpdater",
    "ArchLinux",
    "ChromeOS",
    "Clonezilla",
    "Debian",
    "Fedora",
    "FreeDOS",
    "GPartedLive",
    "HDAT2",
    "HirensBootCDPE",
    "KaliLinux",
    "LinuxMint",
    "Manjaro",
    "MemTest86Plus",
    "OpenSUSE",
    "OpenSUSERolling",
    "OPNsense",
    "Proxmox",
    "Rescuezilla",
    "RockyLinux",
    "ShredOS",
    "SuperGrub2",
    "SystemRescue",
    "Tails",
    "TempleOS",
    "TrueNAS",
    "UltimateBootCD",
    "Ubuntu",
    "Windows10",
    "Windows11",
]
