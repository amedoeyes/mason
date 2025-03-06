import os
from pathlib import Path

from mason.utility import select_by_os

default_data_dir = select_by_os(
    unix=Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local/share")) / "mason",
    windows=Path(os.getenv("APPDATA", Path.home() / "AppData/Roaming")) / "mason",
)

data_dir = Path(os.getenv("MASON_DATA_DIR", default_data_dir))
registries_dir = data_dir / "registries"
packages_dir = data_dir / "packages"
bin_dir = data_dir / "bin"
share_dir = data_dir / "share"
opt_dir = data_dir / "opt"

registry_repo = os.getenv("MASON_REGISTRY_REPO", "mason-org/mason-registry")
registry_path = registries_dir / "github" / registry_repo / "registry.json"
