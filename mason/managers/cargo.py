from pathlib import Path
import platform
import subprocess
from mason.package import Package


def install(pkg: Package) -> None:
    cmd = ["cargo", "install", "--root", "."]
    if pkg.params:
        if repo_url := pkg.params.get("repository_url"):
            cmd += ["--git", repo_url]
            cmd += ["--rev" if pkg.params.get("rev") == "true" else "--tag", pkg.version]
        else:
            cmd += ["--version", pkg.version]
        if features := pkg.params.get("features"):
            cmd += ["--features", features]
        if pkg.params.get("locked") == "true":
            cmd.append("--locked")
    cmd.append(pkg.package)
    subprocess.run(cmd, check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"bin/{target}")
    else:
        return Path(f"bin/{target}.exe")
