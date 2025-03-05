import platform
import subprocess
from pathlib import Path

from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(["composer", "init", "--no-interaction", "--stability=stable"], check=True)
    subprocess.run(["composer", "require", f"{pkg.purl.namespace}/{pkg.purl.name}:{pkg.purl.version}"], check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"vendor/bin/{target}")
    else:
        return Path(f"vendor/bin/{target}.bat")
