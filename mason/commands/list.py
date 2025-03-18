from typing import cast
from mason.context import Context
from mason.package import Package


def list(ctx: Context) -> None:
    for pkg in (cast(Package, ctx.package(p)) for p in ctx.installed_package_names):
        print(f"{pkg.name}@{pkg.purl.version}")
