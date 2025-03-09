import json
from typing import Any, Optional

from mason import config
from mason.package import Package, Receipt
from mason.registry import Registry


class Context:
    registries: list[Registry]
    packages: dict[str, dict[str, Any]]
    receipts: dict[str, dict[str, Any]]

    def __init__(self) -> None:
        self.registries = [Registry(r) for r in config.registries]
        self.packages = {}
        for reg in self.registries:
            for pkg in reg.packages:
                self.packages.setdefault(pkg.get("name", ""), pkg)
        self.receipts = {}
        for file in [file for dir in config.packages_dir.iterdir() if (file := dir / "mason-receipt.json").exists()]:
            receipt = json.loads(file.read_bytes())
            self.receipts[receipt.get("name")] = receipt

    def package(self, name: str) -> Optional[Package]:
        package = self.packages.get(name)
        return Package(package) if package else None

    def receipt(self, name: str) -> Optional[Receipt]:
        receipt = self.packages.get(name)
        return Receipt(receipt) if receipt else None

    def update_registries(self) -> None:
        for reg in self.registries:
            reg.update()
