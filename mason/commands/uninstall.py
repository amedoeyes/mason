from typing import Any

from mason.context import Context


def uninstall(args: Any, ctx: Context) -> None:
    for name in args.package:
        pkg = ctx.package(name)
        if not pkg:
            raise ValueError(f"Package '{name}' not found")
        if name not in ctx.installed_package_names:
            raise ValueError(f"Package '{name}' is not installed")
        print(f"Uninstalling '{name}'...")
        pkg.uninstall()
