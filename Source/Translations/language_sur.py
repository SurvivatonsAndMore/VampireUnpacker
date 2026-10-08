import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Utility.constants import I2_LANGUAGES, COMPOUND_DATA_TYPE, COMPOUND_DATA, PROGRESS_BAR_FUNC_TYPE, \
    PROGRESS_BAR_FUNC_DEFAULT, TRANSLATIONS_FOLDER, GENERATED, SPLIT
from Source.Utility.special_classes import Objectless
from Source.Utility.timer import Timeit
from Source.Translations.language_utils import Lang
from Source.Utility.unity_parser import UnityDoc

VALUE = "_value"


class LangTypeSur(Enum):
    ACHIEVEMENT = "achievementLang"
    ADVENTURE = "adventureLang"
    ARCANA = "arcanaLang"
    CHARACTER = "characterLang"
    ENEMIES = "enemiesLang"
    EVENT = "eventLang"
    GLOSSARY = "Glossary"
    ITEM = "itemLang"
    GENERAL = "lang"
    MUSIC = "musicLang"
    ONLINE = "onlineLang"
    PARTY = "partyLang"
    POWER_UP = "powerUpLang"
    PROGRESS = "progressLang"
    SECRET = "secretLang"
    SKIN = "skinLang"
    STAGE = "stageLang"
    WEAPON = "weaponLang"
    XBOX_ACH = "Xbox Achievements"

    # WHRS
    ACHIEVEMENT2 = "achivementLang" # typo
    PS_ACH = "PlaystationAchievements"
    STATUS = "statusLang"
    STATUS2 = "statusLAng" # typo
    PAINT_POT = "paintPotLang"
    DAMAGE = "damageLang"
    DIALOGUE = "dialogue"


    NONE = None

    @classmethod
    def get_all_types(cls) -> set["LangTypeSur"]:
        return {*cls}.difference({cls.NONE})


def get_lang_value(data: dict, *keys) -> Any | None:
    d = data
    for key in keys:
        d = d.get(key)
        if d is None:
            return None
    return d.get(VALUE)


class LangFile:
    __lang_type: LangTypeSur | COMPOUND_DATA_TYPE
    __data: dict[str, Any] | None = None
    __lang_data: dict[Lang, dict[str, Any]] | None = None
    __raw_text: str | None = None
    __json_text: str | None = None

    def __init__(self, lang_type: LangTypeSur | COMPOUND_DATA_TYPE, data: dict[str, Any] | None = None,
                 raw_text: str | None = None):
        self.__lang_type = lang_type
        if data:
            self.__data = data
        elif raw_text:
            # Raw text in yaml
            self.__raw_text = raw_text

    def __load(self):
        if self.__data and not self.__raw_text:
            self.__raw_text = self.__json_text = json.dumps(self.__data, ensure_ascii=False, indent=2)
        elif self.__raw_text and not self.__data:
            self.__data = UnityDoc.yaml_parse_text_smart(self.__raw_text).entries[0].data
            self.__json_text = json.dumps(self.__data, ensure_ascii=False, indent=2)

    def __load_inverse(self):
        self.__load()
        if not self.__lang_data:
            self.__lang_data = gen_inverse_dict(self.__lang_type)

    def data(self) -> dict[str, Any]:
        self.__load()
        return self.__data

    def raw_text(self) -> str:
        self.__load()
        return self.__raw_text

    def json_text(self) -> str:
        self.__load()
        return self.__json_text

    def lang_data(self) -> dict[Lang, dict[str, Any]]:
        assert self.__lang_type != COMPOUND_DATA
        self.__load_inverse()
        return self.__lang_data

    def get_lang(self, lang: Lang) -> dict[str, Any]:
        return self.lang_data()[lang]


class LangHandler(Objectless):
    _full_file: LangFile = None
    _loaded_data: dict[LangTypeSur, LangFile] = {}

    @classmethod
    def __load_i2languages(cls):
        if cls._full_file:
            return

        timeit = Timeit()
        print("Loading I2Languages")

        i2lang = MetaDataHandler.get_path_by_name_no_meta(I2_LANGUAGES)
        assert i2lang

        with open(i2lang, "r", encoding="utf-8") as f:
            cls._full_file = LangFile(COMPOUND_DATA, raw_text=f.read())

        print(f"Loaded I2Languages {timeit!r}")

    @classmethod
    def __load_separate(cls):
        cls.__load_i2languages()

        if cls._loaded_data:
            return

        timeit = Timeit()
        print("Initializing lang files")

        loaded_data: dict[LangTypeSur, Any] = {lang_type: {} for lang_type in LangTypeSur.get_all_types()}
        full_data = cls._full_file.data()["mSource"]["mTerms"]

        for i, lang_entry in enumerate(full_data):
            lang_type_str, *full_key = lang_entry["Term"].replace("{", "").replace("}", "/").split("/")
            lang_type = LangTypeSur(lang_type_str) if lang_type_str in LangTypeSur else LangTypeSur.NONE

            if lang_type == LangTypeSur.NONE:
                print(f"Skipping lang_type={lang_type_str} ({full_key}). "
                      "This message most likely means that new LangType was added", file=sys.stderr)
                continue

            values = loaded_data[lang_type]
            for key in full_key:
                if key not in values:
                    values[key] = {}
                values = values[key]
            values[VALUE] = [
                e.replace(" ", " ").strip() if isinstance(e, str) else e
                for e in lang_entry["Languages"]
            ]

        for lang_type, values in loaded_data.items():
            if values:
                cls._loaded_data[lang_type] = LangFile(lang_type, data=values)

        print(f"Initialized lang files {timeit!r}")

    @classmethod
    def get_i2language(cls) -> LangFile:
        cls.__load_i2languages()
        return cls._full_file

    @classmethod
    def get_lang_list(cls) -> list[Lang]:
        i2l = cls.get_i2language().data()
        langs = [Lang(e['Code']) for e in i2l["mSource"]["mLanguages"]]
        return langs

    @classmethod
    def get_lang_file(cls, lang_type: LangTypeSur) -> LangFile | None:
        cls.__load_separate()
        return cls._loaded_data.get(lang_type)


def gen_changed_list_to_dict(lang_file: LangFile) -> dict[str, Any]:
    lang_list = LangHandler.get_lang_list()

    out_data = {}

    def make_data_recursive(data: dict):
        out_dict = {}
        for k, v in data.items():
            if isinstance(v, list):
                out_dict[k] = dict(zip(lang_list, v))
            elif isinstance(v, dict):
                out_dict[k] = make_data_recursive(v)
            else:
                assert False
        return out_dict

    for key, val in lang_file.data().items():
        out_data[key] = make_data_recursive(val)

    return out_data


def gen_inverse_dict(lang_type: LangTypeSur, selected_langs: set[int] = None) -> dict[Lang, Any]:
    timeit = Timeit()
    print(f"Generating inverse lang for {lang_type}")

    lang_list = LangHandler.get_lang_list()

    e_lang_list = enumerate(lang_list)
    if selected_langs:
        e_lang_list = [(i, x) for i, x in e_lang_list if i in selected_langs]

    out_data = {}

    def make_data_recursive(data: dict, lang_index: int):
        out_dict = {}
        for k, v in data.items():
            if isinstance(v, list):
                out_dict[k] = v[i]
            elif isinstance(v, dict):
                out_dict[k] = make_data_recursive(v, lang_index)
            else:
                assert False
        return out_dict

    for i, lang in e_lang_list:
        out_data[lang] = {}
        for key, val in LangHandler.get_lang_file(lang_type).data().items():
            out_data[lang][key] = make_data_recursive(val, i)

    print(f"Generated inverse lang for {lang_type} {timeit!r}")

    return out_data


def dump_original_i2l(
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path:
    func_progress_bar_set_percent(0, 1, "Copying I2Languages.assets")
    print("Copying I2Languages.assets")

    _timeit = Timeit()

    save_folder = to_current_game_path(TRANSLATIONS_FOLDER)
    save_folder.mkdir(exist_ok=True, parents=True)

    i2l = LangHandler.get_i2language().raw_text()
    with open((save_folder / I2_LANGUAGES).with_suffix(".yaml"), "w", encoding="utf-8") as f:
        f.write(i2l)

    func_progress_bar_set_percent(1, 1, f"Finished copying I2Languages.assets {_timeit!r}")
    print(f"Finished copying I2Languages.assets {_timeit!r}")
    return save_folder


def dump_json_i2l(
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path:
    func_progress_bar_set_percent(0, 1, "Converting I2Languages to json")
    print("Converting I2Languages to json")

    _timeit = Timeit()

    save_folder = to_current_game_path(TRANSLATIONS_FOLDER) / GENERATED
    save_folder.mkdir(exist_ok=True, parents=True)

    i2l = LangHandler.get_i2language().json_text()
    with open((save_folder / I2_LANGUAGES).with_suffix(".json"), "w", encoding="utf-8") as f:
        f.write(i2l)

    func_progress_bar_set_percent(1, 1, f"Converting I2Languages to json finished {_timeit!r}")
    print(f"Converting I2Languages to json finished {_timeit!r}")
    return save_folder


def get_available_split_types() -> tuple[list[str], list[bool]]:
    """
        Returns:
            Tuple of lists: Names of splits, Bools where language selection available for split.
    """
    return ["Split as is", "Change lang list to dict", "Inverse hierarchy so lang is top key"], [False, False, True]


def get_available_lang_types() -> list[Lang]:
    return LangHandler.get_lang_list()


def dump_split_i2l(
        selected_split_types: list[bool],
        selected_langs: list[Lang] | None = None,
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path:
    def split_func(_index: int, _lang_type: LangTypeSur) -> str | None:
        _lang_file = LangHandler.get_lang_file(_lang_type)

        if _lang_file is None:
            return None

        match _index:
            case 0:
                return _lang_file.json_text()
            case 1:
                return json.dumps(gen_changed_list_to_dict(_lang_file), ensure_ascii=False, indent=2)
            case 2:
                assert selected_langs is not None
                return json.dumps({lang: _lang_file.get_lang(lang) for lang in selected_langs},
                                  ensure_ascii=False, indent=2)

        return None

    split_folder_names = ["LangList", "LangDictionary", "InverseLangDictionary"]

    _timeit = Timeit()
    lang_types = LangTypeSur.get_all_types()
    total_length = len(lang_types) * sum(selected_split_types)
    i = 0

    split_path = to_current_game_path(TRANSLATIONS_FOLDER) / GENERATED / SPLIT

    for split_index, is_selected in enumerate(selected_split_types):
        if not is_selected:
            continue

        print(f"Splitting I2Languages to separate categories. ({split_folder_names[split_index]})")

        save_path = split_path / split_folder_names[split_index]
        save_path.mkdir(parents=True, exist_ok=True)
        for lang_type in lang_types:
            lang_file = split_func(split_index, lang_type)
            if lang_file is not None:
                with open((save_path / str(lang_type.value)).with_suffix(".json"), mode="w", encoding="UTF-8") as f:
                    f.write(lang_file)

            func_progress_bar_set_percent(i := i + 1, total_length, f"{split_folder_names[split_index]} {_timeit!r}")

    _t = f"Finished splitting I2Languages to separate categories. {_timeit!r}"
    func_progress_bar_set_percent(i, total_length, _t)
    print(_t)
    return split_path


def make_meta_file_split_folder_structure() -> Path:
    save_path = to_current_game_path(TRANSLATIONS_FOLDER) / GENERATED / "Metadata.json"
    folder_metadata = [lang_type.value for lang_type in LangTypeSur.get_all_types()]
    save_path.write_text(json.dumps(sorted(folder_metadata), ensure_ascii=False, indent=2))
    return save_path


if __name__ == "__main__":
    # LangHandler.get_i2language().data()
    a = gen_inverse_dict(LangTypeSur.ITEM, {0, 7})
    print(a.keys())
