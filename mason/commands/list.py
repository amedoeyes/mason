from mason.context import Context
from mason.purl import Purl


def list(ctx: Context) -> None:
    for name, receipt in ctx.receipts.items():
        purl = Purl(receipt["primary_source"]["id"])
        print(f"{name}@{purl.version}")

