from dataclasses import dataclass
from typing import Any, Optional

from mason import config
from mason.package import Package
from mason.registry import Registry


@dataclass
class Context:
    registries: list[Registry]
    packages: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self.registries = [Registry(r) for r in config.registries]
        self.packages = {}
        for reg in self.registries:
            for pkg in reg.packages:
                self.packages.setdefault(pkg["name"], pkg)

    def package(self, name: str) -> Optional[Package]:
        pkg = self.packages.get(name)
        return Package(pkg) if pkg else None

    def update_registries(self) -> None:
        for reg in self.registries:
            reg.update()
