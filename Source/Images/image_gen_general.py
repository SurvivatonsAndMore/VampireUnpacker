import itertools
from pathlib import Path

from Source.Config.config import Game
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Images import transparent_save
from Source.Utility.constants import IMAGES_FOLDER, GENERATED, PROGRESS_BAR_FUNC_TYPE, DEFAULT_ANIMATION_FRAME_RATE, \
    PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.image_functions import resize_image, get_anim_sprites_ready, resize_list_images
from Source.Utility.popups import ErrorPopup, InfoPopup


def generate_images_by_meta(
        image_path: Path,
        scale_factor: int = 1,
        folder_save_path: Path | None = None,
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path | None:
    file = image_path.name

    print(f"Generating {file} by meta")

    if not MetaDataHandler.is_loaded():
        MetaDataHandler.load(Game.SPECIAL)

    meta_path = image_path.with_name(file + ".meta")
    if not MetaDataHandler.has_meta_by_path(meta_path):
        if not meta_path.exists():
            raise ErrorPopup("Error", f"Meta data file {meta_path} does not exist")
        MetaDataHandler.add_meta_data_by_path(meta_path)

    data = MetaDataHandler.get_meta_by_name(file)
    data.init_sprites()

    total_len = len(data.data_name)

    folder_save_path = folder_save_path or to_current_game_path(IMAGES_FOLDER) / GENERATED / "_By meta Image"
    if total_len > 1:
        folder_save_path /= image_path.stem
    else:
        folder_save_path /= "_SingeSprites"

    folder_save_path.mkdir(parents=True, exist_ok=True)

    print(f"Files out of {total_len}:")
    func_progress_bar_set_percent(0, total_len)

    for i, (_, sprite_data) in enumerate(data.data_name.items()):
        if sprite_data.sprite is None:
            print(f"Sprite {sprite_data.name} not loaded")
            continue
        sprite = resize_image(sprite_data.sprite, scale_factor)
        sprite.save(folder_save_path / f"{sprite_data.real_name}.png")

        print(f"\r{i + 1}", end="")
        func_progress_bar_set_percent(i + 1, total_len)

    print()
    return folder_save_path.absolute()


def generate_animation_by_meta(
        image_path: Path,
        scale_factor: int = 1,
        frame_rate: int = DEFAULT_ANIMATION_FRAME_RATE,
        selected_anim_types: list[bool] | None = None,
        folder_save_path: Path | None = None,
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> Path | None:
    file = image_path.name

    if not selected_anim_types or not any(selected_anim_types):
        print("Not selected any animation extension")
        return None

    if not MetaDataHandler.is_loaded():
        MetaDataHandler.load(Game.SPECIAL)

    meta_path = image_path.with_name(file + ".meta")
    if not MetaDataHandler.has_meta_by_path(meta_path):
        if not meta_path.exists():
            raise ErrorPopup("Error", f"Meta data file {meta_path} does not exist")
        MetaDataHandler.add_meta_data_by_path(meta_path)

    data = MetaDataHandler.get_meta_by_name(file)

    if not data:
        raise ErrorPopup("Error", f"MetaData not found for {file}")

    animations = data.get_animations()

    total_len = len(animations)

    if not total_len:
        raise InfoPopup("Info", f"Not found animations for {file}")

    anim_types = transparent_save.ANIM_SAVE_TYPES

    print(f"Generating {file} by meta")

    selected_types = list(itertools.compress(anim_types, selected_anim_types))
    print(f"Selected {scale_factor=}, {frame_rate=}, selected extensions={selected_types}")

    folder_save_path = folder_save_path or to_current_game_path(IMAGES_FOLDER) / GENERATED / "_By meta Anim"
    if total_len > 1:
        folder_save_path = folder_save_path / image_path.stem
    else:
        folder_save_path = folder_save_path / "_SingeAnimations"

    folder_save_path.mkdir(parents=True, exist_ok=True)

    duration = 1000 // frame_rate

    print(f"Animations out of {total_len}:")
    func_progress_bar_set_percent(0, total_len)

    for i, anim in enumerate(animations):
        sprites_list = get_anim_sprites_ready(anim)
        sprites_list = resize_list_images(sprites_list, scale_factor)

        for ext, folder, func in itertools.compress(transparent_save.SAVE_DATA, selected_anim_types):
            path = folder_save_path / folder
            path.mkdir(exist_ok=True)
            func(sprites_list, duration, path / f"{anim.name}{ext}")

        print(f"\r{i + 1}", end="")
        func_progress_bar_set_percent(i + 1, total_len)

    print()
    return folder_save_path.absolute()
