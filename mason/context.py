import json
from typing import Any, Iterator, Optional

from mason import config
from mason.package import Package, Receipt
from mason.registry import Registry


class Context:
    _registries: list[Registry]
    _packages: dict[str, Package]
    _receipts: dict[str, Receipt]
    _packages_raw: dict[str, dict[str, Any]]
    _receipts_raw: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self._registries = [Registry(r) for r in config.registries]
        self._packages = {}
        self._receipts = {}
        self._packages_raw = {pkg["name"]: pkg for reg in self._registries for pkg in reg.packages if "name" in pkg}
        self._receipts_raw = {
            rct["name"]: rct
            for file in config.packages_dir.glob("*/mason-receipt.json")
            if (rct := json.loads(file.read_bytes())) and "name" in rct
        }

    @property
    def packages(self) -> Iterator[Package]:
        for name, pkg in self._packages_raw.items():
            if name in self._packages:
                yield self._packages[name]
            else:
                yield self._packages.setdefault(name, Package(pkg))

    @property
    def receipts(self) -> Iterator[Receipt]:
        for name, rct in self._receipts_raw.items():
            if name in self._receipts:
                yield self._receipts[name]
            else:
                yield self._receipts.setdefault(name, Receipt(rct))

    def package(self, name: str) -> Optional[Package]:
        if name in self._packages:
            return self._packages[name]
        package = self._packages_raw.get(name)
        if package:
            return self._packages.setdefault(name, Package(package))
        return None

    def receipt(self, name: str) -> Optional[Receipt]:
        if name in self._receipts:
            return self._receipts[name]
        receipt = self._receipts_raw.get(name)
        if receipt:
            return self._receipts.setdefault(name, Receipt(receipt))
        return None

    def update_registries(self) -> None:
        for reg in self._registries:
            reg.update()
        self._packages = {}
        self._receipts = {}
        self._packages_raw = {pkg["name"]: pkg for reg in self._registries for pkg in reg.packages if "name" in pkg}
        self._receipts_raw = {
            rct["name"]: rct
            for file in config.packages_dir.glob("*/mason-receipt.json")
            if (rct := json.loads(file.read_bytes())) and "name" in rct
        }
