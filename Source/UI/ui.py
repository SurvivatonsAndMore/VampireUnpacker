import itertools
from os import PathLike
from pathlib import Path
from typing import Iterable

from Source.Config.config import Config, DLC, CfgKey, Game
from Source.Data import game_version, data_vc, data_vs
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Images import transparent_save, image_gen_vs
from Source.Images.image_gen_general import generate_images_by_meta, generate_animation_by_meta
from Source.Translations import language_vc, language_vs
from Source.Utility import image_functions
from Source.Utility.constants import to_source_path, IMAGES_FOLDER, GENERATED, COMPOUND_DATA_TYPE, COMPOUND_DATA, \
    DEFAULT_ANIMATION_FRAME_RATE, PREFAB_INSTANCE, GAME_OBJECT, TILEMAPS
from Source.Utility.popups import ErrorPopup, BasePopup, InfoPopup, WarningPopup
from Source.Ripper import ripper


class UIBase:
    def __init__(self):
        self._title_text = 'Vampire Unpacker'
        self._icon_path = to_source_path(IMAGES_FOLDER) / "Show" / "_Sprite-Atlas Gate.png"

        self._last_loaded_folder: Path | None = None

    @staticmethod
    def ask_open_file_name(title: str = "Select file", initialdir: str | PathLike[str] | None = None,
                           filetypes: Iterable[tuple[str, str | list[str]]] | None = None) -> Path | None:
        raise NotImplementedError()

    @staticmethod
    def ask_open_file_names(title: str = "Select file", initialdir: str | PathLike[str] | None = None,
                            filetypes: Iterable[tuple[str, str | list[str]]] | None = None) -> list[Path] | None:
        raise NotImplementedError()

    @staticmethod
    def ask_yes_no(title: str | None = None, message: str | None = None, **options) -> bool:
        raise NotImplementedError()

    @staticmethod
    def ask_integer(title: str | None,
                    prompt: str,
                    *,
                    initialvalue: int | None = None,
                    minvalue: int | None = None,
                    maxvalue: int | None = None,
                    **options) -> int | None:
        raise NotImplementedError()

    @staticmethod
    def show_info(title: str | None = None, message: str | None = None, **options) -> None:
        raise NotImplementedError()

    @staticmethod
    def show_warning(title: str | None = None, message: str | None = None, **options) -> None:
        raise NotImplementedError()

    @staticmethod
    def show_error(title: str | None = None, message: str | None = None, **options) -> None:
        raise NotImplementedError()

    def show_popup(self, popup: BasePopup) -> None:
        match popup:
            case InfoPopup(t, m):
                self.show_info(t, m)
            case WarningPopup(t, m):
                self.show_warning(t, m)
            case ErrorPopup(t, m):
                self.show_error(t, m)

    def progress_bar_set_percent(self, current: int | float, total: int | float, add_text: str = "") -> None:
        raise NotImplementedError()

    def progress_bar_set_sec(self, seconds: float, add_text: str = "") -> None:
        raise NotImplementedError()

    def check_boxes[T](self, list_to_boxes: list[T], title="", label: str | list[str] = "", width: int = 300) -> \
            list[bool]:
        raise NotImplementedError()

    def buttons_box[T](self, list_to_texts: list[T], title="", label: str | list[str] = "",
                       width: int = 300) -> T | None:
        raise NotImplementedError()

    def open_last_loaded_folder(self) -> None:
        raise NotImplementedError()

    def change_config(self) -> None:
        raise NotImplementedError()

    ###
    @staticmethod
    def get_assets_dir(game: Game) -> Path:
        path = Config.get_assets_dir(game)
        return path if path.exists() else Path()

    def dlc_selector(self, game: Game, allow_compound: bool = False) -> DLC | COMPOUND_DATA_TYPE | None:
        all_dlcs = DLC.get_all_types_by_game(game, is_game_sorting=True)
        if allow_compound:
            all_dlcs.append(COMPOUND_DATA)

        return self.buttons_box(all_dlcs, "Select DLC", "Select DLC from which data file will be selected")

    def game_selector(self) -> Game | None:
        return self.buttons_box(sorted(Game.get_all_types()), "Select Game",
                                "Select Game from which data file will be selected")

    def load_metadata(self):
        selected_game = self.game_selector()
        if not selected_game:
            return

        if Config.has_valid(selected_game.value.assets_folder):
            MetaDataHandler.load(selected_game)
        else:
            _t = f"Not found path to assets folder for {selected_game}"
            print(_t)
            self.show_warning("Warning", _t)

    ###

    def rip_data(self) -> None:
        if not Config[CfgKey.RIPPER]:
            self.show_error("Error", "Not found path to AssetRipper")
            return

        games_list = []
        for g in Game.get_all_types():
            if Config[g.value.steam_folder] != Path():
                games_list.append(g)

        games_list.sort()

        data_from_popup = self.check_boxes(games_list, label="Select Games to rip", title="Select Games")
        if not data_from_popup:
            return

        games_set = {t for i, t in enumerate(games_list) if data_from_popup[i]}
        if not games_set:
            return

        print(f"Started ripping files: {games_set}")

        try:
            ripper.rip_files(games_set)
        except BasePopup as p:
            self.show_popup(p)

        print("Finished ripping files")
        MetaDataHandler.unload()

    @staticmethod
    def create_version_file():
        game_version.load_version_file()

    def unpack_by_meta(self, generate_function):
        selected_game = self.game_selector()
        if not selected_game:
            return

        _start_path = self.get_assets_dir(selected_game)
        start_paths = [_start_path.joinpath("Texture2D"), _start_path]

        while (start_path := start_paths.pop(0)) and not start_path.exists():
            pass

        if not start_paths:
            self.show_warning("Warning", f"Assets folder not found for\n{selected_game}.")
            return

        self.generate_by_meta_selector(start_path, generate_function)

    def unpack_by_meta_from_spritesheets(self, generate_function):
        folder = self.get_assets_dir(Game.VS).joinpath("Resources", "spritesheets")

        if not folder.exists():
            self.show_warning("Warning", "Spritesheets folder for Vampire Survivors does not found.")
            return

        self.generate_by_meta_selector(folder, generate_function)

    def generate_by_meta_selector(self, selecting_path: Path, generate_function):
        full_path = self.ask_open_file_name(
            title='Select a file',
            initialdir=selecting_path,
            filetypes=[('Images', '*.png')]
        )

        if not full_path:
            return

        generate_function(Path(full_path))

    def generate_images_by_meta(self, full_path: Path):
        scale_factor = self.ask_integer("Scale", "Input scale multiplier", initialvalue=1)
        if not scale_factor or scale_factor <= 0: return

        try:
            llf = generate_images_by_meta(
                full_path,
                scale_factor=scale_factor,
                func_progress_bar_set_percent=self.progress_bar_set_percent)
            if llf:
                self._last_loaded_folder = llf
        except BasePopup as p:
            self.show_popup(p)

    def generate_animation_by_meta(self, full_path: Path):
        scale_factor = self.ask_integer("Scale", "Input scale multiplier", initialvalue=1)
        if not scale_factor or scale_factor <= 0: return

        frame_rate = self.ask_integer("Frame rate", "Input frame rate (frames per second)",
                                      initialvalue=DEFAULT_ANIMATION_FRAME_RATE)
        if not frame_rate or frame_rate <= 0: return

        selected_anim_types = self.check_boxes(
            transparent_save.ANIM_SAVE_TYPES,
            label="Select animation extension to use.\n(GIF does not support partial transparency)",
            title="Select anim types")

        try:
            llf = generate_animation_by_meta(
                full_path,
                scale_factor=scale_factor,
                frame_rate=frame_rate,
                selected_anim_types=selected_anim_types,
                func_progress_bar_set_percent=self.progress_bar_set_percent)
            if llf:
                self._last_loaded_folder = llf
        except BasePopup as p:
            self.show_popup(p)

    def get_tilemap(self, selected_game: Game | None = None):
        if selected_game is None or selected_game == Game.NONE:
            return

        is_found = False
        folders = [GAME_OBJECT, PREFAB_INSTANCE]

        start_path = None
        for folder in folders:
            start_path = self.get_assets_dir(selected_game).joinpath(folder)
            if start_path.exists():
                is_found = True
                break

        if not is_found:
            self.show_warning("Error", "Folder with prefabs not found.")
            start_path = Config[selected_game.value.assets_folder]

        tilemap_paths = self.ask_open_file_names(
            title='Select prefab files of tilemap',
            initialdir=start_path,
            filetypes=[('Prefab', '*.prefab')]
        )
        if not tilemap_paths:
            return

        print(f"Selected for generating tilemap: {tilemap_paths!r}")

        from Source.Images import tilemap_gen
        save_folder = None

        is_full_auto = False
        if len(tilemap_paths) > 1:
            is_full_auto = self.ask_yes_no("Generation",
                                           "Selected multiple tilemap prefabs.\nDo you want to automatically generate all tilemaps or manually handle every tilemap?")

        for tilemap_path in tilemap_paths:
            layers_count = tilemap_gen.get_tilemap_layers_count(tilemap_path)

            if layers_count == 0:
                self.show_warning("Warning", f"Not found any tilemap for {tilemap_path.name}.")
                continue

            if not is_full_auto:
                if not self.ask_yes_no("Generation",
                                       f"Found tilemap for {tilemap_path.name}.\nDo you want to generate it?"):
                    continue

            exclude_layers = set()
            if not is_full_auto:
                exclude_data = self.check_boxes(range(layers_count), title="Layers to exclude",
                                                label="Select layers to exclude in generation")
                exclude_layers = set(itertools.compress(range(layers_count), exclude_data))

            save_folder = tilemap_gen.create_tilemap(tilemap_path, exclude_layers,
                                                     func_progress_bar_set_percent=self.progress_bar_set_percent)

        print(f"Finished generating all tilemaps: {[fp.name for fp in tilemap_paths]}")
        self._last_loaded_folder = save_folder

    def create_inverse_tilemap(self):
        selecting_path = to_current_game_path(IMAGES_FOLDER) / GENERATED / TILEMAPS
        while not selecting_path.exists():
            selecting_path = selecting_path.parent

        image_path = self.ask_open_file_name(
            title='Open an image file of tilemap',
            initialdir=selecting_path,
            filetypes=[('Images', '*.png')]
        )

        if not image_path:
            return

        tint_dec_int = self.ask_integer("Enter tint", "Enter tint in form of integer base 10")
        tint = image_functions.get_tint(tint_dec_int)

        is_create = self.ask_yes_no("Create inverse?",
                                    f"Create inverse with {tint=} [ {tint_dec_int} / {hex(tint_dec_int).upper()[2:]} ]")
        if not is_create:
            return

        save_path = image_path.parent / "Inverse"
        save_path.mkdir(exist_ok=True, parents=True)

        self._last_loaded_folder = image_functions.create_tint_image(image_path, save_path, tint,
                                                                     self.progress_bar_set_percent)

    ###

    def get_data_vs_all(self):
        self._last_loaded_folder = data_vs.dump_all_data(self.progress_bar_set_percent)
        data_vs.make_meta_file_folder_structure()

    def get_data_vs_merged(self):
        self._last_loaded_folder = data_vs.dump_merged_data(self.progress_bar_set_percent)

    def get_languages_vs_yaml(self):
        self._last_loaded_folder = language_vs.dump_original_i2l(self.progress_bar_set_percent)

    def get_languages_vs_json(self):
        self._last_loaded_folder = language_vs.dump_json_i2l(self.progress_bar_set_percent)

    def get_languages_vs_split(self):
        available_split_types, lang_splits = language_vs.get_available_split_types()

        selected_split_types = self.check_boxes(available_split_types, title="Select split types",
                                                label="Select types for splitting langs")
        if selected_split_types is None:
            return

        is_lang_select = any(select and lang for select, lang in zip(selected_split_types, lang_splits))

        selected_langs = None
        if is_lang_select:
            available_langs = language_vs.get_available_lang_types()

            selected_langs = self.check_boxes(available_langs,
                                              label="Select languages to include in split files",
                                              title="Select languages")
            selected_langs = [available_langs[i] for i, is_selected in enumerate(selected_langs) if is_selected]

        self._last_loaded_folder = language_vs.dump_split_i2l(selected_split_types, selected_langs,
                                                              self.progress_bar_set_percent)

        language_vs.make_meta_file_split_folder_structure()

    def get_unified_images_vs(self):
        selected_dlc = self.dlc_selector(Game.VS, allow_compound=True)

        if not selected_dlc:
            return

        data_dict = data_vs.get_available_data_by_dlc(selected_dlc)
        data_types = list(sorted(image_gen_vs.get_supported_gen_types().intersection(data_dict.keys()),
                                 key=lambda x: x.value))

        selected_data = self.buttons_box(
            data_types, title="Select data types",
            label=["Select data type which will be used to generate images", f"({selected_dlc!s})"])

        if not selected_data:
            return

        self._last_loaded_folder = image_gen_vs.gen_unified_images(selected_dlc, selected_data,
                                                                   self.progress_bar_set_percent, parent=self)

    def get_unified_audio_vs(self):
        from req_test import check_pydub
        if not check_pydub():
            print("FFmpeg not found")
            self.show_error("Error", "FFmpeg not found")
            return

        import Source.Audio.audio_gen_vs as audio_gen

        save_types_list = audio_gen.AudioSaveType.get()
        selected_save_type = self.check_boxes(save_types_list, title="Select save types",
                                              label="Select audio save types")

        if not selected_save_type:
            return

        save_types_set = {t for i, t in enumerate(save_types_list) if selected_save_type[i]}

        if not save_types_set:
            return

        print(f"Started generating audio: {save_types_set}")

        llf, error = audio_gen.gen_music_tracks(COMPOUND_DATA, save_types_set, self.progress_bar_set_percent)
        if error:
            print(error)
            self.show_error("Error", error)
        else:
            self._last_loaded_folder = llf

    ###

    def get_data_vc_all(self):
        dumpers = data_vc.get_available_dumpers()
        selected = self.check_boxes([d.data_type.value for d in dumpers], title="Select data to dump",
                                    label="Select data to dump")

        if selected is None or not any(selected): return

        self._last_loaded_folder = data_vc.dump_selected_data(selected, self.progress_bar_set_percent)

        data_vc.make_meta_file_folder_structure()

    def get_languages_vc_all(self):
        self._last_loaded_folder = language_vc.save_all_langs(self.progress_bar_set_percent)

    ###
