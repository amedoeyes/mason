from typing import Any, Iterator, Optional

from mason import config
from mason.package import Package
from mason.registry import Registry


class Context:
    _registries: list[Registry]
    _packages: dict[str, Package]
    _packages_raw: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self._registries = [Registry(r) for r in config.registries]
        self._packages = {}
        self._packages_raw = {pkg["name"]: pkg for reg in self._registries for pkg in reg.packages if "name" in pkg}

    @property
    def packages(self) -> Iterator[Package]:
        for name, pkg in self._packages_raw.items():
            if name in self._packages:
                yield self._packages[name]
            else:
                yield self._packages.setdefault(name, Package(pkg))

    @property
    def installed_packages(self) -> Iterator[Package]:
        for name, pkg in self._packages_raw.items():
            if (config.packages_dir / name / "mason-receipt.json").exists():
                if name in self._packages:
                    yield self._packages[name]
                else:
                    yield self._packages.setdefault(name, Package(pkg))

    def package(self, name: str) -> Optional[Package]:
        if name in self._packages:
            return self._packages[name]
        package = self._packages_raw.get(name)
        if package:
            return self._packages.setdefault(name, Package(package))
        return None

    def update_registries(self) -> None:
        for reg in self._registries:
            reg.update()
        self._packages = {}
        self._packages_raw = {pkg["name"]: pkg for reg in self._registries for pkg in reg.packages if "name" in pkg}
