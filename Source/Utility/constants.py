import sys
from pathlib import Path
from typing import Final, Callable

from Source.Utility.special_classes import Objectless
from Source.Utility.utility import _find_source_folder

IS_DEBUG: Final[bool] = (sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID)) is not None or (
        sys.gettrace() is not None)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    ROOT_FOLDER: Final[Path] = Path(sys._MEIPASS)
    PROGRAM_FOLDER: Final[Path] = ROOT_FOLDER.parent
else:
    _source = _find_source_folder()
    assert _source is not None
    ROOT_FOLDER: Final[Path] = _source.parent.absolute()
    PROGRAM_FOLDER: Final[Path] = ROOT_FOLDER

AUDIO_FOLDER: Final[Path] = ROOT_FOLDER / "Audio"
DATA_FOLDER: Final[Path] = ROOT_FOLDER / "Data"
IMAGES_FOLDER: Final[Path] = ROOT_FOLDER / "Images"
TRANSLATIONS_FOLDER: Final[Path] = ROOT_FOLDER / "Translations"

CONFIG_FOLDER: Final[Path] = ROOT_FOLDER / "Config"
RIPPER_FOLDER: Final[Path] = ROOT_FOLDER / "Ripper"

VAMPIRE_SURVIVORS: Final[str] = "Vampire Survivors"

SOURCE: Final[str] = "Source"
GENERATED: Final[str] = "Generated"
SPLIT: Final[str] = "Split"
TILEMAPS: Final[str] = "_Tilemaps"

RESOURCES: Final[str] = "Resources"
TEXTURE_2D: Final[str] = "Texture2D"
TEXT_ASSET: Final[str] = "TextAsset"
GAME_OBJECT: Final[str] = "GameObject"
PREFAB_INSTANCE: Final[str] = "PrefabInstance"
AUDIO_CLIP: Final[str] = "AudioClip"
MONO_BEHAVIOUR: Final[str] = "MonoBehaviour"
MATERIAL: Final[str] = "Material"

DATA_MANAGER_SETTINGS: Final[str] = "DataManagerSettings"
BUNDLE_MANIFEST_DATA: Final[str] = "BundleManifestData"
VERSION_DATA: Final[str] = "VersionData"

I2_LANGUAGES: Final[str] = "I2Languages"


class _CompoundDataMeta(type(Objectless)):
    value = "Compound Data"

    def __str__(cls) -> str:  return f"{cls.value} (all DLC)"


class COMPOUND_DATA(Objectless, metaclass=_CompoundDataMeta):
    """
    Special constant class for representing aggregated data from every DLC.
    Uses type 'COMPOUND_DATA_TYPE'.
    Cannot be instantiated directly. Should be used as 'COMPOUND_DATA'
    """


COMPOUND_DATA_TYPE = type[COMPOUND_DATA]

PROGRESS_BAR_FUNC_TYPE = Callable[[int | float, int | float], None] | Callable[[int | float, int | float, str], None]
PROGRESS_BAR_FUNC_DEFAULT: Final[PROGRESS_BAR_FUNC_TYPE] = lambda c, t, *s: None


def to_source_path(path: Path) -> Path:
    start = path.parent
    end = path.name
    return start / SOURCE / end


DEFAULT_ANIMATION_FRAME_RATE: Final[int] = 7

## VC
VAMPIRE_CRAWLERS: Final[str] = "Vampire Crawlers"

SHARED_DATA: Final[str] = "Shared Data"

CARD_DATABASE: Final[str] = "CardDatabase"
CARD_GROUP_DATABASE: Final[str] = "CardGroupDatabase"

SPRITE_CLASS_IDS: Final[set[int]] = {28, 213}
AUDIO_CLASS_IDS: Final[set[int]] = {83, 1020}

NOT_UNITY_DATA_CLASS_IDS: Final[set[int]] = {*SPRITE_CLASS_IDS, *AUDIO_CLASS_IDS}
