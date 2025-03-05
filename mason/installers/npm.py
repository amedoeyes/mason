import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    Path(".npmrc").write_text("install-strategy=shallow")
    subprocess.run(["npm", "init", "--yes", "--scope=mason"])
    subprocess.run(["npm", "install", f"{pkg.purl.name}@{pkg.purl.version}", *pkg.extra_packages], check=True)
