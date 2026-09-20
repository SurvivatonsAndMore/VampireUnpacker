import dataclasses
import json
from enum import Enum
from pathlib import Path

from Source.Config.config import Game
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Translations.language_utils import Lang
from Source.Utility.constants import TRANSLATIONS_FOLDER, GENERATED, SHARED_DATA, PROGRESS_BAR_FUNC_TYPE, \
    PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.multirun import map_multithread
from Source.Utility.special_classes import Objectless
from Source.Utility.timer import Timeit
from Source.Utility.unity_parser import UnityDoc, UnityEntry, UnityLocalizedReference


class LangTypeVC(Enum):
    ACHIEVEMENT = "Achievements"
    ARCANA = "Arcanas"
    CARDS = "Cards"
    COMMON = "Common"
    CREDITS = "Credits"
    DUNGEONS = "Dungeons"
    EFFECTS = "Effects"
    GEMS = "Gems"
    GLOBAL_KEYWORDS = "GlobalKeywords"
    MENUS = "Menus"
    POWER_UPS = "PowerUps"
    RELICS = "Relics"


@dataclasses.dataclass
class LangFileVC:
    lang_type: LangTypeVC
    guid: str = None
    name: str = None
    _data: dict[Lang, dict[int, str]] = dataclasses.field(default_factory=dict)
    _key_to_id: dict[str, int] = dataclasses.field(default_factory=dict)
    _paths: dict[Lang, Path] = None
    _raw: dict[Lang, str] = dataclasses.field(default_factory=dict)

    @staticmethod
    def __get_data_from_entry(entry: UnityEntry) -> dict[int, str]:
        data = entry.data.get('m_TableData') or entry.data.get('m_Entries')

        return {lang_ref['m_Id']: (lang_ref.get('m_Localized') or lang_ref.get('m_Key')) for lang_ref in data}

    def __load_lang(self, lang: Lang) -> UnityEntry | None:
        if lang in self._data:
            return

        with open(self._paths[lang], "r", encoding="UTF-8") as _f:
            text = _f.read()

        entry = UnityDoc.yaml_parse_text_smart(text).entry
        self._data[lang] = self.__get_data_from_entry(entry)
        self._raw[lang] = text
        return entry

    def __post_init__(self):
        langs_list = [f" {SHARED_DATA}", *[f"_{l.value}" for l in Lang.get_vc()]]
        langs_list = [f"{self.lang_type.value}{l}" for l in langs_list]
        paths = list(map(MetaDataHandler.get_path_by_name_no_meta, langs_list))
        self._paths = dict(zip([Lang.SHARED_DATA, *Lang.get_vc()], paths))

        shared_entry = self.__load_lang(Lang.SHARED_DATA)
        self._key_to_id = {key: _id for _id, key in self._data[Lang.SHARED_DATA].items()}

        self.name = shared_entry.data.get('m_TableCollectionName')
        self.guid = shared_entry.data.get('m_TableCollectionNameGuidString')
        assert self.guid is not None

    def get(self, lang: Lang) -> dict[int, str]:
        self.__load_lang(lang)
        return self._data[lang]

    def en(self, _id: int) -> str | None:
        return self.get(Lang.EN).get(_id)

    def raw(self, lang: Lang) -> str | None:
        self.__load_lang(lang)
        return self._raw[lang]


class LangHandlerVC(Objectless):
    _data_by_lang: dict[LangTypeVC, LangFileVC] = {}
    _data_loaded: dict[str, LangFileVC] = {}

    @classmethod
    def get_lang_file(cls, lang_type: LangTypeVC) -> LangFileVC:
        if not lang_type in cls._data_by_lang:
            file = LangFileVC(lang_type)
            cls._data_by_lang[lang_type] = file
            cls._data_loaded[file.name] = file
            cls._data_loaded[file.guid] = file

        return cls._data_by_lang.get(lang_type)

    @classmethod
    def get_lang_by_guid(cls, guid: str) -> LangFileVC:
        if not guid in cls._data_loaded:
            map_multithread(cls.get_lang_file, [*LangTypeVC])

        return cls._data_loaded.get(guid)

    @classmethod
    def get_by_loc_ref(cls, loc_ref: UnityLocalizedReference) -> str | None:
        file = cls.get_lang_by_guid(loc_ref.table_guid)
        key_id = loc_ref.key_id

        if not key_id:
            key_id = file._key_to_id.get(loc_ref.key_name)

        return file.en(key_id)

    @classmethod
    def save_raw_langs(cls, lang_types: set[LangTypeVC] = None) -> Path:
        if lang_types is None:
            lang_types = {*LangTypeVC}

        save_folder = to_current_game_path(TRANSLATIONS_FOLDER) / "Raw"
        save_folder.mkdir(parents=True, exist_ok=True)

        for lang_type in lang_types:
            data = cls.get_lang_file(lang_type)

            sf = save_folder / lang_type.value
            sf.mkdir(parents=True, exist_ok=True)

            for lang, path in data._paths.items():
                name = path.with_suffix(".yaml").name

                with open(sf / name, "w", encoding="UTF-8") as _f:
                    print(data.raw(lang), file=_f)

        return save_folder

    @classmethod
    def save_dict_langs(cls, lang_types: set[LangTypeVC] = None) -> Path:
        if lang_types is None:
            lang_types = {*LangTypeVC}

        save_folder = to_current_game_path(TRANSLATIONS_FOLDER) / GENERATED / "LangDictionary"
        save_folder.mkdir(parents=True, exist_ok=True)

        for lang_type in lang_types:
            data = cls.get_lang_file(lang_type)

            shared = data.get(Lang.SHARED_DATA)

            full_data = {
                name: {
                    lang.value: data.get(lang).get(_id)
                    for lang in Lang.get_vc()
                }
                for _id, name in shared.items()
            }

            with open(save_folder / f"{lang_type.value}.json", "w", encoding="UTF-8") as _f:
                print(json.dumps(full_data, ensure_ascii=False, indent=2), file=_f)

        return save_folder


def save_all_langs(func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT):
    assert MetaDataHandler.loaded_game == Game.VC, f"Loaded wrong metadata ({MetaDataHandler.loaded_game}). Need {Game.VC}"

    print("Started getting Translation files for VC")
    tt = Timeit()

    func_progress_bar_set_percent(0, 2)
    save_path = LangHandlerVC.save_raw_langs()
    func_progress_bar_set_percent(1, 2)
    LangHandlerVC.save_dict_langs()
    func_progress_bar_set_percent(2, 2)

    print(f"Finished getting Translation files for VC {tt!r}")

    return save_path.parent


if __name__ == "__main__":
    MetaDataHandler.load(Game.VC)
    save_all_langs()
