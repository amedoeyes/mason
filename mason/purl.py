from dataclasses import dataclass, field
from urllib.parse import unquote


@dataclass
class Purl:
    purl: str
    scheme: str = field(init=False, default="")
    type: str = field(init=False, default="")
    namespace: str = field(init=False, default="")
    name: str = field(init=False, default="")
    version: str = field(init=False, default="")
    qualifiers: dict = field(init=False, default_factory=dict)
    subpath: str = field(init=False, default="")

    def __post_init__(self) -> None:
        remainder = self.purl
        if "#" in remainder:
            remainder, subpath = remainder.rsplit("#", 1)
            self.subpath = "/".join([unquote(p) for p in subpath.strip("/").split("/") if p not in ["", ".", ".."]])

        if "?" in remainder:
            remainder, qualifiers_str = remainder.rsplit("?", 1)
            self.qualifiers = {
                k.lower(): unquote(v).split(",") if k == "checksums" else unquote(v)
                for k, v in (p.split("=", 1) for p in qualifiers_str.split("&"))
                if v
            }

        if ":" in remainder:
            scheme, remainder = remainder.split(":", 1)
            self.scheme = scheme.lower()

        remainder = remainder.strip("/")
        if "/" in remainder:
            type, remainder = remainder.split("/", 1)
            self.type = type.lower()

        if "@" in remainder:
            remainder, version = remainder.rsplit("@", 1)
            self.version = unquote(version)

        if "/" in remainder:
            remainder, name = remainder.rsplit("/", 1)
            self.name = unquote(name)
        else:
            self.name = unquote(remainder)
            remainder = ""

        if remainder:
            self.namespace = "/".join([unquote(p) for p in remainder.split("/") if p != ""])
