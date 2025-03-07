import json

from mason import config
from mason.purl import Purl


def list() -> None:
    for file in (config.packages_dir).iterdir():
        receipt_json = file / "mason-receipt.json"
        if receipt_json.exists():
            receipt = json.loads(receipt_json.read_bytes())
            purl = Purl(receipt["primary_source"]["id"])
            print(f"{receipt['name']}@{purl.version}")

