from __future__ import annotations
import json
import os
import re
from pathlib import Path
import subprocess
import textwrap
from typing import Any, Optional

from jinja2 import Environment

from mason import config
from mason.purl import Purl
from mason.utility import (
    download_file,
    download_github_release,
    extract_file,
    is_extractable,
    is_platform,
    safe_rmtree,
    select_by_os,
)

env = Environment()
env.filters["take_if_not"] = lambda value, cond: value if not cond else None
env.filters["strip_prefix"] = lambda value, prefix: value[len(prefix) :] if value.startswith(prefix) else value
env.globals["is_platform"] = is_platform


_SCRIPT_TEMPLATE = select_by_os(
    unix=textwrap.dedent("""\
        #!/usr/bin/env bash
        {}
        exec {} "$@"
    """),
    windows=textwrap.dedent("""\
        @ECHO off
        {}
        {} %*
    """),
)


_JINJA_SYNTAX_FIX = [
    (re.compile(r"\|\|"), "|"),
    (re.compile(r'strip_prefix\s*\\?"(.*?)\\?"'), r'strip_prefix("\1")'),
]


class Build:
    cmds: list[str]
    env: dict[str, str]

    def __init__(self, data: dict[str, Any]) -> None:
        self.cmds = data["run"].splitlines()
        self.env = data.get("env", {})


class Bin:
    type: Optional[str]
    source: Path
    dist: Path
    target: str

    def __init__(self, source: str, dest: str) -> None:
        self.dest = Path(dest)
        if ":" in source:
            self.type, self.target = source.split(":")
            match self.type:
                case "dotnet" | "exec" | "gem" | "java-jar" | "node" | "php" | "python" | "pyvenv" | "ruby":
                    self.source = select_by_os(
                        unix=self.dest,
                        windows=self.dest.with_suffix(".cmd"),
                    )
                case "cargo":
                    self.source = Path("bin") / select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.exe",
                    )
                case "composer":
                    self.source = Path("vendor/bin") / select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.bat",
                    )
                case "golang":
                    self.source = Path(
                        select_by_os(
                            unix=self.target,
                            windows=f"{self.target}.exe",
                        )
                    )
                case "luarocks":
                    self.source = Path("bin") / select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.bat",
                    )
                case "npm":
                    self.source = Path("node_modules/.bin") / select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.cmd",
                    )
                case "nuget":
                    self.source = select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.exe",
                    )
                case "opam":
                    self.source = Path("bin") / select_by_os(
                        unix=self.target,
                        windows=f"{self.target}.exe",
                    )
                case "pypi":
                    self.source = Path("venv") / select_by_os(
                        unix=Path("bin") / self.target,
                        windows=Path("Scripts") / f"{self.target}.exe",
                    )
                case _:
                    raise Exception(f"Resolver for '{type}' is not implemented")
        else:
            self.type = None
            self.source = Path(source)


class Receipt:
    name: str
    purl: Purl
    bin: dict[str, str]
    share: dict[str, str]
    opt: dict[str, str]

    def __init__(self, pkg: Package) -> None:
        data = json.loads((pkg.dir / "mason-receipt.json").read_bytes())
        self.name = data.get("name", "")
        self.purl = Purl(data.get("primary_source", {}).get("id", ""))
        self.bin = data.get("links", {}).get("bin", {})
        self.share = data.get("links", {}).get("share", {})
        self.opt = data.get("links", {}).get("opt", {})


class Package:
    name: str
    description: str
    homepage: str
    licenses: list[str]
    languages: Optional[list[str]]
    categories: list[str]
    deprecation: Optional[str]
    purl: Purl
    files: Optional[list[str] | dict[str, str]]
    build_info: Optional[Build]
    extra_packages: list[str]
    bin: list[Bin]
    share: dict[str, str]
    opt: dict[str, str]
    dir: Path

    def __init__(self, data: dict[str, Any]) -> None:
        self.name = data["name"]
        self.homepage = data["homepage"]
        self.licenses = data["licenses"]
        self.languages = data.get("languages")
        self.categories = data["categories"]
        self.description = data["description"].replace("\n", " ").strip()
        self.deprecation = data.get("deprecation", {}).get("message")
        self.purl = Purl(data["source"]["id"])
        self.extra_packages = data["source"].get("extra_packages", [])
        self.dir = config.packages_dir / self.name

        for field in ["asset", "download", "build"]:
            for item in items if (items := data["source"].get(field)) and isinstance(items, list) else []:
                targets = item.get("target")
                targets = [targets] if isinstance(targets, str) else targets
                if is_platform(tuple(targets)):
                    data["source"][field] = item
                    break

        data_str = json.dumps(data)
        prev = None
        while prev != data_str:
            prev = data_str
            for pattern, replacement in _JINJA_SYNTAX_FIX:
                data_str = pattern.sub(replacement, data_str)
            data_str = env.from_string(data_str, globals={"version": self.purl.version, **data}).render()

        data = json.loads(data_str)

        files = None
        if asset := data["source"].get("asset"):
            files = asset.get("file")
        elif download := data["source"].get("download"):
            files = download.get("files") or download.get("file")

        self.files = [files] if isinstance(files, str) else files
        self.build = Build(build) if (build := data["source"].get("build")) else None
        self.bin = [Bin(s, d) for d, s in data.get("bin", {}).items()]
        self.share = data.get("share", {})
        self.opt = data.get("opt", {})

    def install(self) -> None:
        try:
            self._download()
            self._build()
            self._write_wrapper_script()
            self._link()
            self._write_receipt()
        except:
            safe_rmtree(self.dir, config.data_dir)
            raise

    def uninstall(self) -> None:
        receipt = Receipt(self)
        for bin in receipt.bin:
            os.remove(config.bin_dir / bin)
        for share in receipt.share:
            os.remove(config.share_dir / share)
        for opt in receipt.opt:
            os.remove(config.opt_dir / opt)
        safe_rmtree(self.dir, config.data_dir)

    def _download(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        prev_dir = os.curdir
        os.chdir(self.dir)

        type = self.purl.type
        namespace = self.purl.namespace
        name = self.purl.name
        version = self.purl.version
        qualifiers = self.purl.qualifiers
        subpath = self.purl.subpath

        def run(cmd: list[str] | str, env: Optional[dict[str, str]] = None) -> None:
            subprocess.run(cmd, env={**os.environ, **(env or {})}, check=True)

        match type:
            case "cargo":
                cmd = ["cargo", "install", "--root", "."]
                if qualifiers:
                    if repo_url := qualifiers.get("repository_url"):
                        cmd += ["--git", repo_url]
                        cmd += ["--rev" if qualifiers.get("rev") == "true" else "--tag", version]
                    else:
                        cmd += ["--version", version]
                    if features := qualifiers.get("features"):
                        cmd += ["--features", features]
                    if qualifiers.get("locked") == "true":
                        cmd.append("--locked")
                cmd.append(name)
                run(cmd)
            case "composer":
                run(["composer", "init", "--no-interaction", "--stability=stable"])
                run(["composer", "require", f"{namespace}/{name}:{version}"])
            case "gem":
                run(
                    [
                        "gem",
                        "install",
                        "--no-user-install",
                        "--no-format-executable",
                        "--install-dir=.",
                        "--bindir=bin",
                        "--no-document",
                        f"{name}:{version}",
                    ],
                    {"GEM_HOME": os.getcwd()},
                )
            case "generic":
                for name, url in (self.files if isinstance(self.files, dict) else {}).items():
                    out_path = Path(name)
                    download_file(url, out_path)
                    if is_extractable(out_path):
                        extract_file(out_path)
            case "github":
                repo = f"{namespace}/{name}"
                if self.files:
                    for f in self.files:
                        asset_path = Path(f)
                        out_path = Path(".")
                        match f.split(":", 1):
                            case [source, dest] if dest.endswith("/"):
                                out_path = Path(dest)
                                out_path.mkdir(parents=True, exist_ok=True)
                                download_github_release(repo, source, version, out_path)
                                asset_path = out_path / source
                            case [source, dest]:
                                download_github_release(repo, source, version)
                                asset_path = Path(source).replace(dest)
                            case _:
                                download_github_release(repo, f, version)
                        if is_extractable(asset_path):
                            extract_file(asset_path, out_path)
                else:
                    if (self.dir / ".git").exists():
                        run(["git", "fetch", "--depth=1", "--tags", "origin", version])
                        run(["git", "reset", "--hard", version])
                    else:
                        run(["git", "clone", "--depth=1", f"https://github.com/{repo}.git", "."])
                        run(["git", "fetch", "--depth=1", "--tags", "origin", version])
                        run(["git", "checkout", version])
            case "golang":
                run(
                    ["go", "install", "-v", f"{namespace}/{name}{f'/{subpath}' if subpath else ''}@{version}"],
                    {**os.environ, "GOBIN": os.getcwd()},
                )
            case "luarocks":
                cmd = ["luarocks", "install", "--tree", os.getcwd()]
                if qualifiers:
                    if repo_url := qualifiers.get("repository_url"):
                        cmd += ["--server", repo_url]
                    if qualifiers.get("dev") == "true":
                        cmd.append("--dev")
                cmd += [name, version]
                run(cmd)
            case "npm":
                Path(".npmrc").write_text("install-strategy=shallow")
                run(["npm", "init", "--yes", "--scope=mason"])
                run(["npm", "install", f"{f'{namespace}/' if namespace else ''}{name}@{version}", *self.extra_packages])
            case "nuget":
                run(["dotnet", "tool", "update", "--tool-path", ".", "--version", version, name])
            case "opam":
                run(["opam", "install", "--destdir=.", "--yes", "--verbose", f"{name}.{version}"])
            case "openvsx":
                for file in self.files or []:
                    out_path = Path(file)
                    download_file(
                        f"https://open-vsx.org/api/{namespace}/{name}/{version}/file/{file}",
                        out_path,
                    )
                    extract_file(out_path)
            case "pypi":
                run(
                    [select_by_os(unix="python3", windows="python"), "-m", "venv", "venv", "--system-site-packages"],
                )
                run(
                    [
                        select_by_os(
                            unix=Path("venv") / "bin" / "python",
                            windows=Path("venv") / "Scripts" / "python.exe",
                        ),
                        "-m",
                        "pip",
                        "--disable-pip-version-check",
                        "install",
                        "--ignore-installed",
                        "-U",
                        f"{name}{f'[{qualifiers["extra"]}]' if 'extra' in qualifiers else ''}=={version}",
                        *self.extra_packages,
                    ],
                )
            case _:
                raise Exception(f"Installer for '{type}' is not implemented")

        os.chdir(prev_dir)

    def _build(self) -> None:
        if self.build:
            prev_dir = os.curdir
            os.chdir(self.dir)
            os.environ["PWD"] = str(self.dir)
            subprocess.run(" && ".join(self.build.cmds), env={**os.environ, **self.build.env}, check=True, shell=True)
            os.chdir(prev_dir)
            os.environ["PWD"] = str(prev_dir)

    def _write_wrapper_script(self) -> None:
        def _write_script(out_path: Path, command: str, env: dict[str, str] | None = None):
            env = env or {}
            (self.dir / out_path).write_text(
                _SCRIPT_TEMPLATE.format(
                    "\n".join([f"{select_by_os(unix='export', windows='SET')} {k}={v}" for k, v in env.items()]),
                    command,
                ),
                encoding="utf-8",
            )

        for bin in self.bin:
            if bin.type:
                match bin.type:
                    case "dotnet":
                        _write_script(bin.source, f'dotnet "{self.dir / bin.target}"')
                    case "exec":
                        _write_script(bin.source, str(self.dir / bin.target))
                    case "gem":
                        _write_script(
                            bin.source,
                            str(self.dir / "bin" / select_by_os(unix=bin.target, windows=f"{bin.target}.bat")),
                            {"GEM_PATH": f"{self.dir}{select_by_os(unix=':$GEM_PATH', windows=';%%GEM_PATH%%')}"},
                        )
                    case "java-jar":
                        _write_script(bin.source, f'java -jar "{self.dir / bin.target}"')
                    case "node":
                        _write_script(bin.source, f'node "{self.dir / bin.target}"')
                    case "php":
                        _write_script(bin.source, f'php "{self.dir / bin.target}"')
                    case "python":
                        _write_script(
                            bin.source, f'{select_by_os(unix="python3", windows="python")} "{self.dir / bin.target}"'
                        )
                    case "pyvenv":
                        _write_script(bin.source, f"{self.dir / 'venv/bin/python'} -m {bin.target}")
                    case "ruby":
                        _write_script(bin.source, f'ruby "{self.dir / bin.target}"')

    def _link(self) -> None:
        def _create_symlink(source: Path, dest: Path) -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                for file in [f for f in source.rglob("*") if f.is_file()]:
                    target = dest / file.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.is_symlink() or target.exists():
                        target.unlink()
                    target.symlink_to(file)
            else:
                if dest.is_symlink():
                    dest.unlink()
                dest.symlink_to(source)

        for bin in self.bin:
            source_path = self.dir / bin.source
            _create_symlink(source_path, config.bin_dir / bin.dest)
            if os.name == "posix":
                source_path.chmod(source_path.stat().st_mode | 0o111)

        for dest, source in self.share.items():
            _create_symlink(self.dir / source, config.share_dir / dest)

        for dest, source in self.opt.items():
            _create_symlink(self.dir / source, config.opt_dir / dest)

    def _write_receipt(self):
        def resolve(source: Path, dest: Path) -> dict[str, str]:
            if (self.dir / source).is_dir():
                return {
                    (dest / file.name).as_posix(): (source / file.name).as_posix()
                    for file in [f for f in source.rglob("*") if f.is_file()]
                }
            else:
                return {dest.as_posix(): source.as_posix()}

        (self.dir / "mason-receipt.json").write_text(
            json.dumps(
                {
                    "name": self.name,
                    "primary_source": {"id": self.purl.purl},
                    "links": {
                        "bin": {b.dest.as_posix(): b.source.as_posix() for b in self.bin},
                        "share": {k: v for d, s in self.share.items() for k, v in resolve(Path(s), Path(d)).items()},
                        "opt": {k: v for d, s in self.opt.items() for k, v in resolve(Path(s), Path(d)).items()},
                    },
                }
            )
        )
