from mason.context import Context


def list(ctx: Context) -> None:
    for pkg in ctx.installed_packages:
        print(f"{pkg.name}@{pkg.purl.version}")
