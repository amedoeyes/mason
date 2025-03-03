from pathlib import Path
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(["npm", "install", f"{pkg.package}@{pkg.version}"], check=True)


def bin_path(target: str) -> Path:
    return Path(f"node_modules/.bin/{target}")
