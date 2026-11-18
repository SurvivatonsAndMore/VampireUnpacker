import functools
import shutil
from pathlib import Path
from typing import Any

import Source.Audio.audio_gen_sur as audio_gen_sur
from Source.Data.data_sur import DataType
from Source.Data.meta_data import to_current_game_path
from Source.Images import image_gen_sur
from Source.Images.image_gen_types import GenType
from Source.Utility.constants import PROGRESS_BAR_FUNC_TYPE, PROGRESS_BAR_FUNC_DEFAULT, GENERATED, \
    AUDIO_FOLDER
from Source.Utility.utility import normalize_str

ANNOUNCER = "Announcer"


def get_announcer_data_types() -> tuple[tuple[DataType, ...], tuple[bool, ...]]:
    """
        Returns tuple of available data types and bools where to use image gen sur.
    """
    return (
        (DataType.CHARACTER, DataType.WEAPON, DataType.STAGE),
        (True, True, True)
    )


class AudioEntryToCopy(image_gen_sur.EntryToSave):
    source_path: Path

    def __init__(self, source_path: Path, name: image_gen_sur.NameToSave, add_to_path: str | None = None) -> None:
        super().__init__(name, add_to_path=add_to_path)
        self.source_path = source_path

    def _save(self, save_folder_path: Path, scale: int) -> None:
        shutil.copy(self.source_path, save_folder_path / self.name.str_ext(".ogg"))


def gen_announcer(
        self: type[image_gen_sur.BaseImageGenerator],
        audio_clips: dict[str, Path],
        entry: dict[str, Any]
) -> tuple[AudioEntryToCopy, ...]:
    key_id = entry[image_gen_sur.KEY_ID]
    skin_type = entry.get(image_gen_sur.SKIN_TYPE)

    code_name = skin_type if (skin_type and skin_type != image_gen_sur.DEFAULT) else key_id

    eng_name = entry[self.key_entry_name]

    out_entries = []

    for i in range(1, 20):
        code_name_i = f"{code_name}_{i}"
        path = audio_clips.get(normalize_str(code_name_i))
        if not path:
            break

        add_num = f"-{i}" if i > 1 else ""

        out_entries.append(
            AudioEntryToCopy(
                path,
                image_gen_sur.NameToSave(
                    ANNOUNCER,
                    eng_name,
                    self.get_save_image_postfix(entry) + add_num
                )
            )
        )

    return tuple(out_entries)


def gen_audio_announcer(
        data_type,
        selected_dlc,
        progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT,
):
    gen_class = image_gen_sur.ImageGeneratorManager.get_gen(data_type)

    audio_clips_path = audio_gen_sur.get_audio_clips_paths()
    audio_clips = {normalize_str(ac): ac for ac in audio_clips_path}

    save_path = to_current_game_path(AUDIO_FOLDER) / GENERATED / ANNOUNCER / data_type / str(selected_dlc)
    save_path.mkdir(parents=True, exist_ok=True)

    gen = gen_class(selected_dlc, {GenType.IMAGE: 0}, progress=progress_bar_set_percent)
    gen.save_path = save_path
    gen_function = functools.partial(gen_announcer, gen, audio_clips)

    match data_type:
        case DataType.CHARACTER:
            gen.generation_loop(
                entries=gen.skin_entries,
                gen_function=gen_function,
                display_type=ANNOUNCER,
            )

        case DataType.WEAPON:
            gen.generation_loop(
                entries=gen.entries,
                gen_function=gen_function,
                display_type=ANNOUNCER,
            )

        case DataType.STAGE:
            gen.generation_loop(
                entries=gen.entries,
                gen_function=gen_function,
                display_type=ANNOUNCER,
            )

        case _:
            assert False, f"Announcer data type {data_type} not supported"

    return save_path
