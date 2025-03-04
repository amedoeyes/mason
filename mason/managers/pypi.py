import subprocess
from pathlib import Path

from mason.package import Package
from mason.utility import select_by_os


def install(pkg: Package) -> None:
    python_bin = select_by_os(unix="python3", windows="python")
    pip_bin = select_by_os(
        unix=Path("venv") / "bin" / "python",
        windows=Path("venv") / "Scripts" / "python.exe",
    )
    extra = f"[{pkg.params['extra']}]" if "extra" in pkg.params else ""
    subprocess.run([python_bin, "-m", "venv", "venv", "--system-site-packages"], check=True)
    subprocess.run(
        [
            pip_bin,
            "-m",
            "pip",
            "--disable-pip-version-check",
            "install",
            "--ignore-installed",
            "-U",
            f"{pkg.package}{extra}=={pkg.version}",
            *pkg.extra_packages,
        ],
        check=True,
    )


def bin_path(target: str) -> Path:
    return select_by_os(
        unix=Path("venv") / "bin" / target,
        windows=Path("venv") / "Scripts" / f"{target}.exe",
    )
