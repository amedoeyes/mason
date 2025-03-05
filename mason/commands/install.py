import json
import os
from pathlib import Path
import subprocess
import textwrap
from typing import Any, Optional

from mason import config
from mason.package import Package
from mason.utility import download_file, download_github_release, extract_file, is_extractable, select_by_os


def _create_symlink(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        for file in [f for f in source.rglob("*") if f.is_file()]:
            target = dest / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink() or target.exists():
                target.unlink()
            print(f"Linking '{file}' -> '{target}'")
            target.symlink_to(file)
    else:
        if dest.is_symlink():
            dest.unlink()
        print(f"Linking '{dest}' -> '{source}'...")
        dest.symlink_to(source)


def _create_script(name: str, command: str, env: dict[str, str | int] | None = None) -> Path:
    env = env or {}
    bash = textwrap.dedent("""\
        #!/usr/bin/env bash
        {}
        exec {} "$@"
    """)
    batch = textwrap.dedent("""\
        @ECHO off
        {}
        {} %*
    """)

    path = Path(select_by_os(unix=name, windows=f"{name}.cmd"))
    path.write_text(
        select_by_os(unix=bash, windows=batch).format(
            "\n".join([f"{select_by_os(unix='export', windows='SET')} {k}={v}" for k, v in env.items()]),
            command,
        ),
        encoding="utf-8",
    )
    return path


def _run(cmd: list[str] | str, env: Optional[dict[str, str]] = None, shell: bool = False) -> None:
    subprocess.run(cmd, env={**os.environ, **(env or {})}, check=True, shell=shell)


def install(args: Any) -> None:
    packages = json.loads(config.registry_path.read_bytes())

    for name in args.package:
        pkg = next((p for p in packages if p["name"] == name), None)
        if not pkg:
            raise Exception(f"Package '{name}' not found")

        pkg = Package(pkg)
        if pkg.deprecation:
            raise Exception(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")

        pkg.dir.mkdir(parents=True, exist_ok=True)
        os.chdir(pkg.dir)
        os.environ["PWD"] = os.getcwd()

        type = pkg.purl.type
        namespace = pkg.purl.namespace
        name = pkg.purl.name
        version = pkg.purl.version
        qualifiers = pkg.purl.qualifiers
        subpath = pkg.purl.subpath

        print(f"Installing '{type}' package '{name}@{version}'...")

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
                _run(cmd)
            case "composer":
                _run(["composer", "init", "--no-interaction", "--stability=stable"])
                _run(["composer", "require", f"{namespace}/{name}:{version}"])
            case "gem":
                _run(
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
                for name, url in (pkg.files if isinstance(pkg.files, dict) else {}).items():
                    out_path = Path(name)
                    download_file(url, out_path)
                    if is_extractable(out_path):
                        extract_file(out_path)
            case "github":
                repo = f"{namespace}/{name}"
                if pkg.files:
                    for f in pkg.files:
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
                    if (pkg.dir / ".git").exists():
                        _run(["git", "fetch", "--depth=1", "--tags", "origin", version])
                        _run(["git", "reset", "--hard", version])
                    else:
                        _run(["git", "clone", "--depth=1", f"https://github.com/{repo}.git", "--branch", version, "."])
            case "golang":
                _run(
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
                _run(cmd)
            case "npm":
                Path(".npmrc").write_text("install-strategy=shallow")
                _run(["npm", "init", "--yes", "--scope=mason"])
                _run(["npm", "install", f"{name}@{version}", *pkg.extra_packages])
            case "nuget":
                _run(["dotnet", "tool", "update", "--tool-path", ".", "--version", version, name])
            case "opam":
                _run(["opam", "install", "--destdir=.", "--yes", "--verbose", f"{name}.{version}"])
            case "openvsx":
                for file in pkg.files or []:
                    out_path = Path(file)
                    download_file(
                        f"https://open-vsx.org/api/{namespace}/{name}/{version}/file/{file}",
                        out_path,
                    )
                    extract_file(out_path)
            case "pypi":
                _run(
                    [select_by_os(unix="python3", windows="python"), "-m", "venv", "venv", "--system-site-packages"],
                )
                _run(
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
                        *pkg.extra_packages,
                    ],
                )
            case _:
                raise Exception(f"Installer for '{type}' is not implemented")

        if pkg.build:
            print(f"Building '{pkg.name}'...")
            for cmd in pkg.build.cmds:
                print(f"Running '{cmd}'")
                _run(cmd, env={**os.environ, **pkg.build.env}, shell=True)

        for name, path in (pkg.bin or {}).items():
            dest_path = config.bin_dir / name
            bin_path = Path()

            if ":" in path:
                type, target = path.split(":")
                match type:
                    case "cargo":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.exe")
                    case "composer":
                        bin_path = Path("bin") / "vendor" / select_by_os(unix=target, windows=f"{target}.bat")
                    case "dotnet":
                        bin_path = _create_script(name, f'dotnet "{Path(target).absolute()}"')
                    case "exec":
                        bin_path = _create_script(name, str(Path(target).absolute()))
                    case "gem":
                        bin_path = _create_script(
                            name,
                            str(pkg.dir / "bin" / select_by_os(unix=target, windows=f"{target}.bat")),
                            {"GEM_PATH": f"{pkg.dir}{select_by_os(unix=':$GEM_PATH', windows=';%%GEM_PATH%%')}"},
                        )
                    case "golang":
                        bin_path = Path(select_by_os(unix=target, windows=f"{target}.exe"))
                    case "java-jar":
                        bin_path = _create_script(name, f'java -jar "{pkg.dir / target}"')
                    case "luarocks":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.bat")
                    case "node":
                        bin_path = _create_script(name, f'node "{pkg.dir / target}"')
                    case "npm":
                        bin_path = Path("node_modules") / ".bin" / select_by_os(unix=target, windows=f"{target}.cmd")
                    case "nuget":
                        bin_path = select_by_os(unix=target, windows=f"{target}.exe")
                    case "opam":
                        bin_path = Path("bin") / select_by_os(unix=target, windows=f"{target}.exe")
                    case "php":
                        bin_path = _create_script(name, f'php "{pkg.dir / target}"')
                    case "pypi":
                        bin_path = Path("venv") / select_by_os(
                            unix=Path("bin") / target,
                            windows=Path("Scripts") / f"{target}.exe",
                        )
                    case "python":
                        bin_path = _create_script(
                            name,
                            f'{select_by_os(unix="python3", windows="python")} "{pkg.dir / target}"',
                        )
                    case "pyvenv":
                        bin_path = _create_script(name, f"{pkg.dir / 'venv/bin/python'} -m {target}")
                    case "ruby":
                        bin_path = _create_script(name, f'ruby "{pkg.dir / target}"')
                    case _:
                        raise Exception(f"Resolver for '{type}' is not implemented")
                bin_path = pkg.dir / bin_path
            else:
                bin_path = pkg.dir / path

            _create_symlink(bin_path, dest_path)

            if os.name == "posix":
                bin_path.chmod(bin_path.stat().st_mode | 0o111)

        for dest, path in (pkg.share or {}).items():
            _create_symlink(pkg.dir / path, config.share_dir / dest)

        for dest, path in (pkg.opt or {}).items():
            _create_symlink(pkg.dir / path, config.opt_dir / dest)
