import os
from pathlib import Path

registry_repo = os.getenv("MASON_REGISTRY_REPO", "mason-org/mason-registry")
cache_dir = Path(
    os.getenv("MASON_CACHE_DIR", os.path.join(os.getenv("XDG_CACHE_HOME", "~/.cache"), "mason"))
).expanduser()
data_dir = Path(
    os.getenv("MASON_DATA_DIR", os.path.join(os.getenv("XDG_DATA_HOME", "~/.local/share"), "mason"))
).expanduser()
bin_dir = data_dir / "bin"
share_dir = data_dir / "share"
opt_dir = data_dir / "opt"
packages_dir = data_dir / "packages"
registry_path = cache_dir / "registry.json"
