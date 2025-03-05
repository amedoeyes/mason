from pathlib import Path
import subprocess

import requests
from mason.package import Package
from mason.utility import download_file, extract_file, is_extractable


def download_release(repo: str, asset: str, version="latest", out_path=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"
    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    response.raise_for_status()
    download_link = next((a["browser_download_url"] for a in response.json()["assets"] if a["name"] == asset), None)
    if not download_link:
        raise ValueError(f"Asset '{asset}' not found in release '{version}'")
    download_file(download_link, out_path / asset)


def install(pkg: Package) -> None:
    repo = f"{pkg.purl.namespace}/{pkg.purl.name}"
    if pkg.files:
        for f in pkg.files:
            asset_path = Path(f)
            out_path = Path(".")
            match f.split(":", 1):
                case [ref, dist] if dist.endswith("/"):
                    out_path = Path(dist)
                    out_path.mkdir(parents=True, exist_ok=True)
                    download_release(repo, ref, pkg.purl.version, out_path)
                    asset_path = out_path / ref
                case [ref, dist]:
                    download_release(repo, ref, pkg.purl.version)
                    asset_path = Path(ref).replace(dist)
                case _:
                    download_release(repo, f, pkg.purl.version)
            if is_extractable(asset_path):
                extract_file(asset_path, out_path)
    else:
        if (pkg.dir / ".git").exists():
            subprocess.run(["git", "fetch", "--depth=1", "--tags", "origin", pkg.purl.version], check=True)
            subprocess.run(["git", "reset", "--hard", pkg.purl.version], check=True)
        else:
            subprocess.run(
                ["git", "clone", "--depth=1", f"https://github.com/{repo}.git", "--branch", pkg.purl.version, "."],
                check=True,
            )
