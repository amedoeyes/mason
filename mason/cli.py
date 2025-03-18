import argparse
import sys
from pathlib import Path
from typing import Any, cast

import argcomplete
from argcomplete.completers import ChoicesCompleter

from mason import config
from mason.context import Context
from mason.package import Package, Receipt


def install(args: Any, ctx: Context) -> None:
    if args.update_registries:
        print("Updating registries...")
        ctx.update_registries()

    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if pkg.deprecation:
            raise ValueError(f"Package '{pkg.name}' is deprecated: {pkg.deprecation}")
        print(f"Installing '{name}'...")
        pkg.install()


def uninstall(args: Any, ctx: Context) -> None:
    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if name not in ctx.installed_package_names:
            raise ValueError(f"Package '{name}' is not installed")
        print(f"Uninstalling '{name}'...")
        pkg.uninstall()


def update(ctx: Context) -> None:
    ctx.update_registries()


def upgrade(args: Any, ctx: Context) -> None:
    pkgs_to_upgrade = []

    for name in args.package or ctx.installed_package_names:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if name not in ctx.installed_package_names:
            raise ValueError(f"Package '{name}' is not installed")
        rct = Receipt(pkg)
        if pkg.purl.version != rct.purl.version:
            pkgs_to_upgrade.append((pkg, rct))

    if len(pkgs_to_upgrade) > 0:
        for pkg, rct in pkgs_to_upgrade:
            print(f"{pkg.name} {rct.purl.version} -> {pkg.purl.version}")

        if input("Upgrade? [y/N]: ").strip().lower() == "y":
            for pkg, _ in pkgs_to_upgrade:
                pkg.uninstall()
                pkg.install()
    else:
        print("All packages are up to date")


def list(ctx: Context) -> None:
    for pkg in (cast(Package, ctx.package(p)) for p in ctx.installed_package_names):
        print(f"{pkg.name}@{pkg.purl.version}")


def search(args: Any, ctx: Context) -> None:
    def match(package: Package):
        return (
            (not args.category or any(args.category.casefold() == c.casefold() for c in package.categories))
            and (
                not args.language
                or (package.languages and any(args.language.casefold() == l.casefold() for l in package.languages))
            )
            and (args.query in package.name or args.query in package.description)
        )

    for pkg in ctx.packages:
        if not match(pkg):
            continue
        print(f"{pkg.name} {pkg.purl.version}")
        if pkg.deprecation:
            print(f"    Deprecation: {pkg.deprecation}")
        print(f"    Description: {pkg.description}")
        print(f"    Homepage: {pkg.homepage}")
        print(f"    Categories: {', '.join(pkg.categories)}")
        if pkg.languages:
            print(f"    Languages: {', '.join(pkg.languages)}")
        print(f"    Licenses: {', '.join(pkg.licenses)}")
        print()


def main():
    try:
        for dir in [
            config.data_dir,
            config.registries_dir,
            config.packages_dir,
            config.bin_dir,
            config.share_dir,
            config.opt_dir,
        ]:
            dir.mkdir(parents=True, exist_ok=True)

        ctx = Context()

        def formatter(prog):
            return argparse.HelpFormatter(prog, width=80, max_help_position=1000)

        parser = argparse.ArgumentParser(formatter_class=formatter)
        parser.set_defaults(func=lambda _: None)

        subparsers = parser.add_subparsers()

        parser_install = subparsers.add_parser("install", help="install packages", formatter_class=formatter)
        parser_install.set_defaults(func=lambda args: install(args, ctx))
        parser_install.add_argument("-u", "--update-registries", action="store_true", help="update registries")
        parser_install.add_argument("package", nargs="+").completer = ChoicesCompleter(ctx.package_names)

        parser_uninstall = subparsers.add_parser("uninstall", help="uninstall packages", formatter_class=formatter)
        parser_uninstall.set_defaults(func=lambda args: uninstall(args, ctx))
        parser_uninstall.add_argument("package", nargs="+").completer = ChoicesCompleter(ctx.installed_package_names)

        parser_upgrade = subparsers.add_parser("upgrade", help="upgrade packages", formatter_class=formatter)
        parser_upgrade.set_defaults(func=lambda args: upgrade(args, ctx))
        parser_upgrade.add_argument("package", nargs="*").completer = ChoicesCompleter(ctx.installed_package_names)

        parser_update = subparsers.add_parser("update", help="update repositories", formatter_class=formatter)
        parser_update.set_defaults(func=lambda _: update(ctx))

        parser_list = subparsers.add_parser("list", help="list installed packages", formatter_class=formatter)
        parser_list.set_defaults(func=lambda _: list(ctx))

        parser_search = subparsers.add_parser("search", help="search packages", formatter_class=formatter)
        parser_search.set_defaults(func=lambda args: search(args, ctx))
        parser_search.add_argument("query", nargs="?", default="")
        parser_search.add_argument(
            "-c",
            "--category",
            choices=["dap", "formatter", "linter", "lsp"],
            metavar="CATEGORY",
            help="specify category for search",
        )
        parser_search.add_argument("-l", "--language", metavar="language", help="specify language for search")

        argcomplete.autocomplete(parser)

        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(1)

        args = parser.parse_args()

        args.func(args)

    except Exception as e:
        print(f"{Path(sys.argv[0]).name}: {e}")
    except KeyboardInterrupt:
        pass
