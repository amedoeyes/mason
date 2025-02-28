#!/bin/python3

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests
from jinja2 import Template

MASON_REPO = os.getenv("MASON_REPO", "mason-org/mason-registry")
MASON_CACHE_DIR = Path(
    os.getenv("MASON_CACHE_DIR", os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "mason"))
).expanduser()
MASON_DATA_DIR = Path(
    os.getenv("MASON_DATA_DIR", os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "mason"))
).expanduser()
MASON_BIN_DIR = MASON_DATA_DIR / "bin"
MASON_PACKAGES_DIR = MASON_DATA_DIR / "packages"
MASON_REGISTRY = MASON_CACHE_DIR / "registry.json"


def extract_file(file_path: Path, extract_path=Path(".")) -> None:
    print(f"Extracting {file_path}...")
    match file_path.suffixes[-2:]:
        case [".tar", ".gz"] | [".tgz"]:
            with tarfile.open(file_path, "r:gz") as tar:
                tar.extractall(path=extract_path, filter="data")
        case [".tar"]:
            with tarfile.open(file_path, "r:") as tar:
                tar.extractall(path=extract_path, filter="data")
        case [".gz"]:
            with gzip.open(file_path, "rb") as f_in, open(extract_path / file_path.stem, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        case [".zip"]:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(extract_path)
        case _:
            raise Exception(f"Unsupported file type: {file_path}")


def verify_checksums(checksum_file: Path) -> bool:
    with open(checksum_file, "r") as f:
        try:
            for line in f:
                expected_hash, file = line.split()
                with open(checksum_file.parent / file, "rb") as f:
                    if hashlib.file_digest(f, "sha256").hexdigest() != expected_hash:
                        return False
        except FileNotFoundError:
            return False
    return True


def download_github_release(repo: str, asset: str, version="latest", directory=Path(".")) -> None:
    if version != "latest":
        version = f"tags/{version}"

    response = requests.get(f"https://api.github.com/repos/{repo}/releases/{version}")
    release_data = response.json()

    download_link = next(
        (asset_info["browser_download_url"] for asset_info in release_data["assets"] if asset_info["name"] == asset),
        None,
    )
    if not download_link:
        raise ValueError(f"Asset {asset} not found in release {version}")

    print(f"Downloading {asset}...")
    response = requests.get(
        download_link,
        stream=True,
    )

    with open(Path(directory) / asset, "wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)


def download_registry() -> None:
    checksums_file = MASON_CACHE_DIR / "checksums.txt"
    if checksums_file.exists():
        print("Checking for update...")
    download_github_release(MASON_REPO, "checksums.txt", "latest", MASON_CACHE_DIR)
    if not verify_checksums(checksums_file):
        if not MASON_REGISTRY.exists():
            print("Downloading registry...")
        else:
            print("Updating registry...")
        download_github_release(MASON_REPO, "registry.json.zip", "latest", MASON_CACHE_DIR)
        with zipfile.ZipFile(MASON_CACHE_DIR / "registry.json.zip", "r") as z:
            z.extractall(MASON_CACHE_DIR)
    else:
        print("Registry up-to-date")


def is_current_target(target: str) -> bool:
    system = platform.system().lower()
    arch = platform.machine().lower()

    arch_map = {
        "x86_64": "x64",
        "amd64": "x64",
        "i386": "x86",
        "i686": "x86",
        "arm": "arm",
        "aarch64": "arm64",
        "armv6l": "armv6l",
        "armv7l": "armv7l",
    }

    system_map = {
        "linux": "linux",
        "darwin": "darwin",
        "windows": "win",
    }

    result = subprocess.run(["ldd", "--version"], capture_output=True)
    first_line = str(result.stdout.splitlines()[0])
    libc = ""
    if "musl" in first_line:
        libc = "musl"
    elif "glibc" in first_line or "GNU" in first_line:
        libc = "gnu"

    possible_targets = {system, f"{system_map[system]}_{arch_map[arch]}"}
    possible_targets.add(f"{system_map[system]}_{arch_map[arch]}_{libc}")

    if system in {"linux", "darwin"}:
        possible_targets.add("unix")
    elif system == "windows":
        possible_targets.add("win")

    return target in possible_targets


def convert_to_jinja_syntax(template_str):
    return re.sub(r"\|\|?\s*strip_prefix\s*\\?\"(.*?)\\?\"", r"| replace('\1', '')", template_str)


def process_placeholders(obj, context) -> Any:
    if isinstance(obj, dict):
        return {k: process_placeholders(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [process_placeholders(i, context) for i in obj]
    elif isinstance(obj, str):
        return Template(convert_to_jinja_syntax(obj)).render(context)
    return obj


def install(package_name: str) -> None:
    with open(MASON_REGISTRY, "r") as f:
        packages = json.load(f)

    pkg = next((p for p in packages if p["name"] == package_name), None)
    if not pkg:
        raise Exception(f"package '{package_name}' not found")

    package_dir = MASON_PACKAGES_DIR / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(package_dir)

    source_id = pkg["source"]["id"]
    source_id = source_id[4:].split("/", 1)
    source_id = [source_id[0]] + source_id[1].split("@")
    if "?" in source_id[2]:
        source_id = [source_id[0]] + [source_id[1]] + source_id[2].split("?")
        source_id = [source_id[0]] + [source_id[1]] + [source_id[2]] + [dict([source_id[3].split("=")])]

    type, package, version, args = source_id + [None] * (4 - len(source_id))
    package = unquote(package)

    pkg = process_placeholders(
        pkg,
        {
            "version": version,
            "source": {
                "asset": next(
                    (asset for asset in pkg["source"].get("asset", []) if is_current_target(asset.get("target"))),
                    None,
                )
            },
        },
    )

    match type:
        case "npm":
            subprocess.run(["npm", "install", f"{package}@{version}"])
        case "pypi":
            extra = f"[{args['extra']}]" if args is not None else ""
            subprocess.run(["python", "-m", "venv", "venv"])
            subprocess.run(["./venv/bin/pip", "install", f"{package}{extra}=={version}"])
        case "github":
            file = next(
                (a["file"] for a in pkg["source"]["asset"] if is_current_target(a["target"])),
                None,
            )
            if file is None:
                raise Exception("Could not find asset")
            download_github_release(package, file, version)
            extract_file(Path(file))
        case _:
            raise Exception(f"'{type}' not implemented")

    for key, value in pkg.get("bin", {}).items():
        dist = MASON_BIN_DIR / key
        bin_path = Path()
        if ":" in value:
            type, bin = value.split(":")
            match type:
                case "npm":
                    bin_path = package_dir / f"./node_modules/.bin/{bin}"
                case "pypi":
                    bin_path = package_dir / f"./venv/bin/{bin}"
                case _:
                    raise Exception(f"'{type}' not implemented")
        else:
            bin_path = package_dir / value
        if os.path.lexists(dist) and os.path.islink(dist):
            os.remove(dist)
        os.symlink(bin_path.absolute(), dist)


def search(query: str, category: str | None, language: str | None) -> None:
    with open(MASON_REGISTRY, "r") as f:
        packages = json.load(f)
    for pkg in packages:
        cat = not category or any(category.lower() == cat.lower() for cat in pkg["categories"])
        lang = not language or any(language.lower() == lang.lower() for lang in pkg["languages"])
        name = query in pkg["name"]
        desc = query in pkg["description"]
        if (name or desc) and cat and lang:
            print(pkg["name"])
            print(f"    {pkg['description'].rstrip('\n').replace('\n', ' ')}")
            print(f"    Categories: {', '.join(pkg['categories'])}")
            if len(pkg["languages"]) > 0:
                print(f"    Languages: {', '.join(pkg['languages'])}")
            print(f"    Licenses: {', '.join(pkg['licenses'])}")
            print()
    exit(0)


if __name__ == "__main__":
    try:
        for dir in [MASON_CACHE_DIR, MASON_DATA_DIR, MASON_BIN_DIR, MASON_PACKAGES_DIR]:
            dir.mkdir(parents=True, exist_ok=True)

        if not MASON_REGISTRY.exists():
            download_registry()

        parser = argparse.ArgumentParser(
            formatter_class=lambda prog: argparse.HelpFormatter(
                prog,
                width=80,
                max_help_position=1000,
            )
        )
        parser.add_argument("-i", "--install", metavar="PACKAGE", help="Install a specific package")
        parser.add_argument("-s", "--search", nargs="?", const="", metavar="QUERY", help="Search registry")
        parser.add_argument(
            "-c",
            "--category",
            choices=["dap", "formatter", "linter", "lsp"],
            metavar="CATEGORY",
            help="Specify category for search",
        )
        parser.add_argument("-l", "--language", metavar="LANGUAGE", help="Specify language for search")
        parser.add_argument("--update-registry", action="store_true", help="Update Mason registry")

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        args = parser.parse_args()

        if args.update_registry:
            download_registry()

        if args.search is not None:
            search(args.search, args.category, args.language)

        if args.install:
            install(args.install)
    except Exception as e:
        print(f"{sys.argv[0]}: {e}")
