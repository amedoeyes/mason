import platform
import subprocess
from pathlib import Path

from mason.package import Package


def install(pkg: Package) -> None:
    Path(".npmrc").write_text("install-strategy=shallow")
    subprocess.run(["npm", "init", "--yes", "--scope=mason"])
    subprocess.run(["npm", "install", f"{pkg.purl.name}@{pkg.purl.version}", *pkg.extra_packages], check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"node_modules/.bin/{target}")
    else:
        return Path(f"node_modules/.bin/{target}.cmd")
