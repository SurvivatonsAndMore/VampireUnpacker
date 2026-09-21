import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog, messagebox, filedialog, ttk
from typing import Iterable, Callable

from Source.Config.config import Game, Config
from Source.Data.meta_data import MetaDataHandler
from Source.UI.boxes_tkinter import CheckBoxes, ButtonsBox
from Source.UI.ui import UIBase
from Source.Utility.constants import IS_DEBUG, ROOT_FOLDER
from Source.Utility.logger import Logger

_registered_layouts: dict[Game, Callable] = {}


def register_game_layout(game: Game):
    def decorator(func: Callable) -> Callable:
        _registered_layouts[game] = func
        return func

    return decorator


class UITkinter(tk.Tk, UIBase):
    def __init__(self, width=600, height=400):
        sys.stdout = Logger(sys.stdout)
        sys.stderr = Logger(sys.stderr)
        if IS_DEBUG: print(f"{IS_DEBUG = }\n")

        ###
        UIBase.__init__(self)
        super().__init__()
        ###
        self._pady = 5

        self.minsize(width, height)

        self.title(self._title_text)
        self.iconphoto(True, tk.PhotoImage(file=self._icon_path, master=self))

        self.__update_progress_bar: Callable[[int | float, str, str], None] = lambda x,y,z: None
        self.__update_loaded_metadata: Callable[[Game.VS], None] = lambda x: None

        self._main_frame = ttk.Frame(self)
        self.set_main_layout()

    def set_main_layout(self):
        self.grid_columnconfigure(0, weight=1)

        ###
        _pg_frame = ttk.Frame(self)
        _pg_frame.grid(column=0, row=2, pady=self._pady)

        _progress_bar = ttk.Progressbar(
            _pg_frame,
            orient='horizontal',
            mode='determinate',
            length=300
        )
        _progress_bar_label_above_string = tk.StringVar(name="pg_s_a")
        _progress_bar_label_above = ttk.Label(_pg_frame, textvariable=_progress_bar_label_above_string)
        _progress_bar_label_below_string = tk.StringVar(name="pg_s_b")
        _progress_bar_label_below = ttk.Label(_pg_frame, textvariable=_progress_bar_label_below_string)

        _progress_bar_label_above.grid(column=0, row=0)
        _progress_bar.grid(column=0, row=1)
        _progress_bar_label_below.grid(column=0, row=2)

        def upd_pb(value: int | float, above: str, below: str):
            _progress_bar['value'] = value
            _progress_bar.update()

            _progress_bar_label_above_string.set(above)
            _progress_bar_label_above.update()

            _progress_bar_label_below_string.set(below)
            _progress_bar_label_below.update()

        self.__update_progress_bar = upd_pb
        upd_pb(40, "ABOVE", "BELOW")
        ###

        ###
        _md_frame = ttk.Frame(self)
        _md_frame.grid(column=0, row=3, pady=self._pady)

        _metadata_label_string = tk.StringVar(name="md_s")
        _metadata_label = ttk.Label(_md_frame, textvariable=_metadata_label_string)

        _metadata_label.grid(column=0, row=0)

        def upd_md(text: str):
            _metadata_label_string.set(text)
            _metadata_label.update()

        def after_load(game: Game) -> None:
            match game:
                case Game.NONE:
                    metadata_string = f"Not loaded any metadata"
                case Game.SPECIAL:
                    metadata_string = f"Loaded empty (special) metadata for generating images from meta"
                case _:
                    metadata_string = f"Loaded metadata for {game.get_default_dlc().value.full_name}"

            upd_md(metadata_string)

        self.__update_loaded_metadata = after_load
        after_load(Game.NONE)

        MetaDataHandler.register(MetaDataHandler.Emit.AFTER_LOAD, after_load)
        MetaDataHandler.register(MetaDataHandler.Emit.BEFORE_LOAD,
                                 lambda o, n: upd_md(f"Loading metadata for {n.get_default_dlc().value.full_name}..."))

        ttk.Button(
            _md_frame,
            text="Load Game Metadata",
            command=self.load_metadata,
        ).grid(column=0, row=1)

        ###

        ###
        _config_frame = ttk.Frame(self)
        _config_frame.grid(column=0, row=4, pady=self._pady)

        ttk.Button(
            _config_frame,
            text="Rip data automatically",
            command=self.rip_data
        ).grid(column=0, row=0)

        ttk.Button(
            _config_frame,
            text="Change config",
            command=self.change_config
        ).grid(column=1, row=0)

        ttk.Button(
            _config_frame,
            text="Open last loaded folder",
            command=self.open_last_loaded_folder
        ).grid(column=0, row=1, columnspan=2)
        ###

        ###
        _by_meta_frame = ttk.Frame(self)
        _by_meta_frame.grid(column=0, row=5, pady=self._pady)

        ttk.Button(
            _by_meta_frame,
            text="Select image atlas to unpack images",
            command=lambda: self.unpack_by_meta(self.generate_images_by_meta)
        ).grid(row=0, column=0)

        ttk.Button(
            _by_meta_frame,
            text="... from spritesheets",
            command=lambda: self.unpack_by_meta_from_spritesheets(self.generate_images_by_meta)
        ).grid(row=0, column=1)

        ttk.Button(
            _by_meta_frame,
            text="... from any image",
            command=lambda: self.generate_by_meta_selector(ROOT_FOLDER, self.generate_images_by_meta)
        ).grid(row=0, column=2)

        ttk.Button(
            _by_meta_frame,
            text="Select image atlas to unpack animations",
            command=lambda: self.unpack_by_meta(self.generate_animation_by_meta)
        ).grid(row=1, column=0)

        ttk.Button(
            _by_meta_frame,
            text="... from spritesheets",
            command=lambda: self.unpack_by_meta_from_spritesheets(self.generate_animation_by_meta)
        ).grid(row=1, column=1)

        ttk.Button(
            _by_meta_frame,
            text="... from any image",
            command=lambda: self.generate_by_meta_selector(ROOT_FOLDER, self.generate_animation_by_meta)
        ).grid(row=1, column=2)
        ###

        ###
        self._main_frame.grid(column=0, row=6, pady=self._pady)

        def set_main_frame(game: Game) -> None:
            f = _registered_layouts.get(game, UITkinter.clear_main_frame)
            f(self)

        MetaDataHandler.register(MetaDataHandler.Emit.AFTER_LOAD, set_main_frame)
        ###

    def clear_main_frame(self):
        for child in self._main_frame.winfo_children():
            child.destroy()

    @register_game_layout(Game.VS)
    def set_vs_frame(self):
        self.clear_main_frame()
        main_frame = self._main_frame

        ttk.Button(
            main_frame,
            text="Create Game Version file",
            command=self.create_version_file,
        ).grid(row=0, column=0, pady=self._pady)

        _data_frame = ttk.Frame(main_frame)
        _data_frame.grid(column=0, row=1)

        ttk.Button(
            _data_frame,
            text="Get data",
            command=self.get_data_vs_all
        ).grid(row=0, column=0)

        ttk.Button(
            _data_frame,
            text="Get merged data",
            command=self.get_data_vs_merged
        ).grid(row=0, column=1)

        _lang_frame = ttk.Frame(main_frame)
        _lang_frame.grid(column=0, row=2)

        ttk.Button(
            _lang_frame,
            text="Get language strings file yaml",
            command=self.get_languages_vs_yaml
        ).grid(row=0, column=0)

        ttk.Button(
            _lang_frame,
            text="Get language strings file json",
            command=self.get_languages_vs_json
        ).grid(row=0, column=1)

        ttk.Button(
            _lang_frame,
            text="Get split language strings files",
            command=self.get_languages_vs_split
        ).grid(row=0, column=2)

        _image_frame = ttk.Frame(main_frame)
        _image_frame.grid(column=0, row=3)

        ttk.Button(
            _image_frame,
            text="Get unified images",
            command=self.get_unified_images_vs
        ).grid(row=0, column=0)

        ttk.Button(
            _image_frame,
            text="Get stage tilemap",
            command=lambda: self.get_tilemap(Game.VS)
        ).grid(row=0, column=2)

        ttk.Button(
            _image_frame,
            text="Create inverse tilemap",
            command=self.create_inverse_tilemap
        ).grid(row=0, column=3)

        #
        ttk.Button(
            main_frame,
            text="Get unified audio",
            command=self.get_unified_audio_vs
        ).grid(row=4, column=0)

    @register_game_layout(Game.VC)
    def set_vc_frame(self):
        self.clear_main_frame()
        main_frame = self._main_frame

        ttk.Button(
            main_frame,
            text="Create Game Version file",
            command=self.create_version_file,
        ).grid(column=0, row=0, pady=self._pady)

        ttk.Button(
            main_frame,
            text="Get data",
            command=self.get_data_vc_all
        ).grid(column=0, row=1)

        ttk.Button(
            main_frame,
            text="Get language strings",
            command=self.get_languages_vc_all
        ).grid(column=0, row=2)

    @register_game_layout(Game.WRHS)
    def set_ws_frame(self):
        self.clear_main_frame()
        main_frame = self._main_frame

        _image_frame = ttk.Frame(main_frame)
        _image_frame.grid(column=0, row=0)

        ttk.Button(
            _image_frame,
            text="Get stage tilemap",
            command=lambda: self.get_tilemap(Game.WRHS)
        ).grid(row=0, column=0)

        ttk.Button(
            _image_frame,
            text="Create inverse tilemap",
            command=self.create_inverse_tilemap
        ).grid(row=0, column=1)

    @register_game_layout(Game.JJKRS)
    def set_jjkrs_frame(self):
        self.clear_main_frame()
        main_frame = self._main_frame

        _image_frame = ttk.Frame(main_frame)
        _image_frame.grid(column=0, row=0)

        ttk.Button(
            _image_frame,
            text="Get stage tilemap",
            command=lambda: self.get_tilemap(Game.JJKRS)
        ).grid(row=0, column=0)

        ttk.Button(
            _image_frame,
            text="Create inverse tilemap",
            command=self.create_inverse_tilemap
        ).grid(row=0, column=1)

    @staticmethod
    def ask_open_file_name(title: str = "Select file", initialdir: str | os.PathLike[str] | None = None,
                           filetypes: Iterable[tuple[str, str | list[str]]] | None = None) -> Path | None:
        _path = filedialog.askopenfilename(initialdir=initialdir, title=title, filetypes=filetypes)
        return Path(_path) if _path else None

    @staticmethod
    def ask_open_file_names(title: str = "Select file", initialdir: str | os.PathLike[str] | None = None,
                            filetypes: Iterable[tuple[str, str | list[str]]] | None = None) -> list[Path] | None:
        _paths = filedialog.askopenfilenames(initialdir=initialdir, title=title, filetypes=filetypes)
        return [Path(p) for p in _paths] if _paths else None

    @staticmethod
    def ask_yes_no(title: str | None = None, message: str | None = None, **options) -> bool:
        return tk.messagebox.askyesno(title, message, **options)

    @staticmethod
    def ask_integer(title: str | None,
                    prompt: str,
                    *,
                    initialvalue: int | None = None,
                    minvalue: int | None = None,
                    maxvalue: int | None = None,
                    **options) -> int | None:
        return tk.simpledialog.askinteger(title, prompt, initialvalue=initialvalue, minvalue=minvalue,
                                          maxvalue=maxvalue, **options)

    @staticmethod
    def show_info(title: str | None = None, message: str | None = None, **options) -> None:
        tk.messagebox.showinfo(title, message, **options)

    @staticmethod
    def show_warning(title: str | None = None, message: str | None = None, **options) -> None:
        tk.messagebox.showwarning(title, message, **options)

    @staticmethod
    def show_error(title: str | None = None, message: str | None = None, **options) -> None:
        tk.messagebox.showerror(title, message, **options)

    def progress_bar_set_percent(self, current: int | float, total: int | float, add_text: str = "") -> None:
        self.__update_progress_bar(current / total * 100 if total else 100, f"{current} / {total}", add_text)

    def progress_bar_set_sec(self, seconds: float, add_text: str = "") -> None:
        self.__update_progress_bar((seconds * 10) % 100, f"{seconds:.2f}", add_text)

    def open_last_loaded_folder(self) -> None:
        if self._last_loaded_folder and self._last_loaded_folder.exists():
            os.startfile(self._last_loaded_folder)

    def change_config(self) -> None:
        Config.invoke_config_changer(self)

    def check_boxes[T](self, list_to_boxes: list[T], title="", label: str | list[str] = "",
                       width: int = 300) -> list[bool]:
        return CheckBoxes.execute(list_to_boxes, title=title, label=label, parent=self, width=width)

    def buttons_box[T](self, list_to_texts: list[T], title="", label: str | list[str] = "",
                       width: int = 300) -> T | None:
        return ButtonsBox.execute(list_to_texts, title=title, label=label, parent=self, width=width)


if __name__ == '__main__':
    app = UITkinter()
    app.mainloop()
