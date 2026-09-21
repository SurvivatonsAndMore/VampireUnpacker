from __future__ import annotations

import dataclasses
import itertools
import json
import tkinter as tk
from dataclasses import dataclass
from enum import Enum, StrEnum
from pathlib import Path
from tkinter import ttk
from tkinter.filedialog import askdirectory
from tkinter.messagebox import showerror, showinfo
from typing import Final, Callable

from Source.Utility.constants import CONFIG_FOLDER, ROOT_FOLDER
from Source.Utility.special_classes import Objectless

ASSETS = "Assets"
PROJECT_SETTINGS = "ProjectSettings"
EXPORTED_PROJECT = "ExportedProject"


class CfgKey(StrEnum):
    RIPPER = "AS_RIPPER"

    ASSETS_VS = "ASSETS_VS"
    STEAM_VS = "STEAM_VS"
    DATA_VS = "DATA_VS"

    ASSETS_VC = "ASSETS_VC"
    STEAM_VC = "STEAM_VC"
    DATA_VC = "DATA_VC"

    ASSETS_WRHS = "ASSETS_WRHS"
    STEAM_WRHS = "STEAM_WRHS"
    DATA_WRHS = "DATA_WRHS"

    ASSETS_JJKRS = "ASSETS_JJKRS"
    STEAM_JJKRS = "STEAM_JJKRS"
    DATA_JJKRS = "DATA_JJKRS"

    def __str__(self):
        return self.value

    @classmethod
    def get_non_path_keys(cls) -> set[CfgKey]:
        return set()

    @classmethod
    def get_assets_keys(cls) -> list[CfgKey]:
        return [cls.ASSETS_VS, cls.ASSETS_VC, cls.ASSETS_WRHS, cls.ASSETS_JJKRS]

    @classmethod
    def get_steam_path_keys(cls) -> list[CfgKey]:
        return [cls.STEAM_VS, cls.STEAM_VC, cls.STEAM_WRHS, cls.STEAM_JJKRS]

    @classmethod
    def get_data_path_keys(cls) -> list[CfgKey]:
        return [cls.DATA_VS, cls.DATA_VC, cls.DATA_WRHS, cls.DATA_JJKRS]

    @classmethod
    def get_path_keys(cls) -> set[CfgKey]:
        return {*cls}.difference(cls.get_non_path_keys())


@dataclass(order=True, unsafe_hash=True)
class GameType:
    appid: int
    steam_folder: CfgKey
    assets_folder: CfgKey
    data_folder: CfgKey


class Game(Enum):
    VS = GameType(1794680, CfgKey.STEAM_VS, CfgKey.ASSETS_VS, CfgKey.DATA_VS)
    VC = GameType(3265700, CfgKey.STEAM_VC, CfgKey.ASSETS_VC, CfgKey.DATA_VC)
    WRHS = GameType(3669620, CfgKey.STEAM_WRHS, CfgKey.ASSETS_WRHS, CfgKey.DATA_WRHS)
    JJKRS = GameType(4753290, CfgKey.STEAM_JJKRS, CfgKey.ASSETS_JJKRS, CfgKey.DATA_JJKRS)

    SPECIAL = GameType(-1, CfgKey.STEAM_VS, CfgKey.ASSETS_VS, CfgKey.DATA_VS)
    NONE = GameType(-2, CfgKey.STEAM_VS, CfgKey.ASSETS_VS, CfgKey.DATA_VS)

    @classmethod
    def get_all_types(cls) -> set[Game]:
        return {*cls}.difference({cls.SPECIAL, cls.NONE})

    def get_default_dlc(self) -> DLC:
        match self:
            case Game.VS | Game.SPECIAL:
                return DLC.VS
            case Game.VC:
                return DLC.VC
            case Game.WRHS:
                return DLC.WRHS
            case Game.JJKRS:
                return DLC.JJKRS
            case _:
                assert False, "Game enum has no default dlc"

    @classmethod
    def get_game_by_cfgkey(cls, cfgkey: CfgKey) -> Game:
        for game in cls.get_all_types():
            if cfgkey in dataclasses.astuple(game.value):
                return game
        return Game.NONE

    def __str__(self):
        return self.get_default_dlc().value.full_name

    def __lt__(self, other: Game) -> bool:
        return other.value is not None and self.value < other.value


@dataclass(order=True, unsafe_hash=True)
class DLCType:
    index: int
    sorting_index: int
    game: Game
    code_name: str
    full_name: str


class DLC(Enum):
    VS = DLCType(0, 0, Game.VS, "SURVIVORS", "Vampire Survivors")
    MS = DLCType(1, 1, Game.VS, "MOONSPELL", "Legacy of the Moonspell")
    FS = DLCType(2, 3, Game.VS, "FOSCARI", "Tides of the Foscari")
    EM = DLCType(3, 4, Game.VS, "CHALCEDONY", "Emergency Meeting")
    OG = DLCType(4, 5, Game.VS, "FIRST_BLOOD", "Operation Guns")
    OC = DLCType(5, 6, Game.VS, "THOSE_PEOPLE", "Ode to Castlevania")
    ED = DLCType(6, 7, Game.VS, "EMERALDS", "Emerald Diorama")
    AC = DLCType(7, 8, Game.VS, "LEMON", "Ante Chamber")
    BM = DLCType(8, 2, Game.VS, "BLOODMOON", "Legacy of the Bloodmoon")
    # IS = DLCType(99, 99, Game.VS, "-", "-")

    VC = DLCType(100, 0, Game.VC, "CRAWLERS", "Vampire Crawlers")

    WRHS = DLCType(200, 0, Game.WRHS, "WARHAMMER", "Warhammer Survivors")

    JJKRS = DLCType(300, 0, Game.JJKRS, "JJKRS", "JUJUTSU KAISEN RUMBLE: SURVIVATON")

    def __str__(self):
        return self.value.full_name

    def __repr__(self):
        val = self.value
        return f"<{DLC.__name__}.{self.name} - {val.code_name} - {val.full_name}>"

    @classmethod
    def get_all_types(cls) -> list[DLC]:
        dlcs = [*cls]
        return list(sorted(dlcs, key=lambda x: x.value))

    @classmethod
    def get_all_types_by_game(cls, game: Game, is_game_sorting: bool = False) -> list[DLC]:
        dlcs = [c for c in cls if c.value.game == game]
        sorting_f = (lambda x: x.value.sorting_index) if is_game_sorting else (lambda x: x.value.index)
        return list(sorted(dlcs, key=sorting_f))

    @classmethod
    def get(cls, index: int) -> DLC | None:
        _all = cls.get_all_types()
        return _all[index] if index < len(_all) else None


class Config(Objectless):
    __data: dict[CfgKey, Path] = dict()

    _CONFIG_FILE: Final[Path] = CONFIG_FOLDER / "Config.json"

    @classmethod
    def load(cls) -> None:
        cls.__data = cls._get_default_config()
        if not cls._CONFIG_FILE.exists():
            cls._CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        else:
            cls._load_config()
            data, _ = cls._fix_assets_path(cls.__data)
            cls.__data = data

    @classmethod
    def _save_config_file(cls) -> None:
        with open(cls._CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                key.value: str(val) if isinstance(val, Path) else val
                for key, val in cls.__data.items()
                if val != Path()
            }, ensure_ascii=False, indent=2))

    @staticmethod
    def _get_default_config() -> dict[CfgKey, Path]:
        data: dict[CfgKey, Path] = {}
        data = {
            cfg: Path()
            for game in sorted(Game.get_all_types())
            for cfg in dataclasses.astuple(game.value)[1:]
        }

        # data.update({cfg: Path() for cfg in CfgKey.get_steam_path_keys()})
        # data.update({cfg: Path() for cfg in CfgKey.get_assets_keys()})
        # data.update({cfg: Path() for cfg in CfgKey.get_data_path_keys()})

        data[CfgKey.RIPPER] = Path()
        return data

    @classmethod
    def migrate_config_key(cls, key: str) -> str:
        match key:
            case "STEAM_APP":
                return CfgKey.STEAM_VS
            case "VS_ASSETS":
                return CfgKey.ASSETS_VS
            case "VC_ASSETS":
                return CfgKey.ASSETS_VC
            case _:
                return key

    @classmethod
    def _load_config(cls) -> None:
        with open(cls._CONFIG_FILE, "r", encoding="UTF-8") as f:
            try:
                json_file = json.loads(f.read())
            except json.decoder.JSONDecodeError as e:
                print(e)
                json_file = dict()

            data: dict[CfgKey, Path] = dict()
            for key, val in json_file.items():
                key_m = cls.migrate_config_key(key)
                if key_m not in CfgKey:
                    continue
                data[CfgKey(key_m)] = Path(val)

            cls._update_data(data)

    @classmethod
    def _update_data(cls, data: dict[CfgKey, Path]):
        cls.__data.update(data)

    @classmethod
    def get_data(cls) -> dict[CfgKey, Path]:
        Config.load()
        return cls.__data

    def __class_getitem__(cls, item: CfgKey) -> Path:
        return cls.get_data()[item]

    @classmethod
    def assert_key(cls, key: CfgKey):
        i = cls[key]
        assert i is not None and i != Path()

    @classmethod
    def has_valid(cls, key: CfgKey) -> bool:
        i = cls[key]
        return i and i != Path()

    @classmethod
    def get_assets_dir(cls, game: Game) -> Path:
        return cls[game.value.assets_folder] / EXPORTED_PROJECT / ASSETS

    @classmethod
    def get_project_settings_dir(cls, game: Game) -> Path:
        return cls[game.value.assets_folder] / EXPORTED_PROJECT / PROJECT_SETTINGS

    @staticmethod
    def _fix_assets_path(data: dict[CfgKey, Path]) -> tuple[dict[CfgKey, Path], bool]:
        is_changed = False

        for key in CfgKey.get_assets_keys():
            path = Path(data.get(key, ""))
            while EXPORTED_PROJECT in str(path) and ASSETS in str(path):
                is_changed = True
                path = path.parent

            if path.name == EXPORTED_PROJECT:
                is_changed = True
                path = path.parent

            data[key] = path

        return data, is_changed

    @classmethod
    def invoke_config_changer(cls, parent: tk.Tk | None = None):
        Config.load()
        cc = cls.CfgChanger(parent)
        cc.wait_window()

    class CfgChanger(tk.Toplevel):
        def __init__(self, parent):
            super().__init__(parent)
            self.title("Change config")
            # self.geometry("700x600")

            self.variables: dict[CfgKey, tk.StringVar] = dict(zip(
                Config._get_default_config(),
                itertools.cycle((None,))
            ))

            ttk.Label(self, text="Select path where to save ripped assets.").pack()
            ttk.Label(self, text="!! When ripping all data in selected folder WILL BE REMOVED !!").pack()

            ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

            def select_folder(variable: tk.StringVar) -> Callable[[], None]:
                def _in_func():
                    folder = askdirectory(parent=self, initialdir=Path(variable.get()) or ROOT_FOLDER)
                    if folder:
                        variable.set(str(Path(folder)))

                return _in_func

            for key in self.variables.keys():
                if key in CfgKey.get_non_path_keys():
                    continue

                info_text = ""
                game = Game.get_game_by_cfgkey(key)
                if "ASSETS_" in key:
                    info_text = f"Folder with/for ripped data of {game.get_default_dlc().value.full_name}."
                elif "STEAM_" in key:
                    info_text = f"{game.get_default_dlc().value.code_name} steam folder. Folder must contain game executable."
                elif "DATA_" in key:
                    info_text = f"Folder for dumping {game.get_default_dlc().value.code_name} data"

                match key:
                    case CfgKey.RIPPER:
                        info_text = f"Asset Ripper. Folder must contain 'AssetRipper[...].exe'"

                tk.Label(self, text=info_text).pack()

                frame = ttk.Frame(self)
                frame.pack()

                path = Config[key]
                path = "" if path == Path() else str(path)
                self.variables[key] = tk.StringVar(frame, path)

                ttk.Label(frame, text=str(key), anchor="center", width=14).pack(side=tk.LEFT)
                ttk.Entry(frame, textvariable=self.variables[key], width=90).pack(side=tk.LEFT)
                ttk.Button(frame, text="Select folder", command=select_folder(self.variables[key])).pack(side=tk.LEFT)

                if "DATA_" in key:
                    ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

            frame = ttk.Frame(self)
            frame.pack()

            ttk.Button(self, text="Check paths and/or Save", command=self.try_save).pack(pady=5)

        def try_save(self):
            # print({k: v.get() for k, v in self.variables.items()})
            data, is_changed = Config._fix_assets_path(
                {k: Path(v.get()) for k, v in self.variables.items()}
            )

            for key in CfgKey.get_assets_keys():
                self.variables[key].set(str(Path(data.get(key, ""))))

            if is_changed:
                showinfo("Config changed",
                         f"Removed '{EXPORTED_PROJECT}' and '{ASSETS}' from assets paths. Press button again to save.")

            asset_ripper_path = Path(self.variables[CfgKey.RIPPER].get())
            is_asset_ripper = asset_ripper_path == Path() or any(asset_ripper_path.glob("AssetRippe*.exe"))
            if not is_asset_ripper:
                showerror("Error: AssetRipper", "AssetRipper.exe not found in selected folder.")

            steam_path_vs = Path(self.variables[CfgKey.STEAM_VS].get())
            is_steam_path_vs = steam_path_vs == Path() or any(steam_path_vs.glob(r"*Survivors*exe"))
            if not is_steam_path_vs:
                showerror("Error: VampireSurvivors", "Vampire Survivors.exe not found in selected folder.")

            steam_path_vc = Path(self.variables[CfgKey.STEAM_VC].get())
            is_steam_path_vc = steam_path_vc == Path() or any(steam_path_vc.glob(r"*Crawlers*exe"))
            if not is_steam_path_vc:
                showerror("Error: VampireCrawlers", "Vampire Crawlers.exe not found in selected folder.")

            if is_changed or not is_asset_ripper or not is_steam_path_vs or not is_steam_path_vc:
                return

            self.__save()

        def __save(self):
            data = {k: Path(v.get()) for k, v in self.variables.items()}

            Config._update_data(data)
            Config._save_config_file()
            self.destroy()


if __name__ == "__main__":
    Config.invoke_config_changer()
