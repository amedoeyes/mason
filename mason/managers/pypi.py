from pathlib import Path
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    extra = f"[{pkg.params['extra']}]" if "extra" in pkg.params else ""
    subprocess.run(["python", "-m", "venv", "venv"], check=True)
    subprocess.run(["./venv/bin/pip", "install", f"{pkg.package}{extra}=={pkg.version}"], check=True)


def bin_path(target: str) -> Path:
    return Path(f"venv/bin/{target}")
