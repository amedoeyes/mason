from mason.context import Context


def list(ctx: Context) -> None:
    for rct in ctx.receipts:
        print(f"{rct.name}@{rct.purl.version}")
