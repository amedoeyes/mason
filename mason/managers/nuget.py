from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(["dotnet", "tool", "update", "--tool-path", ".", "--version", pkg.version, pkg.package], check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(target)
    else:
        return Path(f"{target}.exe")
