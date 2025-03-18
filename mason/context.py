from typing import Any, Iterator, Optional

from mason import config
from mason.package import Package
from mason.registry import Registry


class Context:
    _registries: list[Registry]
    _packages: dict[str, Package]
    _packages_data: dict[str, dict[str, Any]]
    package_names: list[str]
    installed_package_names: list[str]

    def __init__(self) -> None:
        self._registries = [Registry(r) for r in config.registries]
        self._load_packages()

    @property
    def packages(self) -> Iterator[Package]:
        for name, pkg in self._packages_data.items():
            if name in self._packages:
                yield self._packages[name]
            else:
                yield self._packages.setdefault(name, Package(pkg))

    def package(self, name: str) -> Optional[Package]:
        if name in self._packages:
            return self._packages[name]
        package = self._packages_data.get(name)
        if package:
            return self._packages.setdefault(name, Package(package))
        return None

    def update_registries(self) -> None:
        for reg in self._registries:
            reg.update()
        self._load_packages()

    def _load_packages(self):
        self._packages = {}
        self._packages_data = {}
        self.package_names = []
        self.installed_package_names = []
        for reg in self._registries:
            for pkg in reg.packages:
                if name := pkg.get("name"):
                    self._packages_data[name] = pkg
                    self.package_names.append(name)
                    if (config.packages_dir / name / "mason-receipt.json").exists():
                        self.installed_package_names.append(name)
