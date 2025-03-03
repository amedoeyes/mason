import json
import os
import platform
import re
import shlex
import subprocess
from typing import Any, Optional
from urllib.parse import unquote

from jinja2 import Environment


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


class Build:
    cmds: list[list[str]]
    env: dict[str, str]

    def __init__(self, data: Any) -> None:
        self.cmds = [shlex.split(os.path.expandvars(cmd)) for cmd in data["run"].splitlines()]
        self.env = data.get("env", {})

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in vars(self).items())})"


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
    files: Optional[list[str]]
    build: Optional[Build]
    bin: Optional[dict[str, str]]
    share: Optional[dict[str, str]]

    def __init__(self, data: Any) -> None:
        self.name = data["name"]
        self.homepage = data["homepage"]
        self.licenses = data["licenses"]
        self.languages = data["languages"]
        self.categories = data["categories"]
        self.description = data["description"].replace("\n", " ").strip()
        self.deprecation = data["deprecation"]["message"] if "deprecation" in data else None
        self.manager, rest = data["source"]["id"][4:].split("/", 1)
        self.package, rest = rest.split("@", 1)
        self.package = unquote(self.package)
        self.version, rest = (rest.split("?", 1) + [""])[:2]
        self.version = unquote(self.version)
        self.params = {k: v for param in rest.split("&") for k, v in [param.split("=", 1)]} if rest else {}

        env = Environment()
        env.filters["take_if_not"] = lambda value, cond: value if not cond else None
        env.filters["strip_prefix"] = lambda value, prefix: value[len(prefix) :] if value.startswith(prefix) else value
        env.globals["is_platform"] = _is_platform
        env.globals["version"] = self.version

        assets = data["source"].get("asset")
        if isinstance(assets, list):
            data["source"]["asset"] = next((a for a in assets if _is_platform(a.get("target"))), None)

        builds = data["source"].get("build")
        if isinstance(builds, list):
            data["source"]["build"] = next((a for a in builds if _is_platform(a.get("target"))), None)

        env.globals.update(data)

        data_str = json.dumps(data)
        data_str = env.from_string(_to_jinja_syntax(data_str)).render()
        data_str = env.from_string(_to_jinja_syntax(data_str)).render()  # have to do 2 passes because nesting :/
        data = json.loads(data_str)

        self.files = ([f] if isinstance(f, str) else f) if (f := data["source"].get("asset", {}).get("file")) else None
        self.build = Build(b) if (b := data["source"].get("build")) else None
        self.bin = data.get("bin")
        self.share = data.get("share")

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(f'{k}={v!r}' for k, v in vars(self).items())})"
