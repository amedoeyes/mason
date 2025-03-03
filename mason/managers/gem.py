import os
from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    subprocess.run(
        [
            "gem",
            "install",
            "--no-user-install",
            "--no-format-executable",
            "--install-dir=.",
            "--bindir=bin",
            "--no-document",
            f"{pkg.package}:{pkg.version}",
        ],
        env={"GEM_HOME": os.getcwd()},
        check=True,
    )


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"bin/{target}")
    else:
        return Path(f"bin/{target}.bat")
