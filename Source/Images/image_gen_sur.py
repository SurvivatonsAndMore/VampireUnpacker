from __future__ import annotations

import os
import re
import sys
import itertools
import dataclasses
from pathlib import Path
from typing import Any, Callable

from PIL import ImageDraw
from PIL.Image import Image, open as image_open, new as image_new

from Source.Config.config import DLC
from Source.Data.data_sur import DataHandler, DataType, DataFile
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Images import image_gen_types, transparent_save
from Source.Images.image_gen_types import GenType
from Source.Translations import language_sur
from Source.Translations.language_sur import LangHandler, LangTypeSur
from Source.Translations.language_utils import Lang
from Source.Utility import image_functions
from Source.Utility.constants import to_source_path, IMAGES_FOLDER, COMPOUND_DATA_TYPE, GENERATED, \
    PROGRESS_BAR_FUNC_TYPE, COMPOUND_DATA, PROGRESS_BAR_FUNC_DEFAULT, DEFAULT_ANIMATION_FRAME_RATE
from Source.Utility.image_functions import make_image_black
from Source.Utility.image_functions import resize_image, get_adjusted_sprites_to_rect, get_rects_by_sprite_list
from Source.Utility.sprite_data import SpriteData, AnimationData
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
ADD_TO_PATH_ENTRY1 = "_add_to_path_entry1"
ADD_TO_PATH_ENTRY2 = "_add_to_path_entry2"
UNIQUE_SHORT_CHARACTER_NAME = "_unique_short_character_name"
FULL_CHARACTER_NAME = "_full_character_name"
DEFAULT = "DEFAULT"
SAVE_POSTFIX = "_save_postfix"

FONT_FILE_PATH = to_source_path(IMAGES_FOLDER) / "Courier.ttf"

_UNSAVABLE_CHARACTERS = re.compile(r'[<>:/|\\?*\"]')


def get_save_name(name: str) -> str:
    return _UNSAVABLE_CHARACTERS.sub('', name.strip())


@dataclasses.dataclass
class NameToSave:
    prefix: str
    name: str
    postfix: str

    def __str__(self) -> str:
        return get_save_name(f"{self.prefix}-{self.name}{self.postfix}")

    def str_ext(self, ext: str):
        return f"{self!s}{ext}"

    def w(self, *, prefix: str | None = None, name: str | None = None, postfix: str | None = None) -> NameToSave:
        return NameToSave(prefix or self.prefix, name or self.name, postfix or self.postfix)


class EntryToSave:
    name: NameToSave
    add_to_path: str | None = None

    _used_mkdir: set[Path] = set()

    def __init__(self, name: NameToSave, add_to_path: str | None = None) -> None:
        self.name = name
        self.add_to_path = add_to_path

    def save_entry(self,
                   save_path: Path,
                   entry: dict[str, Any],
                   scale: int,
                   add_to_path: os.PathLike[str] | str | None = None
                   ) -> None:
        entry_save_path = save_path / entry.get("contentGroup", "BASE_GAME")
        key_id = entry.get(KEY_ID)

        if self.name.name == key_id:
            entry_save_path /= "No lang"

        if entry.get("alwaysHidden"):
            entry_save_path /= "Always hidden"

        if add_to_path_entry := entry.get(ADD_TO_PATH_ENTRY1, False):
            entry_save_path /= add_to_path_entry

        if add_to_path:
            entry_save_path /= add_to_path

        if add_to_path_entry := entry.get(ADD_TO_PATH_ENTRY2, False):
            entry_save_path /= add_to_path_entry

        if self.add_to_path:
            entry_save_path /= self.add_to_path

        if entry_save_path not in EntryToSave._used_mkdir:
            entry_save_path.mkdir(parents=True, exist_ok=True)
            EntryToSave._used_mkdir.add(entry_save_path)

        self._save(entry_save_path, scale)

    def _save(self, save_folder_path: Path, scale: int) -> None:
        raise NotImplementedError()


class ImageEntryToSave(EntryToSave):
    image: Image

    def __init__(self, image: Image, name: NameToSave, add_to_path: str | None = None) -> None:
        super().__init__(name, add_to_path=add_to_path)
        self.image = image

    def _save(self, save_folder_path: Path, scale: int) -> None:
        image = resize_image(self.image, scale)
        image.save(save_folder_path / self.name.str_ext(".png"))


class SpriteEntryToSave(ImageEntryToSave):
    sprite_data: SpriteData

    def __init__(self, sprite_data: SpriteData, name: NameToSave, add_to_path: str | None = None) -> None:
        super().__init__(sprite_data.sprite, name, add_to_path=add_to_path)
        self.sprite_data = sprite_data


class AnimationEntryToSave(EntryToSave):
    animation_data: AnimationData
    frame_rate: int
    anim_save_types: list[bool]

    def __init__(self, animation_data: AnimationData, name: NameToSave, frame_rate: int, anim_save_types: list[bool],
                 add_to_path: str | None = None) -> None:
        super().__init__(name, add_to_path=add_to_path)
        self.animation_data = animation_data
        self.frame_rate = frame_rate
        self.anim_save_types = anim_save_types

    def _save(self, save_folder_path: Path, scale: int) -> None:
        sprites_list = image_functions.get_anim_sprites_ready(self.animation_data)
        sprites_list = image_functions.resize_list_images(sprites_list, scale)

        duration = 1000 // self.frame_rate

        for i, is_save_type in enumerate(self.anim_save_types):
            if is_save_type:
                ext, folder, func = transparent_save.SAVE_DATA[i]
                save_path = save_folder_path / folder
                save_path.mkdir(parents=True, exist_ok=True)
                func(sprites_list, duration, save_path / self.name.str_ext(ext))


class ImageGeneratorManager:
    @staticmethod
    def get_gen(data_type: DataType) -> type[BaseImageGenerator] | None:
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
                return CustomMerchantsGenerator
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


class BaseImageGenerator:
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.NONE
    lang_type: LangTypeSur = LangTypeSur.NONE

    default_scale_factor = 1
    default_text_stroke_width = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"
    save_anim_prefix = "Animated"

    key_main_texture_name = None
    key_sprite_name = None
    key_frame_name = None
    key_entry_name = "name"
    key_frame_rate_name = None

    default_main_texture_name = None
    default_frame_name = None

    _is_initialized = True

    @classmethod
    def get_defaults(cls):
        return {
            GenType.IMAGE: cls.default_scale_factor,
            GenType.TEXT_STROKE_WIDTH: cls.default_text_stroke_width,
        }

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE | None, requested_gens: dict[GenType, int | float | bool]):
        self.dlc_type = dlc_type
        if dlc_type is None:
            self._is_initialized = False
            return

        df: DataFile | None = DataHandler.get_data(dlc_type, self.data_type)
        if df is None:
            print(f"!!! Data file {self.data_type} not found for {dlc_type}")
            return
        self.data_file = df

        self.lang_data: dict[str, Any] = dict()
        if ((lang_data_full := LangHandler.get_lang_file(self.lang_type))
                and (lang_data := lang_data_full.get_lang(Lang.EN))):
            self.lang_data = lang_data

        self.requested_gens = requested_gens
        self.scale = int(self.requested_gens[GenType.IMAGE])
        self._set_entries()

        texture_set = self.get_textures_set()
        texture_set.discard(None)
        self.meta_data = MetaDataHandler.get_meta_dict_by_name_set_fullest(texture_set)

        # print(self.meta_data)

        for texture_name, meta_data in self.meta_data.items():
            meta_data.init_sprites()
            if image_gen_types.has_requested_anim(self.requested_gens):
                meta_data.init_animations()

        ###
        self.func_progress_bar_set_percent = PROGRESS_BAR_FUNC_DEFAULT
        self.save_path = Path()
        self.selected_anim_types = None

    def _set_entries(self):
        self.entries = []
        self.entries_dict = {}
        for key_id, entry in self.data_file.data().items():
            e = self.get_unit(key_id, entry.copy())
            self.entries.append(e)
            self.entries_dict[key_id] = e

    def generation_loop(self, *,
                        entries: list,
                        gen_function: Callable[[dict[str, Any]], EntryToSave | None],
                        add_to_path: str | None = None,
                        required_gen_types: set[GenType]):
        if not all(self.requested_gens.get(req) for req in required_gen_types):
            return

        total_len = len(entries)

        for i, entry in enumerate(entries):
            self.func_progress_bar_set_percent(i + 1, total_len, f"{add_to_path or "Image"}: {entry.get(KEY_ID)}")

            out_entry = gen_function(entry)
            if out_entry is None:
                print(f"{add_to_path or "Image"}: {entry.get(KEY_ID)} skipped generation")
                continue
            else:
                out_entry.save_entry(self.save_path, entry, self.scale, add_to_path=add_to_path)

    def main_generator(self) -> None:

        self.generation_loop(entries=self.entries,
                             gen_function=self.gen_image,
                             add_to_path=None,
                             required_gen_types={GenType.IMAGE})

        self.generation_loop(entries=self.entries,
                             gen_function=self.gen_image_with_frame,
                             add_to_path=self.save_icon_prefix,
                             required_gen_types={GenType.IMAGE_FRAME})

        self.generation_loop(entries=self.entries,
                             gen_function=self.gen_anim,
                             add_to_path=self.save_anim_prefix,
                             required_gen_types={GenType.ANIM})

    def start_generator(self, selected_anim_types: list[bool] | None = None,
                        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE | None = None) -> Path:
        self.selected_anim_types = selected_anim_types

        self.save_path = to_current_game_path(IMAGES_FOLDER) / GENERATED / self.data_type / str(self.dlc_type)
        self.save_path.mkdir(parents=True, exist_ok=True)

        fpb = func_progress_bar_set_percent
        self.func_progress_bar_set_percent = fpb if fpb is not None else PROGRESS_BAR_FUNC_DEFAULT

        print(f"Selected settings for {self.__class__.__name__}: {self.requested_gens}")
        print(f"Started generating images for '{str(self.dlc_type)}' - '{self.data_type}'")
        _timeit = Timeit()

        self.main_generator()

        print(f"Finished generating unified images {_timeit!r}")

        return self.save_path

    @classmethod
    def get_available_gens(cls) -> list[GenType]:
        return cls._available_gens

    def get_save_image_prefix(self, entry):
        return self.save_image_prefix

    def get_save_icon_prefix(self, entry):
        return self.save_icon_prefix

    def get_save_anim_prefix(self, entry):
        return self.save_anim_prefix

    def get_save_image_postfix(self, entry):
        postfix = entry.get(SAVE_POSTFIX)
        return '' if postfix is None else postfix

    def get_unit(self, key_id: str, entry: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        assert isinstance(entry, dict)
        to_update: dict[str, Any] = {
            KEY_ID: key_id,
        }

        if self.lang_type != LangTypeSur.NONE:
            lang_entry = self.lang_data and self.lang_data.get(key_id) or {}
            entry_name = language_sur.get_lang_value(lang_entry, self.key_entry_name)

            ## Lang name -> Data name -> ID
            if entry_name is None:
                entry_name = entry.get(self.key_entry_name) or ""
                if entry_name:
                    to_update[ADD_TO_PATH_ENTRY1] = "Data name"

            to_update[self.key_entry_name] = entry_name

        entry.update(to_update)

        return entry

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        return entry.get(self.key_frame_name, self.default_frame_name).replace(".png", "")

    def get_textures_set(self, entries: list[dict[str, Any]] | None = None) -> set[str | None]:
        entries = entries or self.entries
        textures_set = {entry.get(self.key_main_texture_name) for entry in entries}
        textures_set.add(UI)
        return textures_set

    def gen_image(self, entry: dict[str, Any]) -> SpriteEntryToSave | None:
        main_texture = normalize_str(entry.get(self.key_main_texture_name) or self.default_main_texture_name)
        sprite_texture = normalize_str(entry[self.key_sprite_name])

        texture_meta_data = self.meta_data.get(main_texture)
        if not texture_meta_data:
            print(f"!!! Image skipped '{sprite_texture}': texture '{main_texture}' not found", file=sys.stderr)
            return None

        sprite_data = texture_meta_data.data_name.get(sprite_texture) or texture_meta_data.data_id.get(0)
        if not sprite_data:
            print(f"!!! Image skipped '{sprite_texture}': not found for texture '{main_texture}'", file=sys.stderr)
            return None

        eng_name = entry.get(self.key_entry_name) or entry[KEY_ID]

        return SpriteEntryToSave(
            sprite_data,
            NameToSave(
                self.get_save_image_prefix(entry),
                eng_name,
                self.get_save_image_postfix(entry)
            )
        )

    def gen_image_with_frame(self, entry: dict[str, Any]) -> ImageEntryToSave | None:
        out_image_data: SpriteEntryToSave | None = self.gen_image(entry)
        if out_image_data is None:
            return None

        image_data = out_image_data.sprite_data
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

        return ImageEntryToSave(
            frame,
            out_image_data.name.w(prefix=self.get_save_icon_prefix(entry))
        )

    def gen_anim(self, entry: dict[str, Any]) -> AnimationEntryToSave | None:
        main_texture = normalize_str(entry.get(self.key_main_texture_name) or self.default_main_texture_name)
        sprite_texture = normalize_str(entry[self.key_sprite_name])

        texture_meta_data = self.meta_data.get(main_texture)
        if not texture_meta_data:
            print(f"!!! Anim skipped '{sprite_texture}': not found texture '{main_texture}'", file=sys.stderr)
            return None

        sprite_data = texture_meta_data.data_name.get(sprite_texture) or texture_meta_data.data_id.get(0)
        if not sprite_data:
            print(f"!!! Anim skipped '{sprite_texture}': not found sprite for texture '{main_texture}'",
                  file=sys.stderr)
            return None

        if not sprite_data.animation:
            print(f"!!! Anim skipped '{sprite_texture}': not found animation for texture '{main_texture}'",
                  file=sys.stderr)
            return None

        eng_name = entry.get(self.key_entry_name) or entry[KEY_ID]
        frame_rate = entry.get(self.key_frame_rate_name, DEFAULT_ANIMATION_FRAME_RATE)

        return AnimationEntryToSave(
            sprite_data.animation,
            NameToSave(
                self.get_save_anim_prefix(entry),
                eng_name,
                self.get_save_image_postfix(entry)
            ),
            frame_rate=frame_rate,
            anim_save_types=self.selected_anim_types
        )


class ItemImageGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.ITEM
    lang_type: LangTypeSur = LangTypeSur.ITEM

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
    lang_type: LangTypeSur = LangTypeSur.ARCANA

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"
    key_frame_name = "collectionFrame"

    default_frame_name = "frameG"

    key_secondary_texture_name = "texture2"

    main_texture_name = "tps_props"

    def _set_entries(self):
        super()._set_entries()

        self.base_entries = self.entries.copy()

        self.entries = self.get_arcana_entries(self.base_entries)
        self.entries_names = self.get_changed_names_entries(self.entries)
        self.survarots = self.get_arcana_entries(self.base_entries, is_survarots=True)

    def get_frame_name(self, entry: dict[str, Any]) -> str:
        return "frameH" if entry["arcanaType"] >= 22 else super().get_frame_name(entry)

    def get_save_image_prefix(self, entry):
        return self._SURVAROT if entry["arcanaType"] > 100 else self.save_image_prefix

    def get_unit(self, key_id: str, entry: dict[str, Any]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        entry.update({
            self.key_main_texture_name: self.main_texture_name,
            self.key_secondary_texture_name: entry.get(self.key_main_texture_name),
        })
        return entry

    def get_textures_set(self, entries: list[dict[str, Any]] | None = None) -> set[str | None]:
        textures_set = super().get_textures_set(entries)
        textures_set.update({entry.get(self.key_secondary_texture_name) for entry in self.entries})
        return textures_set

    def main_generator(self) -> None:
        super().main_generator()

        self.generation_loop(
            entries=self.entries_names,
            gen_function=self.gen_image,
            add_to_path="Other name format",
            required_gen_types={GenType.IMAGE})

        self.generation_loop(
            entries=self.entries_names,
            gen_function=self.gen_image_with_frame,
            add_to_path=f"Other name format/{self.save_icon_prefix}",
            required_gen_types={GenType.IMAGE_FRAME})

        self.generation_loop(
            entries=self.entries,
            gen_function=self.gen_arcana_picture,
            add_to_path="Picture",
            required_gen_types={GenType.ARCANA_PICTURE})

        self.generation_loop(
            entries=self.entries_names,
            gen_function=self.gen_arcana_picture,
            add_to_path=f"Other name format/Picture",
            required_gen_types={GenType.IMAGE_FRAME})

        self.generation_loop(
            entries=self.survarots,
            gen_function=self.gen_arcana_picture,
            add_to_path="Survarots",
            required_gen_types={GenType.ARCANA_PICTURE})

    def get_changed_names_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        entries_names = []

        for entry in entries:
            name_entry = {**entry}

            eng_name = name_entry.get(self.key_entry_name) or name_entry[KEY_ID]

            name_s = eng_name.split("-")
            if len(name_s) < 2:
                num = "0"
                name = name_s[0].strip()
            else:
                num = name_s[0].strip()
                name = name_s[1].strip()
            eng_name = f"{name} ({num})"

            name_entry[self.key_entry_name] = eng_name

            entries_names.append(name_entry)

        return entries_names

    @staticmethod
    def get_arcana_entries(entries: list[dict[str, Any]], *, is_survarots: bool = False) -> list[dict[str, Any]]:
        return list(filter(lambda entry: (entry["arcanaType"] <= 100) ^ is_survarots, entries))

    def gen_arcana_picture(self, entry: dict[str, Any]) -> SpriteEntryToSave | None:
        main_texture = normalize_str(entry[self.key_secondary_texture_name])
        sprite_texture = normalize_str(entry[self.key_sprite_name])

        texture_meta_data = self.meta_data.get(main_texture)
        if not texture_meta_data:
            print(f"!!! Arcana picture skipped '{sprite_texture}': texture '{main_texture}' not found", file=sys.stderr)
            return None

        sprite_data = texture_meta_data.data_name.get(sprite_texture)
        if not sprite_data:
            print(f"!!! Arcana picture skipped '{sprite_texture}': not found for texture '{main_texture}'",
                  file=sys.stderr)
            return None

        eng_name = entry.get(self.key_entry_name) or entry[KEY_ID]

        return SpriteEntryToSave(
            sprite_data,
            NameToSave(
                self.get_save_image_prefix(entry),
                eng_name,
                self.get_save_image_postfix(entry)
            )
        )


class PropsImageGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.ANIM]

    data_type: DataType = DataType.PROPS
    lang_type: LangTypeSur = LangTypeSur.NONE

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
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.ADVENTURE_MERCHANTS
    lang_type: LangTypeSur = LangTypeSur.CHARACTER

    default_scale_factor = 1

    save_image_prefix = "Sprite"
    save_icon_prefix = "Icon"

    key_main_texture_name = "staticSpriteTexture"
    key_sprite_name = "staticSprite"
    key_frame_name = None
    key_entry_name = "charName"

    default_frame_name = None


class CustomMerchantsGenerator(AdvMerchantsGenerator):
    data_type: DataType = DataType.CUSTOM_MERCHANTS


class AlbumCoversGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.ALBUM
    lang_type: LangTypeSur = LangTypeSur.NONE

    default_scale_factor = 1

    save_image_prefix = "Album"

    key_main_texture_name = "icon"
    key_sprite_name = "icon"
    key_entry_name = "title"


class MusicIconsGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.MUSIC
    lang_type: LangTypeSur = LangTypeSur.NONE

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
        check = (entry.get("source") or entry.get("title") or "").lower()
        if "castlevania" in check:
            add_to_path = entry.get("source")
        if "vampire survivors" in check:
            add_to_path = entry.get("author")

        entry.update({
            ADD_TO_PATH_ENTRY2: add_to_path
        })
        return entry


class CpuGenerator(BaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE]

    data_type: DataType = DataType.CPU
    lang_type: LangTypeSur = LangTypeSur.PARTY

    default_scale_factor = 1

    save_image_prefix = "Cpu"

    key_main_texture_name = "AIIconTexture"
    key_sprite_name = "AIIconSprite"
    key_entry_name = "name"


class ListBaseImageGenerator(BaseImageGenerator):
    def get_unit(self, key_id: str, entry: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
        assert isinstance(entry, list)
        return super().get_unit(key_id, entry[0])


class WeaponImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.WEAPON
    lang_type: LangTypeSur = LangTypeSur.WEAPON

    key_main_texture_name = "texture"
    key_sprite_name = "frameName"
    key_frame_name = "collectionFrame"

    default_frame_name = "frameB"


class PowerUpImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.IMAGE_FRAME]

    data_type: DataType = DataType.POWER_UP
    lang_type: LangTypeSur = LangTypeSur.POWER_UP

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
                                      GenType.CHARACTER_SKINS, GenType.TEXT_STROKE_WIDTH,
                                      GenType.ANIM, GenType.ANIM_SPECIAL]

    data_type: DataType = DataType.CHARACTER
    lang_type: LangTypeSur = LangTypeSur.CHARACTER

    save_image_prefix = "Sprite"
    save_icon_prefix = "Select"

    key_main_texture_name = "textureName"
    key_sprite_name = "spriteName"
    key_frame_name = None
    key_entry_name = FULL_CHARACTER_NAME
    key_frame_rate_name = "walkFrameRate"

    key_secondary_texture_name = CHAR_SEL_TEXTURE
    key_secondary_sprite_name = CHAR_SEL_FRAME

    default_frame_name = "CharacterSelectFrame.png"
    default_text_stroke_width = 0.7

    _weapon_image_gen: WeaponImageGenerator = WeaponImageGenerator(None, {})

    def __init__(self, dlc_type: DLC | COMPOUND_DATA_TYPE, requested_gens: dict[GenType, int | bool]):
        if not CharacterImageGenerator._weapon_image_gen._is_initialized:
            CharacterImageGenerator._weapon_image_gen = WeaponImageGenerator(COMPOUND_DATA,
                                                                             {GenType.IMAGE: 1})

        super().__init__(dlc_type, requested_gens)

        if requested_gens.get(GenType.IMAGE_FRAME):
            self.frame_image = image_open(to_source_path(IMAGES_FOLDER) / self.default_frame_name)

    def _set_entries(self):
        super()._set_entries()

        lang_data_full = LangHandler.get_lang_file(LangTypeSur.SKIN)
        self.lang_skin_data: dict[str, Any] = lang_data_full.get_lang(Lang.EN) if lang_data_full else {}

        self.base_entries = self.entries.copy()
        self.skin_entries = self.get_skin_entries(self.entries)
        self.entries = list(filter(lambda x: x.get(SKIN_TYPE, DEFAULT) == DEFAULT, self.skin_entries))

        self.weapon_skin_entries = []
        self.select_entries = []
        self.select_skin_entries = []
        self.weapon_select_skin_entries = []
        self.special_anim_entries = []
        self.special_anim_skin_entries = []

        if self.requested_gens.get(GenType.CHARACTER_SKINS):
            self.weapon_skin_entries = self.get_weapon_entries(self.skin_entries)

        if self.requested_gens.get(GenType.CHARACTER_SPECIAL_SELECT):
            self.select_entries = self.get_select_entries(self.entries)
            if self.requested_gens.get(GenType.CHARACTER_SKINS):
                self.select_skin_entries = self.get_select_entries(self.skin_entries)
                self.weapon_select_skin_entries = self.get_weapon_entries(self.select_skin_entries)

        if self.requested_gens.get(GenType.ANIM_SPECIAL):
            self.special_anim_entries = self.get_special_anim_entries(self.entries)
            if self.requested_gens.get(GenType.CHARACTER_SKINS):
                self.special_anim_skin_entries = self.get_special_anim_entries(self.skin_entries)

    def get_textures_set(self, entries: list[dict[str, Any]] | None = None) -> set[str | None]:
        textures_set = super().get_textures_set(self.skin_entries)
        textures_set.update({entry.get(self.key_secondary_texture_name) for entry in self.skin_entries})
        return textures_set

    def main_generator(self) -> None:
        super().main_generator()

        self.generation_loop(
            entries=self.select_entries,
            gen_function=self.gen_image,
            add_to_path="Special",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SPECIAL_SELECT})

        self.generation_loop(
            entries=self.select_entries,
            gen_function=self.gen_image_with_frame,
            add_to_path="Select/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SPECIAL_SELECT})

        self.generation_loop(
            entries=self.skin_entries,
            gen_function=self.gen_image,
            add_to_path="Skin",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS})

        self.generation_loop(
            entries=self.skin_entries,
            gen_function=self.gen_image_with_frame,
            add_to_path=f"Skin/{self.save_icon_prefix}",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS})
        self.generation_loop(
            entries=self.weapon_skin_entries,
            gen_function=self.gen_image_with_frame,
            add_to_path=f"Skin/Weapon/{self.save_icon_prefix}",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS})

        self.generation_loop(
            entries=self.select_skin_entries,
            gen_function=self.gen_image,
            add_to_path="Skin/Special",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT})

        self.generation_loop(
            entries=self.select_skin_entries,
            gen_function=self.gen_image_with_frame,
            add_to_path=f"Skin/{self.save_icon_prefix}/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT})
        self.generation_loop(
            entries=self.weapon_select_skin_entries,
            gen_function=self.gen_image_with_frame,
            add_to_path=f"Skin/Weapon/{self.save_icon_prefix}/Special",
            required_gen_types={GenType.IMAGE_FRAME, GenType.CHARACTER_SKINS, GenType.CHARACTER_SPECIAL_SELECT})

        ####
        self.generation_loop(
            entries=self.skin_entries,
            gen_function=self.gen_anim,
            add_to_path=f"Skin/{self.save_anim_prefix}",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS, GenType.ANIM})

        self.generation_loop(
            entries=self.special_anim_entries,
            gen_function=self.gen_anim,
            add_to_path=f"{self.save_anim_prefix} Special",
            required_gen_types={GenType.IMAGE, GenType.ANIM_SPECIAL})

        self.generation_loop(
            entries=self.special_anim_skin_entries,
            gen_function=self.gen_anim,
            add_to_path=f"Skin/{self.save_anim_prefix} Special",
            required_gen_types={GenType.IMAGE, GenType.CHARACTER_SKINS, GenType.ANIM_SPECIAL})

    def get_skin_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        skin_entries = []
        for entry in entries:
            key_id = entry[KEY_ID]
            char_skins = entry.get("skins")

            if not char_skins:
                char_skins = [entry]

            for skin in char_skins:
                skin_entry = dict(**entry)
                skin_entry.update(skin)

                lang_entry = self.lang_data.get(key_id, {}) if self.lang_data else {}
                skin_type = skin_entry.get(SKIN_TYPE, DEFAULT)
                skin_lang_entry = self.lang_skin_data and self.lang_skin_data.get(skin_type) or {}

                prefix = language_sur.get_lang_value(skin_lang_entry, PREFIX) \
                         or language_sur.get_lang_value(lang_entry, PREFIX) \
                         or skin_entry.get(PREFIX)
                char_name = language_sur.get_lang_value(lang_entry, CHAR_NAME) \
                            or skin_entry.get(CHAR_NAME)
                surname = language_sur.get_lang_value(lang_entry, SURNAME) \
                          or skin_entry.get(SURNAME)
                suffix = language_sur.get_lang_value(skin_lang_entry, SUFFIX) \
                         or skin_entry.get(SUFFIX)

                skin_entry.update({
                    PREFIX: prefix or "",
                    CHAR_NAME: char_name or "",
                    SURNAME: surname or "",
                    SUFFIX: suffix or "",
                    FULL_CHARACTER_NAME: " ".join(filter(None, [prefix, char_name, surname])),
                    SKIN_TYPE: skin_type,
                    SAVE_POSTFIX: f" {suffix}" if suffix else None,
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
                weapon_lang_data = CharacterImageGenerator._weapon_image_gen.lang_data
                weapon_lang = language_sur.get_lang_value(weapon_lang_data, weapon_id, 'name')

                if weapon_lang is None:
                    print(f"Not found weapon [ID={weapon_id}] for character {key_id}")
                    continue

                weapon_entry = dict(**entry)
                weapon_entry[SAVE_POSTFIX] = f" ({weapon_lang})"
                weapon_entries.append(weapon_entry)

        return weapon_entries

    def get_special_anim_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        special_anim_entries = []

        for entry in entries:
            key_id = entry.get(KEY_ID)

            for anim_name, anim_data in entry.get("spriteAnims", dict()).items():
                anim_entry = {**entry}
                anim_name = re.findall('.[^A-Z]*', anim_name)
                anim_name[0] = anim_name[0].title()

                anim_entry.update(anim_data)
                anim_entry.update({
                    self.key_entry_name: f"{entry[self.key_entry_name]} ({' '.join(anim_name)})",
                    self.key_frame_rate_name: anim_entry.get("frameRate"),
                })

                special_anim_entries.append(anim_entry)

        return special_anim_entries

    def get_unit(self, key_id: str, entry: list[dict[str, Any]]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        lang_entry = self.lang_data and self.lang_data.get(key_id) or {}
        prefix = language_sur.get_lang_value(lang_entry, PREFIX)
        char_name = language_sur.get_lang_value(lang_entry, CHAR_NAME)
        surname = language_sur.get_lang_value(lang_entry, SURNAME)

        if char_name is None:
            prefix = entry.get(PREFIX)
            char_name = entry.get(CHAR_NAME)
            surname = entry.get(SURNAME)
            if char_name:
                entry[ADD_TO_PATH_ENTRY1] = "Data name"

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

        char_sprite = resize_image(out_image_data.sprite_data.sprite, 3.8)
        frame_image = self.frame_image.copy()

        if (weapon_id := entry.get("startingWeapon", 0)) and weapon_id not in ["VOID", "0", 0, None]:
            weapon_image_gen = CharacterImageGenerator._weapon_image_gen
            weapon_data = weapon_image_gen.data_file.data().get(weapon_id)
            if weapon_data is None:
                print(f"Not found weapon [ID={weapon_id}] for character {out_image_data.name}")
                return None

            weapon_entry = weapon_image_gen.gen_image(weapon_image_gen.get_unit(weapon_id, weapon_data))

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

        text = entry[CHAR_NAME]

        image_text = image_functions.get_wrapped_text(
            text,
            FONT_FILE_PATH,
            (frame_image.size[0] - 30, frame_image.size[1]),
            (20, 30)
        )
        image_text.stroke(
            width=self.requested_gens.get(GenType.TEXT_STROKE_WIDTH, self.default_text_stroke_width),
            fill="#ffffff"
        )

        canvas = image_new('RGBA', frame_image.size)
        draw = ImageDraw.Draw(canvas)
        draw.text((3, 5), image_text)

        frame_image.alpha_composite(canvas, (14, 10))

        return ImageEntryToSave(
            frame_image,
            out_image_data.name.w(prefix=self.get_save_icon_prefix(entry)),
        )


_UNDERSCORE_DIGITS = re.compile(r"_(\d+)$")
_UNDERSCORE_I_DIGITS = re.compile(r"_i(\d+)$")


class EnemyImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE,
                                      GenType.ANIM, GenType.ANIM_DEATH]

    data_type: DataType = DataType.ENEMY
    lang_type: LangTypeSur = LangTypeSur.ENEMIES

    save_image_prefix = "Sprite"

    key_main_texture_name = "textureName"
    key_sprite_name = "frameNames"
    key_frame_name = None
    key_entry_name = "bName"

    key_frame_rate_name = "_frame_rate"

    death_anim_frame_rate = 20

    def _set_entries(self):
        super()._set_entries()

        self.base_entries = self.entries.copy()
        self.bestiary_entries_death, self.non_bestiary_entries_death = self.get_split_entries_death(self.entries_dict)
        self.entries = self.get_sprite_entries(self.bestiary_entries_death)
        self.non_bestiary_entries = self.get_sprite_entries(self.non_bestiary_entries_death)

    def get_textures_set(self, entries: list[dict[str, Any]] | None = None) -> set[str | None]:
        textures_set = super().get_textures_set(self.base_entries)
        return textures_set

    def main_generator(self) -> None:
        super().main_generator()

        self.generation_loop(
            entries=self.non_bestiary_entries,
            gen_function=self.gen_image,
            add_to_path="Not in bestiary",
            required_gen_types={GenType.IMAGE})
        self.generation_loop(
            entries=self.non_bestiary_entries,
            gen_function=self.gen_anim,
            add_to_path=f"Not in bestiary/{self.save_anim_prefix}",
            required_gen_types={GenType.IMAGE, GenType.ANIM})

        self.generation_loop(
            entries=self.bestiary_entries_death,
            gen_function=self.gen_anim,
            add_to_path="Death Animated",
            required_gen_types={GenType.IMAGE, GenType.ANIM_DEATH})
        self.generation_loop(
            entries=self.non_bestiary_entries_death,
            gen_function=self.gen_anim,
            add_to_path="Death Animated/Not in bestiary",
            required_gen_types={GenType.IMAGE, GenType.ANIM_DEATH})

    def get_split_entries_death(self, entries_dict: dict[str, dict[str, Any]]) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]]]:
        bestiary_entries = []
        bestiary_k_ids = set()

        def sprite_to_death_sprite(s: str) -> str:
            s = s.replace(".png", "")
            return _UNDERSCORE_I_DIGITS.sub("_0", s)

        for key_id, entry in entries_dict.items():
            if not entry.get("bInclude"):
                continue

            b_variants = {key_id}.union(entry.get("bVariants", []))
            bestiary_k_ids.update(b_variants)

            frame_names: set[tuple[str, str]] = set()
            for variant_k_id in b_variants:
                variant_entry = entries_dict.get(variant_k_id)
                if variant_entry is None:
                    continue
                frame_names.update(zip(
                    itertools.repeat(variant_entry[self.key_main_texture_name]),
                    variant_entry[self.key_sprite_name]
                ))

            for idx, (texture_name, sprite_name) in enumerate(frame_names):
                postfix = '' if idx < 1 else f'-{idx + 1}'
                b_name = f"{entry[self.key_entry_name]}{postfix}"

                entry_sprite = entry.copy()
                entry_sprite.update({
                    self.key_entry_name: b_name,
                    self.key_main_texture_name: texture_name,
                    self.key_sprite_name: sprite_to_death_sprite(sprite_name),
                    self.key_frame_rate_name: self.death_anim_frame_rate,
                    SAVE_POSTFIX: f' (death)',
                })
                bestiary_entries.append(entry_sprite)

        non_bestiary_entries = []
        for key_id, entry in entries_dict.items():
            if key_id in bestiary_k_ids:
                continue

            for sprite_name in entry["frameNames"]:
                entry_sprite = entry.copy()
                entry_sprite.update({
                    self.key_sprite_name: sprite_to_death_sprite(sprite_name),
                    self.key_frame_rate_name: self.death_anim_frame_rate,
                    SAVE_POSTFIX: f' (death)',
                })
                non_bestiary_entries.append(entry_sprite)

        return bestiary_entries, non_bestiary_entries

    def get_sprite_entries(self, entries_death: list[dict[str, Any]]):
        sprite_entries = []

        for entry in entries_death:
            sprite_entry = entry.copy()
            del sprite_entry[self.key_frame_rate_name]
            del sprite_entry[SAVE_POSTFIX]

            sprite_name = sprite_entry[self.key_sprite_name].replace(".png", "")
            sprite_entry[self.key_sprite_name] = _UNDERSCORE_DIGITS.sub("_i01", sprite_name)
            sprite_entries.append(sprite_entry)

        return sprite_entries


class StageImageGenerator(ListBaseImageGenerator):
    _available_gens: list[GenType] = [GenType.IMAGE, GenType.STAGE_WITH_NAME, GenType.TEXT_STROKE_WIDTH]

    data_type: DataType = DataType.STAGE
    lang_type: LangTypeSur = LangTypeSur.STAGE

    default_scale_factor = 1

    save_image_prefix = "Stage"

    key_main_texture_name = "uiTexture"
    key_sprite_name = "uiFrame"
    key_frame_name = None
    key_entry_name = "stageName"

    def main_generator(self) -> None:
        super().main_generator()

        self.generation_loop(
            entries=self.entries,
            gen_function=self.gen_image_with_name,
            add_to_path="With name",
            required_gen_types={GenType.STAGE_WITH_NAME})

    def gen_image_with_name(self, entry: dict[str, Any]) -> ImageEntryToSave | None:
        out_image_data: SpriteEntryToSave | None = self.gen_image(entry)
        if out_image_data is None:
            return None

        image_data = out_image_data.sprite_data

        stage_image = resize_image(image_data.sprite, 4)

        text = out_image_data.name.name.strip()

        image_text = image_functions.get_wrapped_text(
            text,
            FONT_FILE_PATH,
            (stage_image.size[0] - 40, 0),
            (30, 50)
        )
        image_text.stroke(width=self.requested_gens.get(GenType.TEXT_STROKE_WIDTH, self.default_text_stroke_width))

        *_, w, h = image_text.get_bbox()
        w = int(w)
        h = int(h)

        canvas = image_new('RGBA', (w, h))

        draw = ImageDraw.Draw(canvas)
        draw.text((w // 2, h // 2), image_text, fill="#eef92b", anchor="mm")

        im_w, im_h = stage_image.size

        stage_image.alpha_composite(canvas, ((im_w - w) // 2, int(im_h * 0.19) - h // 2))

        return ImageEntryToSave(
            stage_image,
            out_image_data.name.w(prefix=self.get_save_image_postfix(entry)),
        )


class AdventureStageImageGenerator(StageImageGenerator):
    data_type: DataType = DataType.ADVENTURE_STAGE

    stage_set: DataFile
    stage_to_stage_set: dict[str, str]

    def _set_entries(self):
        assert self.dlc_type is not None

        self.stage_set: DataFile | None = DataHandler.get_data(self.dlc_type, DataType.ADVENTURE_STAGE_SET)

        assert self.stage_set is not None

        self.stage_to_stage_set = {
            stage: stage_set
            for stage_set, stages in self.stage_set.data().items()
            for stage in stages
        }

        super()._set_entries()

    def get_unit(self, key_id: str, entry: list[dict[str, Any]]) -> dict[str, Any]:
        entry = super().get_unit(key_id, entry)
        entry.update({
            ADD_TO_PATH_ENTRY2: self.stage_to_stage_set[key_id],
        })
        return entry
