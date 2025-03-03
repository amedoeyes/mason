from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(["npm", "init", "--yes", "--scope=mason"])
    Path(".npmrc").write_text("install-strategy=shallow")
    subprocess.run(["npm", "install", f"{pkg.package}@{pkg.version}"] + pkg.extra_packages, check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"node_modules/.bin/{target}")
    else:
        return Path(f"node_modules/.bin/{target}.cmd")
