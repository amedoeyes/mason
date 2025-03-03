from pathlib import Path

import requests
from tqdm import tqdm


def download_file(url: str, out_path: Path) -> None:
    print(f"Downloading '{url}'...")
    with requests.get(url, stream=True) as response:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        with out_path.open("wb") as f, tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024) as progress:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(len(chunk))


def download_github_release(repo: str, asset: str, version="latest", out_path=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"
    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    response.raise_for_status()
    download_link = next((a["browser_download_url"] for a in response.json()["assets"] if a["name"] == asset), None)
    if not download_link:
        raise ValueError(f"Asset '{asset}' not found in release '{version}'")
    download_file(download_link, out_path / asset)
