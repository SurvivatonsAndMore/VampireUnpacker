import subprocess
from typing import Final

from Source.Config.config import Config, CfgKey

UNPACKER_VERSION: Final[tuple[int, int, int]] = (1, 0, 2)

RIPPER_VERSION_MINIMAL: Final[tuple[int, int, int]] = (2, 0, 0)

def get_ripper_version() -> tuple[int, int, int] | None:
    ripper = ""
    try:
        ripper = next(Config[CfgKey.RIPPER].rglob("AssetRippe*.exe"))
    except StopIteration:
        pass

    if not ripper:
        return None

    result = subprocess.run([ripper, "--version"], capture_output=True, text=True)
    result = result.stdout.strip().split(" ")[1].split("+")[0]
    return tuple(map(int, result.split(".")))


def version_to_str(ver: tuple[int, ...]) -> str:
    return '.'.join(map(str, ver))
