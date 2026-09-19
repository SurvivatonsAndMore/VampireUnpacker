from __future__ import annotations

import os
import re
import sys
import tkinter as tk
import tkinter.ttk as ttk
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from PIL import ImageFont, ImageDraw, ImageText
from PIL.Image import Image, open as image_open, new as image_new

from Source.Config.config import DLC
from Source.Data.data_vs import DataHandler, DataType, DataFile
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Translations import language_vs
from Source.Translations.language_utils import Lang
from Source.Translations.language_vs import LangHandler, LangTypeVS
from Source.Utility import image_functions
from Source.Utility.constants import to_source_path, IMAGES_FOLDER, COMPOUND_DATA_TYPE, GENERATED, \
    PROGRESS_BAR_FUNC_TYPE, COMPOUND_DATA, PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.image_functions import make_image_black
from Source.Utility.image_functions import resize_image, get_adjusted_sprites_to_rect, get_rects_by_sprite_list
from Source.Utility.sprite_data import SpriteData
from Source.Utility.timer import Timeit
from Source.Utility.utility import normalize_str

PREFIX = "prefix"
CHAR_NAME = "charName"
SURNAME = "surname"
SUFFIX = "suffix"
SKIN_TYPE = "skinType"
CHAR_SEL_FRAME = "charSelFrame"
CHAR_SEL_TEXTURE = "charSelTexture"
UI = "UI"

KEY_ID = "_key_id"
ADD_TO_PATH_ENTRY = "_add_to_path_entry"
UNIQUE_SHORT_CHARACTER_NAME = "_unique_short_character_name"
FULL_CHARACTER_NAME = "_full_character_name"
SKIN_INDEX = "_skin_index"

FONT_FILE_PATH = to_source_path(IMAGES_FOLDER) / "Courier.ttf"


class GenType(Enum):
    IMAGE = 0
    IMAGE_FRAME = 1

    ANIM = 10
    ANIM_DEATH = 11
    ANIM_SPECIAL = 12

    ARCANA_PICTURE = 20

    CHARACTER_SKINS = 30
    CHARACTER_SPECIAL_SELECT = 31

    STAGE_WITH_NAME = 40

    TEXT_STROKE_WIDTH = 41

    @classmethod
    def get_types(cls) -> set[GenType]:
        return {*cls}

    @classmethod
    def get_int_types(cls) -> set[GenType]:
        return {cls.IMAGE, cls.TEXT_STROKE_WIDTH}

    def get_input_value(self, value):
        match self:
            case GenType.IMAGE:
                return int(value)
            case GenType.TEXT_STROKE_WIDTH:
                return float(value)
            case _:
                return value

    def get_tip(self) -> str:
        match self:
            case GenType.IMAGE:
                return "Scale factor"
            case GenType.IMAGE_FRAME:
                return "Generate frame variants"

            case GenType.ANIM:
                return "Generate animations"
            case GenType.ANIM_DEATH:
                return "Generate death animations"
            case GenType.ANIM_SPECIAL:
                return "Generate special animations"

            case GenType.ARCANA_PICTURE:
                return "Generate arcana pictures"

            case GenType.CHARACTER_SPECIAL_SELECT:
                return "Generate special select variants"
            case GenType.CHARACTER_SKINS:
                return "Generate character skins"

            case GenType.STAGE_WITH_NAME:
                return "Generate with stage name"
            case GenType.TEXT_STROKE_WIDTH:
                return "Text stroke width"
        return None


class EntryToSave:
    name: str
    name_wrapper: Callable[[str], str]
    add_to_path: str | None = None

    def __init__(self, name: str, name_wrapper: Callable[[str], str], add_to_path: str | None = None) -> None:
        self.name = name
        self.name_wrapper = name_wrapper
        self.add_to_path = add_to_path

    def save_entry(self,
                   save_path: Path,
                   entry: dict[str, Any],
                   scale: int,
                   add_to_path: os.PathLike[str] | str = None
                   ) -> None:
        entry_save_path = save_path / entry.get("contentGroup", "BASE_GAME")
        key_id = entry.get(KEY_ID)
        if self.name == key_id:
            entry_save_path /= "No lang"
        if entry.get("alwaysHidden"):
            entry_save_path /= "Always hidden"
        if add_to_path:
            entry_save_path /= add_to_path
        if add_to_path_entry := entry.get(ADD_TO_PATH_ENTRY):
            entry_save_path /= add_to_path_entry
        if self.add_to_path:
            entry_save_path /= self.add_to_path

        entry_save_path.mkdir(parents=True, exist_ok=True)
        self._save(entry_save_path / self.name_wrapper(self.name), scale)

    def _save(self, save_file_path: Path, scale: int) -> None:
        raise NotImplementedError()


class ImageEntryToSave(EntryToSave):
    image: Image

    def __init__(self, image: Image, name: str, name_wrapper: Callable[[str], str],
                 add_to_path: str | None = None) -> None:
        super().__init__(name, name_wrapper, add_to_path)
        self.image = image

    def _save(self, save_file_path: Path, scale: int) -> None:
        image = resize_image(self.image, scale)
        image.save(save_file_path)


class SpriteEntryToSave(ImageEntryToSave):
    sprite_data: SpriteData = None

    def __init__(self, sprite_data: SpriteData, name: str, name_wrapper: Callable[[str], str],
                 add_to_path: str | None = None) -> None:
        super().__init__(sprite_data.sprite, name, name_wrapper, add_to_path)
        self.sprite_data = sprite_data


class ImageGeneratorManager:
    @staticmethod
    def get_gen(data_type: DataType) -> "BaseImageGenerator".__class__ | None:
        match data_type:
            case DataType.ACHIEVEMENT:
                return None
            case DataType.ADVENTURE:
                return None
            case DataType.ADVENTURE_MERCHANTS:
                return AdvMerchantsGenerator
            case DataType.ADVENTURE_STAGE:
                return AdventureStageImageGenerator
            case DataType.ADVENTURE_STAGE_SET:
                return None
            case DataType.ALBUM:
                return AlbumCoversGenerator
            case DataType.ARCANA:
                return ArcanaImageGenerator
            case DataType.CHARACTER:
                return CharacterImageGenerator
            case DataType.CPU:
                return CpuGenerator
            case DataType.CUSTOM_MERCHANTS:
                return AdvMerchantsGenerator
            case DataType.ENEMY:
                return EnemyImageGenerator
            case DataType.HIT_VFX:
                return None
            case DataType.ITEM:
                return ItemImageGenerator
            case DataType.LIMIT_BREAK:
                return None
            case DataType.MUSIC:
                return MusicIconsGenerator
            case DataType.POWER_UP:
                return PowerUpImageGenerator
            case DataType.PROPS:
                return PropsImageGenerator
            case DataType.SECRET:
                return None
            case DataType.STAGE:
                return StageImageGenerator
            case DataType.WEAPON:
                return WeaponImageGenerator

        return None


def get_supported_gen_types() -> set[DataType]:
    return set(filter(ImageGeneratorManager.get_gen, DataType.get_all_types()))


def gen_unified_images(dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                       func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT,
                       parent=None) -> Path | None:
    gen_class: BaseImageGenerator.__class__ = ImageGeneratorManager.get_gen(data_type)

    if not gen_class:
        return None

    dialog = GeneratorDialog(gen_class, parent=parent)
    dialog.wait_window()
    req_gens: dict[GenType, int | bool] | None = dialog.return_data

    if not req_gens:
        return None

    gen: BaseImageGenerator = gen_class(dlc_type, data_type, req_gens)

    print(f"Selected settings for {gen_class.__name__}: {req_gens}")
    print(f"Started generating images for '{str(dlc_type)}' - '{data_type}'")
    _timeit = Timeit()

    save_path = gen.main_generator(dlc_type, data_type, func_progress_bar_set_percent)

    print(f"Finished generating unified images {_timeit!r}")

    return save_path


class BaseImageGenerator:
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.NONE
    lang_type: LangTypeVS = LangTypeVS.NONE

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = None
    key_sprite_name = None
    key_frame_name = None
    key_entry_name = "name"

    default_main_texture_name = None

    default_frame_name = None

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                 requested_gen_types: dict[GenType, int | bool]):
        self.data_file: DataFile | None = DataHandler.get_data(dlc_type, data_type)

        lang_data_full = LangHandler.get_lang_file(self.lang_type) or {}
        self.lang_data = lang_data_full and lang_data_full.get_lang(Lang.EN) or {}

        self.requested_gens = requested_gen_types
        self._set_entries()
        self.meta_data = MetaDataHandler.get_meta_dict_by_name_set_fullest(self.get_textures_set())

        print(self.meta_data)

        for texture_name, meta_data in self.meta_data.items():
            meta_data.init_sprites()
            if (GenType.ANIM in self.requested_gens
                    or GenType.ANIM_DEATH in self.requested_gens
                    or GenType.ANIM in self.requested_gens):
                meta_data.init_animations()

    def _set_entries(self):
        self.entries = [
            self.get_unit(key_id, entry.copy()) for key_id, entry in self.data_file.data().items()
        ]

    def main_condition_loop(
            self,
            *,
            entries: list,
            gen_function: Callable[[dict[str, Any]], EntryToSave | None],
            save_path: Path,
            add_to_path: str | None = None,
            required_gen_types: set[GenType],
            func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
    ):
        for req in required_gen_types:
            if not self.requested_gens.get(req):
                return

        scale = self.requested_gens[GenType.IMAGE]
        total_len = len(entries)

        for i, entry in enumerate(entries):
            func_progress_bar_set_percent(i + 1, total_len, f"{add_to_path or "Image"}: {entry.get(KEY_ID)}")

            out_entry = gen_function(entry)
            if out_entry:
                out_entry.save_entry(save_path, entry, scale, add_to_path=add_to_path)

    def main_generator(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                       func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Path | None:

        save_path = to_current_game_path(IMAGES_FOLDER) / GENERATED / data_type / str(dlc_type)
        save_path.mkdir(parents=True, exist_ok=True)

        self.main_condition_loop(
            entries=self.entries,
            gen_function=self.gen_image,
            save_path=save_path,
            add_to_path=None,
            required_gen_types={GenType.IMAGE},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path=self.save_icon_prefix,
            required_gen_types={GenType.IMAGE_FRAME},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        return save_path

    @classmethod
    def get_available_gens(cls) -> list[GenType]:
        return cls._available_gens

    def get_save_name(self, name: str) -> str:
        return re.sub(r'[<>:/|\\?*\"]', '', name.strip())

    def get_save_image_prefix(self, entry):
        return self.save_image_prefix

    def get_save_icon_prefix(self, entry):
        return self.save_icon_prefix

    def get_unit(self, key_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        to_update: dict[str, Any] = {
            KEY_ID: key_id,
        }

        if self.lang_type != LangTypeVS.NONE:
            lang_entry = self.lang_data and self.lang_data.get(key_id) or {}
            entry_name = language_vs.get_lang_value(lang_entry, self.key_entry_name) or ""
            to_update[self.key_entry_name] = entry_name

        entry.update(to_update)

        return entry

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        return entry.get(self.key_frame_name, self.default_frame_name).replace(".png", "")

    def get_textures_set(self) -> set[str]:
        textures_set = {entry.get(self.key_main_texture_name) for entry in self.entries}
        textures_set.add(UI)
        return textures_set

    def gen_image(self, entry: dict[str, Any]) -> SpriteEntryToSave | None:
        main_texture = normalize_str(entry.get(self.key_main_texture_name, self.default_main_texture_name))
        sprite_texture = normalize_str(entry.get(self.key_sprite_name))

        texture_meta_data = self.meta_data.get(main_texture)
        if not texture_meta_data:
            print(f"!!! Image skipped '{sprite_texture}': texture '{main_texture}' not found", file=sys.stderr)
            return None

        sprite_data = texture_meta_data.data_name.get(sprite_texture) or texture_meta_data.data_id.get(0)
        if not sprite_data:
            print(f"!!! Image skipped '{sprite_texture}': not found for texture '{main_texture}'", file=sys.stderr)
            return None

        eng_name = entry.get(self.key_entry_name) or entry.get(KEY_ID)

        save_image_prefix = self.get_save_image_prefix(entry)

        return SpriteEntryToSave(
            sprite_data,
            eng_name,
            lambda x: f"{save_image_prefix}-{self.get_save_name(x)}.png"
        )

    def gen_image_with_frame(self, entry: dict[str, Any]) -> ImageEntryToSave | None:
        out_image_data: SpriteEntryToSave | None = self.gen_image(entry)
        if out_image_data is None:
            return None

        image_data = out_image_data.sprite_data
        eng_name = out_image_data.name
        frame_name = self.get_frame_name(entry)

        texture_meta_data = self.meta_data.get(UI)
        if not texture_meta_data:
            print(f"!!! Image frame skipped '{frame_name}': texture '{UI}' not found", file=sys.stderr)
            return None

        frame_data = texture_meta_data.data_name.get(frame_name)
        if not frame_data:
            print(f"!!! Image frame skipped '{frame_name}': not found for texture '{UI}'", file=sys.stderr)
            return None

        rects = get_rects_by_sprite_list([image_data, frame_data])
        image, frame = get_adjusted_sprites_to_rect(zip([image_data.sprite, frame_data.sprite], rects))

        frame.alpha_composite(image)

        save_icon_prefix = self.get_save_icon_prefix(entry)

        return ImageEntryToSave(
            frame,
            eng_name,
            lambda x: f"{save_icon_prefix}-{self.get_save_name(x)}.png"
        )

    # def gen_anim(self, entry: dict[str, Any]):
    #     pass
    #
    # def gen_anim_death(self, entry: dict[str, Any]):
    #     pass
    #
    # def gen_anim_attack(self, entry: dict[str, Any]):
    #     pass


class ItemImageGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.ITEM
    lang_type: LangTypeVS = LangTypeVS.ITEM

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"
    key_frame_name = "collectionFrame"

    default_frame_name = "frameC"

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        frame = super().get_frame_name(entry)
        return "frameF" if entry.get("isRelic") and frame == self.default_frame_name else frame


class ArcanaImageGenerator(BaseImageGenerator):
    _SURVAROT = "Survarot"

    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME, GenType.ARCANA_PICTURE]

    data_type: DataType = DataType.ARCANA
    lang_type: LangTypeVS = LangTypeVS.ARCANA

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"
    key_frame_name = "collectionFrame"

    default_frame_name = "frameG"

    key_secondary_texture_name = "texture2"

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        return "frameH" if entry.get("arcanaType") >= 22 else super().get_frame_name(entry)

    # def get_save_name(self, name: str) -> str:
    #     name = super().get_save_name(name)
    #     return name[name.find("-") + 1:].strip()

    def get_save_image_prefix(self, entry):
        return self._SURVAROT if entry.get("arcanaType") > 100 else self.save_image_prefix

    def get_unit(self, key_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        entry.update({
            self.key_main_texture_name: "items",
            self.key_secondary_texture_name: entry.get(self.key_main_texture_name),
        })
        if entry.get("arcanaType") > 100:
            entry.update({
                ADD_TO_PATH_ENTRY: self._SURVAROT
            })
        return entry

    def get_textures_set(self) -> set[str]:
        textures_set = super().get_textures_set()
        textures_set.update({entry.get(self.key_secondary_texture_name) for entry in self.entries})
        return textures_set

    def main_generator(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                       func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Path | None:
        save_path = super().main_generator(dlc_type, data_type)

        self.main_condition_loop(
            entries=self.entries,
            gen_function=self.gen_arcana_picture,
            save_path=save_path,
            add_to_path="Picture",
            required_gen_types={GenType.ARCANA_PICTURE},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        return save_path

    def gen_arcana_picture(self, entry: dict[str, Any]) -> SpriteEntryToSave | None:
        main_texture = normalize_str(entry.get(self.key_secondary_texture_name))
        sprite_texture = normalize_str(entry.get(self.key_sprite_name))

        texture_meta_data = self.meta_data.get(main_texture)
        if not texture_meta_data:
            print(f"!!! Arcana picture skipped '{sprite_texture}': texture '{main_texture}' not found", file=sys.stderr)
            return None

        sprite_data = texture_meta_data.data_name.get(sprite_texture)
        if not sprite_data:
            print(f"!!! Arcana picture skipped '{sprite_texture}': not found for texture '{main_texture}'",
                  file=sys.stderr)
            return None

        eng_name = entry.get(self.key_entry_name) or entry.get(KEY_ID)

        if entry.get("arcanaType") < 100:
            name_s = eng_name.split("-")
            if len(name_s) < 2:
                num = "0"
                name = name_s[0].strip()
            else:
                num = name_s[0].strip()
                name = name_s[1].strip()
            eng_name = f"{name} ({num})"

        save_image_prefix = self.get_save_image_prefix(entry)

        return SpriteEntryToSave(
            sprite_data,
            eng_name,
            lambda x: f"{save_image_prefix}-{self.get_save_name(x)}.png"
        )


class PropsImageGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.ANIM]

    data_type: DataType = DataType.PROPS
    lang_type: LangTypeVS = LangTypeVS.NONE

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "textureName"
    key_sprite_name = "frameName"
    key_frame_name = None

    default_frame_name = None

    def get_unit(self, key_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        entry.update({
            self.key_sprite_name: f"{entry.get(self.key_sprite_name)}1",
        })
        return entry


class AdvMerchantsGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.ANIM]

    data_type: DataType = DataType.ADVENTURE_MERCHANTS
    lang_type: LangTypeVS = LangTypeVS.CHARACTER

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "staticSpriteTexture"
    key_sprite_name = "staticSprite"
    key_frame_name = None
    key_entry_name = "charName"

    default_frame_name = None


class AlbumCoversGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.ALBUM
    lang_type: LangTypeVS = LangTypeVS.NONE

    default_scale_factor = 1

    save_image_prefix = "Album"

    key_main_texture_name = "icon"
    key_sprite_name = "icon"
    key_entry_name = "title"


class MusicIconsGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.MUSIC
    lang_type: LangTypeVS = LangTypeVS.NONE

    default_scale_factor = 1

    save_image_prefix = "Music"

    key_main_texture_name = None
    key_sprite_name = "icon"
    key_frame_name = None
    key_entry_name = "title"

    default_main_texture_name = UI

    def get_unit(self, key_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)

        add_to_path = ""
        check = entry.get("source").lower() or entry.get("title").lower()
        if "castlevania" in check:
            add_to_path = entry.get("source")
        if "vampire survivors" in check:
            add_to_path = entry.get("author")

        entry.update({
            ADD_TO_PATH_ENTRY: add_to_path
        })
        return entry


class CpuGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.CPU
    lang_type: LangTypeVS = LangTypeVS.PARTY

    default_scale_factor = 1

    save_image_prefix = "Cpu"

    key_main_texture_name = "AIIconTexture"
    key_sprite_name = "AIIconSprite"
    key_entry_name = "name"


class ListBaseImageGenerator(BaseImageGenerator):
    def get_unit(self, key_id: str, entry: list[dict[str, Any]]) -> dict[str, Any]:
        return super().get_unit(key_id, entry[0])


class WeaponImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.WEAPON
    lang_type: LangTypeVS = LangTypeVS.WEAPON

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"
    key_frame_name = "collectionFrame"

    default_frame_name = "frameB"


class PowerUpImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.POWER_UP
    lang_type: LangTypeVS = LangTypeVS.POWER_UP

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "PowerUp"

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"

    default_frame_name = "frameD"

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        frame = super().get_frame_name(entry)
        return "frameE" if entry.get("specialBG") and frame == self.default_frame_name else frame


class CharacterImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME, GenType.CHARACTER_SPECIAL_SELECT,
                                      GenType.CHARACTER_SKINS, GenType.TEXT_STROKE_WIDTH]

    data_type: DataType = DataType.CHARACTER
    lang_type: LangTypeVS = LangTypeVS.CHARACTER

    save_image_prefix = "Sprite"
    save_icon_prefix = "Select"

    key_main_texture_name = "textureName"
    key_sprite_name = "spriteName"
    key_frame_name = None
    key_entry_name = FULL_CHARACTER_NAME

    key_secondary_texture_name = CHAR_SEL_TEXTURE
    key_secondary_sprite_name = CHAR_SEL_FRAME

    default_frame_name = "CharacterSelectFrame.png"
    default_stroke_width = 0.7

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                 requested_gen_types: dict[GenType, int | bool]):
        super().__init__(dlc_type, data_type, requested_gen_types)

        self.weapon_image_gen = WeaponImageGenerator(COMPOUND_DATA, DataType.WEAPON, {GenType.IMAGE: 1})
        if requested_gen_types.get(GenType.IMAGE_FRAME):
            self.frame_image = image_open(to_source_path(IMAGES_FOLDER) / self.default_frame_name)

        self.weapon_skin_entries = None
        self.select_entries = None
        self.select_skin_entries = None
        self.weapon_select_skin_entries = None

        if requested_gen_types.get(GenType.CHARACTER_SKINS):
            self.weapon_skin_entries = self.get_weapon_entries(self.skin_entries)

        if requested_gen_types.get(GenType.CHARACTER_SPECIAL_SELECT):
            self.select_entries = self.get_select_entries(self.entries)
            if requested_gen_types.get(GenType.CHARACTER_SKINS):
                self.select_skin_entries = self.get_select_entries(self.skin_entries)
                self.weapon_select_skin_entries = self.get_weapon_entries(self.select_skin_entries)

    def _set_entries(self):
        super()._set_entries()

        lang_data_full = LangHandler.get_lang_file(LangTypeVS.SKIN) or {}
        self.lang_skin_data: dict[str, Any] | None = lang_data_full and lang_data_full.get_lang(Lang.EN) or {}

        self.base_entries = self.entries.copy()
        self.skin_entries = self.get_skin_entries(self.entries)
        self.entries = list(filter(lambda x: x.get(SKIN_INDEX, 0) == 0, self.skin_entries))

    def get_textures_set(self) -> set[str]:
        textures_set = super().get_textures_set()
        textures_set.update({entry.get(self.key_secondary_texture_name) for entry in self.skin_entries})
        return textures_set

    def main_generator(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                       func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Path | None:
        save_path = super().main_generator(dlc_type, data_type, func_progress_bar_set_percent)

        self.main_condition_loop(
            entries=self.select_entries,
            gen_function=self.gen_image,
            save_path=save_path,
            add_to_path="Special",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SPECIAL_SELECT},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.select_entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path="Select/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SPECIAL_SELECT},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.skin_entries,
            gen_function=self.gen_image,
            save_path=save_path,
            add_to_path="Skin",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.skin_entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path=f"Skin/{self.save_icon_prefix}",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )
        self.main_condition_loop(
            entries=self.weapon_skin_entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path=f"Skin/Weapon/{self.save_icon_prefix}",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.select_skin_entries,
            gen_function=self.gen_image,
            save_path=save_path,
            add_to_path="Skin/Special",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        self.main_condition_loop(
            entries=self.select_skin_entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path=f"Skin/{self.save_icon_prefix}/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )
        self.main_condition_loop(
            entries=self.weapon_select_skin_entries,
            gen_function=self.gen_image_with_frame,
            save_path=save_path,
            add_to_path=f"Skin/Weapon/{self.save_icon_prefix}/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        return save_path

    def get_skin_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        skin_entries = []
        for entry in entries:
            key_id = entry.get(KEY_ID)
            char_skins = entry.get("skins")

            if not char_skins:
                char_skins = [entry]

            for skin_index, skin in enumerate(char_skins):
                skin_entry = dict(**entry)
                skin_entry.update(skin)

                lang_entry = self.lang_data and self.lang_data.get(key_id) or {}
                skin_type = skin_entry.get(SKIN_TYPE)
                skin_lang_entry = self.lang_skin_data and self.lang_skin_data.get(skin_type) or {}

                prefix = language_vs.get_lang_value(skin_lang_entry, PREFIX) \
                         or language_vs.get_lang_value(lang_entry, PREFIX) \
                         or skin_entry.get(PREFIX)
                char_name = language_vs.get_lang_value(lang_entry, CHAR_NAME) \
                            or skin_entry.get(CHAR_NAME)
                surname = language_vs.get_lang_value(lang_entry, SURNAME) \
                          or skin_entry.get(SURNAME)
                suffix = language_vs.get_lang_value(skin_lang_entry, SUFFIX) \
                         or skin_entry.get(SUFFIX)

                skin_entry.update({
                    PREFIX: prefix or "",
                    CHAR_NAME: char_name or "",
                    SURNAME: surname or "",
                    SUFFIX: suffix or "",
                    FULL_CHARACTER_NAME: " ".join(filter(None, [prefix, char_name, surname, suffix])),
                    SKIN_INDEX: skin_index
                })
                skin_entries.append(skin_entry)

        return skin_entries

    def get_select_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        select_entries = []

        for entry in entries:
            key_id = entry.get(KEY_ID)
            select_entry = {**entry}

            if self.key_secondary_texture_name not in entry:
                continue

            select_entry.update({
                self.key_main_texture_name: select_entry.get(self.key_secondary_texture_name),
                self.key_sprite_name: select_entry.get(self.key_secondary_sprite_name),
            })

            select_entries.append(select_entry)

        return select_entries

    def get_weapon_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        weapon_entries = []

        for entry in entries:
            key_id = entry.get(KEY_ID)

            if (weapon_id := entry.get("startingWeapon")) and weapon_id not in ["VOID", "0", 0, None]:
                weapon_lang_data = self.weapon_image_gen.lang_data
                weapon_lang = language_vs.get_lang_value(weapon_lang_data, weapon_id, 'name')

                if weapon_lang is None:
                    print(f"Not found weapon [ID={weapon_id}] for character {key_id}")
                    continue

                weapon_entry = dict(**entry)

                prefix = entry.get(PREFIX)
                char_name = entry.get(CHAR_NAME)
                surname = entry.get(SURNAME)

                weapon_entry.update({
                    FULL_CHARACTER_NAME: " ".join(filter(None, [prefix, char_name, surname, f"({weapon_lang})"])),
                })
                weapon_entries.append(weapon_entry)

        return weapon_entries

    def get_unit(self, key_id: str, entry: list[dict[str, Any]]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        lang_entry = self.lang_data and self.lang_data.get(key_id) or {}
        prefix = language_vs.get_lang_value(lang_entry, PREFIX)
        char_name = language_vs.get_lang_value(lang_entry, CHAR_NAME)
        surname = language_vs.get_lang_value(lang_entry, SURNAME)
        entry.update({
            PREFIX: prefix or "",
            CHAR_NAME: char_name or "",
            SURNAME: surname or "",
            FULL_CHARACTER_NAME: " ".join(filter(None, [prefix, char_name, surname]))
        })
        return entry

    def gen_image_with_frame(self, entry: dict[str, Any]) -> ImageEntryToSave | None:
        out_image_data: SpriteEntryToSave | None = self.gen_image(entry)
        if out_image_data is None:
            return None

        image_data = out_image_data.sprite_data
        eng_name = out_image_data.name

        char_sprite = resize_image(image_data.sprite, 3.8)
        frame_image = self.frame_image.copy()

        if (weapon_id := entry.get("startingWeapon")) and weapon_id not in ["VOID", "0", 0, None]:
            weapon_data = self.weapon_image_gen.data_file.data().get(weapon_id)
            if weapon_data is None:
                print(f"Not found weapon [ID={weapon_id}] for character {eng_name}")
                return None

            weapon_entry = self.weapon_image_gen.gen_image(self.weapon_image_gen.get_unit(weapon_id, weapon_data))

            if weapon_entry is None:
                return None

            weapon_image = resize_image(weapon_entry.image, 4)
            weapon_image_shadow = make_image_black(weapon_image)

            weapon_offset = {
                "x": frame_image.width - weapon_image.width - 10, "y": frame_image.height - weapon_image.height - 12
            }

            frame_image.alpha_composite(weapon_image_shadow, (weapon_offset["x"], weapon_offset["y"]))
            frame_image.alpha_composite(weapon_image, (weapon_offset["x"] - 8, weapon_offset["y"] - 4))

        frame_image.alpha_composite(char_sprite, (12, frame_image.height - char_sprite.height - 11))

        text = entry.get(CHAR_NAME)

        image_text = image_functions.get_wrapped_text(
            text,
            FONT_FILE_PATH,
            (frame_image.size[0] - 30, frame_image.size[1]),
            (20, 30)
        )
        image_text.stroke(width=self.requested_gens.get(GenType.TEXT_STROKE_WIDTH), fill="#ffffff")

        canvas = image_new('RGBA', frame_image.size)
        draw = ImageDraw.Draw(canvas)
        draw.text((3, 5), image_text)

        frame_image.alpha_composite(canvas, (14, 10))

        return ImageEntryToSave(
            frame_image,
            eng_name,
            lambda x: f"{self.save_icon_prefix}-{self.get_save_name(x)}.png"
        )


class EnemyImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.ENEMY
    lang_type: LangTypeVS = LangTypeVS.ENEMIES

    save_image_prefix = "Sprite"

    key_main_texture_name = "textureName"
    key_sprite_name = "frameNames"
    key_frame_name = None
    key_entry_name = "bName"

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                 requested_gen_types: dict[GenType, int | bool]):
        super().__init__(dlc_type, data_type, requested_gen_types)
        raise NotImplementedError(f"{self.__class__.__name__} not implemented")


class StageImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.STAGE_WITH_NAME, GenType.TEXT_STROKE_WIDTH]

    data_type: DataType = DataType.STAGE
    lang_type: LangTypeVS = LangTypeVS.STAGE

    default_scale_factor = 1

    save_image_prefix = "Stage"

    key_main_texture_name = "uiTexture"
    key_sprite_name = "uiFrame"
    key_frame_name = None
    key_entry_name = "stageName"

    default_stroke_width = 1

    def main_generator(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                       func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT) -> Path | None:
        save_path = super().main_generator(dlc_type, data_type, func_progress_bar_set_percent)

        self.main_condition_loop(
            entries=self.entries,
            gen_function=self.gen_image_with_name,
            save_path=save_path,
            add_to_path="With name",
            required_gen_types={GenType.STAGE_WITH_NAME},
            func_progress_bar_set_percent=func_progress_bar_set_percent
        )

        return save_path

    def gen_image_with_name(self, entry: dict[str, Any]) -> ImageEntryToSave | None:
        out_image_data: SpriteEntryToSave | None = self.gen_image(entry)
        if out_image_data is None:
            return None

        image_data = out_image_data.sprite_data
        eng_name = out_image_data.name

        stage_image = resize_image(image_data.sprite, 4)

        text = eng_name.strip()
        base_scale = 50
        while True:
            font = ImageFont.truetype(FONT_FILE_PATH, base_scale)
            w = font.getbbox(text)[2] + 4
            h = font.getbbox(text + "|")[3]
            if w + 40 > stage_image.size[0]:
                base_scale -= 2
            else:
                break

        canvas = image_new('RGBA', (int(w), int(h)))

        draw = ImageDraw.Draw(canvas)
        draw.text((3, -5), text, "#eef92b", font, stroke_width=self.requested_gens.get(GenType.TEXT_STROKE_WIDTH))

        crx, cry = stage_image.size
        crx //= 2
        cry //= 5
        frx, fry = canvas.size
        frx //= 2
        fry //= 2
        stage_image.alpha_composite(canvas, (crx - frx, cry - fry))

        return ImageEntryToSave(
            stage_image,
            eng_name,
            lambda x: f"{self.save_image_prefix}-{self.get_save_name(x)}.png"
        )


class AdventureStageImageGenerator(StageImageGenerator):
    data_type: DataType = DataType.ADVENTURE_STAGE

    stage_set: DataFile = None
    stage_to_stage_set: dict[str, str] | None = None

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE, data_type: DataType,
                 requested_gen_types: dict[GenType, int | bool]):
        self.stage_set: DataFile | None = DataHandler.get_data(dlc_type, DataType.ADVENTURE_STAGE_SET)
        self.stage_to_stage_set = {
            stage: stage_set
            for stage_set, stages in self.stage_set.data().items()
            for stage in stages
        }

        super().__init__(dlc_type, data_type, requested_gen_types)

    def get_unit(self, key_id: str, entry: list[dict[str, Any]]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        entry.update({
            ADD_TO_PATH_ENTRY: self.stage_to_stage_set[key_id],
        })
        return entry


class GeneratorDialog(tk.Toplevel):
    def __init__(self, gen: BaseImageGenerator.__class__, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.title("Select settings")
        ttk.Label(self, text="Select settings for image generator").pack()
        ttk.Label(self, text=f"({gen.data_type})").pack()

        self.settings: dict[GenType, ...] = dict()

        gen_types_order = list(sorted(GenType.get_types(), key=lambda x: x.value))
        available_gens = gen.get_available_gens()

        for gen_type in gen_types_order:
            if gen_type not in available_gens:
                continue

            if gen_type == GenType.IMAGE:
                ttk.Label(self, text=gen_type.get_tip()).pack()
                scale_input = ttk.Entry(self)
                scale_input.insert(0, str(gen.default_scale_factor))
                scale_input.pack()

                self.settings.update({gen_type: scale_input})

            elif gen_type == GenType.TEXT_STROKE_WIDTH:
                ttk.Label(self, text=gen_type.get_tip()).pack()
                stroke_width_input = ttk.Entry(self)
                stroke_width_input.insert(0, str(gen.default_stroke_width))
                stroke_width_input.pack()

                self.settings.update({gen_type: stroke_width_input})

            else:
                bool_var = tk.BooleanVar()
                ttk.Checkbutton(self, text=gen_type.get_tip(), variable=bool_var, takefocus=False).pack()

                self.settings.update({gen_type: bool_var})

        ttk.Button(self, text="Start", command=self.__close).pack()

        self.protocol("WM_DELETE_WINDOW", self.__close_exit)

    def __close_exit(self):
        self.return_data = None
        self.destroy()

    def __close(self):
        self.return_data = {k: k.get_input_value(v.get()) for k, v in self.settings.items()}
        self.destroy()


if __name__ == "__main__":
    width, height = 198, 228
    text = "Master Librarian"
    font = ImageFont.truetype("Courier.ttf", 30)
    image_text = ImageText.Text(text, font)
    image_text.stroke(width=0.7, fill="#ffffff")
    a = image_text.wrap(width, height, scaling=("shrink", 20))
    wrap = ImageText._Wrap(image_text, width, height, font)
    print(repr(image_text.text), repr(a), repr(wrap.lines))
