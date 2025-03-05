import platform
import subprocess
from pathlib import Path

from mason.package import Package


def install(pkg: Package) -> None:
    cmd = ["cargo", "install", "--root", "."]
    if pkg.purl.qualifiers:
        if repo_url := pkg.purl.qualifiers.get("repository_url"):
            cmd += ["--git", repo_url]
            cmd += ["--rev" if pkg.purl.qualifiers.get("rev") == "true" else "--tag", pkg.purl.version]
        else:
            cmd += ["--version", pkg.purl.version]
        if features := pkg.purl.qualifiers.get("features"):
            cmd += ["--features", features]
        if pkg.purl.qualifiers.get("locked") == "true":
            cmd.append("--locked")
    cmd.append(pkg.purl.name)
    subprocess.run(cmd, check=True)


def bin_path(target: str) -> Path:
    if platform.system() != "Windows":
        return Path(f"bin/{target}")
    else:
        return Path(f"bin/{target}.exe")
