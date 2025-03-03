import os
from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(
        ["go", "install", "-v", f"{pkg.package}@{pkg.version}"],
        env={**os.environ, "GOBIN": os.getcwd()},
        check=True,
    )


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"{target}")
    else:
        return Path(f"{target}.exe")
