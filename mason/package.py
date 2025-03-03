import json
import platform
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

from jinja2 import Environment

from mason import config


def _is_platform(target: str | list[str]) -> bool:
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
    libc = None
    if system == "linux":
        result = subprocess.run(["ldd", "--version"], capture_output=True, text=True)
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        libc = "musl" if "musl" in first_line else "gnu" if any(s in first_line for s in {"glibc", "GNU"}) else None
    possible_targets = [
        f"{system_map[system]}_{arch_map[arch]}",
        "win" if system == "windows" else "unix",
    ]
    if system == "linux":
        possible_targets.append("linux")
        possible_targets.append(f"{system_map[system]}_{arch_map[arch]}_{libc if libc else 'gnu'}")
    return any(t in possible_targets for t in (target if isinstance(target, list) else [target]))


def _to_jinja_syntax(s):
    s = re.sub(r"\|\|", "|", s)
    s = re.sub(r'strip_prefix\s*\\?"(.*?)\\?"', r'strip_prefix("\1")', s)
    return s


@dataclass
class Build:
    cmds: list[str]
    env: dict[str, str]

    def __init__(self, data: Any) -> None:
        self.cmds = data["run"].splitlines()
        self.env = data.get("env", {})


@dataclass()
class Package:
    name: str
    description: str
    homepage: str
    licenses: list[str]
    languages: Optional[list[str]]
    categories: list[str]
    deprecation: Optional[str]
    manager: str
    package: str
    version: str
    params: dict[str, str]
    files: Optional[list[str] | dict[str, str]]
    build: Optional[Build]
    extra_packages: list[str]
    bin: Optional[dict[str, str]]
    share: Optional[dict[str, str]]
    dir: Path

    def __init__(self, data: Any) -> None:
        self.name = data["name"]
        self.homepage = data["homepage"]
        self.licenses = data["licenses"]
        self.languages = data["languages"]
        self.categories = data["categories"]
        self.description = data["description"].replace("\n", " ").strip()
        self.deprecation = data.get("deprecation", {}).get("message")
        self.manager, rest = data["source"]["id"][4:].split("/", 1)
        self.package, rest = rest.split("@", 1)
        self.package = unquote(self.package)
        self.params = {}
        if "?" in rest:
            self.version, rest = rest.split("?", 1)
            self.params = {k: v for param in rest.split("&") for k, v in [param.split("=", 1)]}
        elif "#" in rest:
            self.version, rest = rest.split("#", 1)
            self.package += f"/{rest}"
        else:
            self.version = rest
        self.version = unquote(self.version)
        self.extra_packages = data["source"].get("extra_packages", [])
        self.dir = config.packages_dir / self.name

        env = Environment()
        env.filters["take_if_not"] = lambda value, cond: value if not cond else None
        env.filters["strip_prefix"] = lambda value, prefix: value[len(prefix) :] if value.startswith(prefix) else value
        env.globals["is_platform"] = _is_platform
        env.globals["version"] = self.version

        asset = data["source"].get("asset")
        if isinstance(asset, list):
            data["source"]["asset"] = next((a for a in asset if _is_platform(a.get("target"))), None)

        download = data["source"].get("download")
        if isinstance(download, list):
            data["source"]["download"] = next((a for a in download if _is_platform(a.get("target"))), None)

        build = data["source"].get("build")
        if isinstance(build, list):
            data["source"]["build"] = next((a for a in build if _is_platform(a.get("target"))), None)

        env.globals.update(data)

        data_str = json.dumps(data)
        data_str = env.from_string(_to_jinja_syntax(data_str)).render()
        data_str = env.from_string(_to_jinja_syntax(data_str)).render()
        data = json.loads(data_str)

        source = data["source"]

        if asset := source.get("asset"):
            files = asset.get("file")
            self.files = [files] if isinstance(files, str) else files
        elif download := source.get("download"):
            self.files = download.get("files") or [download.get("file")]
        else:
            self.files = None

        self.build = Build(build) if (build := source.get("build")) else None

        self.bin = data.get("bin")
        self.share = data.get("share")
