from __future__ import annotations

import functools
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal, Any

import mutagen
import numpy as np
import soundfile as sf

import Source.Data.data_sur as data_module
import Source.Translations.language_sur as language_vs
from Source.Config.config import DLC
from Source.Data.data_sur import DataType
from Source.Data.meta_data import MetaDataHandler, to_current_game_path
from Source.Translations.language_sur import LangTypeSur
from Source.Translations.language_utils import Lang
from Source.Utility.constants import GENERATED, COMPOUND_DATA, AUDIO_FOLDER, COMPOUND_DATA_TYPE, PROGRESS_BAR_FUNC_TYPE, \
    PROGRESS_BAR_FUNC_DEFAULT
from Source.Utility.multirun import map_multiprocess, starmap_multiprocess, \
    starmap_multithread, map_multithread
from Source.Utility.timer import Timeit
from Source.Utility.unity_parser import UnityDoc
from Source.Utility.utility import normalize_str

ARTIST = "artist"
ALBUM = "album"
SOURCE = "comment"
TITLE = "title"


class AudioSaveType(Enum):
    CODE_NAME = "Code names"
    TITLE_NAME = "Audio titles"
    RELATIVE_NAME = "Relative object names"

    @classmethod
    def get(cls):
        return [*cls]

    def __str__(self):
        return self.value


def _get_music_playlists() -> list[dict[str, Any]]:
    search_list = ["MasterAudio", "DynamicSoundGroup", "ProjectContext"]

    def flt(tuple_s_p: tuple[str, Path]):
        s, _ = tuple_s_p
        return any(normalize_str(search) in normalize_str(s) for search in search_list)

    audio_prefabs = MetaDataHandler.filter_paths(flt)
    audio_prefabs = set(dict(audio_prefabs).values())

    timeit = Timeit()
    print(f"Parsing audio prefabs ({len(audio_prefabs)})... ", end=" ")

    args_load = (audio_prefab.with_suffix("") for audio_prefab in audio_prefabs)
    all_unity_playlists = map_multiprocess(UnityDoc.yaml_parse_file_smart, args_load)

    print(f"Finished parsing audio prefabs {timeit!r}")

    music_playlists: list[dict[str, Any]] = [
        entry
        for unity_playlist in all_unity_playlists
        for playlist in unity_playlist.filter(class_names=('MonoBehaviour',), attributes=("musicPlaylists",))
        for entry in playlist.get("musicPlaylists")
    ]

    return music_playlists


def _get_audio_clips_paths() -> set[Path]:
    def flt(tuple_s_p: tuple[str, Path]):
        _, p = tuple_s_p
        return p.match("*/AudioClip/*")

    audio_clips = MetaDataHandler.filter_paths(flt)
    return set(map(lambda x: x.with_suffix(""), dict(audio_clips).values()))


def _export_soundfile(data: np.ndarray, samplerate: int, out_path: Path, ext: str, tags: dict | None = None):
    chunk_size = 8192
    try:
        with sf.SoundFile(
                out_path, mode='w', samplerate=samplerate,
                channels=data.shape[1] if data.ndim > 1 else 1,
                format=ext.upper()
        ) as f:
            for i in range(0, len(data), chunk_size):
                f.write(data[i:i + chunk_size])
        #     sf.write(out_path, data.astype(np.float32), self.samplerate, format=ext.upper())
    except Exception as e:
        print(f"Warning: Could not write {out_path.name} as {ext}. Error: {e}")
        return

    if tags:
        try:
            audio = mutagen.File(out_path, easy=True)
            if audio is not None:
                audio.update(tags)
                audio.save()
        except Exception as e:
            print(f"Warning: Could not write tags to {out_path.name}: {e}")


@dataclass
class MusicTrack:
    audio_clips_paths: list[Path]
    tags: dict[Literal["artist", "album", "title", "comment"], str]
    code_name: str
    ext: str
    content_group: str
    has_same_name: bool

    def get_code_name_ext(self):
        return f"{self.code_name}.{self.ext}"

    def is_valid(self):
        return len(self.audio_clips_paths) and all(clip.exists() for clip in self.audio_clips_paths)

    def save_track(self: MusicTrack, save_path: Path) -> None:
        if not self.ext:
            return

        read_audio = functools.partial(sf.read, always_2d=True)
        clip_datas: list[tuple[np.ndarray, int]] = map_multithread(read_audio, self.audio_clips_paths)
        if not clip_datas:
            return

        samplerate = clip_datas[0][1]
        if any(cd[1] != samplerate for cd in clip_datas):
            print(f"{self} clip files does not have same samplerate. Skipping")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)

        full_data = np.concatenate([cd[0] for cd in clip_datas], axis=0)

        _export_soundfile(full_data, samplerate, save_path, self.ext, tags=self.tags)

        return


def _get_music_track(audio_clips: dict[str, Path], music_data: dict[str, Any], playlist_data) -> MusicTrack:
    code_name = playlist_data['playlistName']

    cur_data = music_data.get(code_name) or {}

    tags = {
        ARTIST: cur_data.get("author"),
        ALBUM: cur_data.get("source"),
        SOURCE: cur_data.get("source"),
        TITLE: cur_data.get("title")
    }
    if None in tags.values():
        tags = {}

    song_name_main = normalize_str(playlist_data['MusicSettings'][0]['songName'])

    is_vs = True
    found_songs = list(filter(lambda k_v: song_name_main + "_" in normalize_str(k_v[0])
                                          or song_name_main == normalize_str(k_v[0]), audio_clips.items()))
    if len(found_songs) > 1:
        is_vs = "_vs_" in normalize_str(code_name) or " - Vampire Survivors" in tags.get(TITLE, "")
        if is_vs:
            print(f"Found songs with duplicate names: {found_songs}. Separating them by their file sizes.")

        found_songs = list(sorted(found_songs, key=lambda k_v: k_v[-1].stat().st_size, reverse=is_vs))

    song_name_current = normalize_str(found_songs[0]) if found_songs else song_name_main

    has_same_name = not is_vs

    clips = []
    ext = ""
    for setting in playlist_data['MusicSettings']:
        song_name = normalize_str(setting['songName'])

        song_name = song_name_current.replace(song_name_main, song_name)

        clip_data = audio_clips.get(song_name)
        if not clip_data:
            print(f"Music track not found by song ({song_name=} ;; {setting['songName']=})")
            continue
        else:
            ext = clip_data.suffix.replace(".", "")

        clips.append(clip_data)

    content_group = cur_data and cur_data.get("contentGroup", "BASE_GAME") or "UNCATEGORIZED"

    return MusicTrack(clips, tags, code_name, ext, content_group, has_same_name)


def gen_music_tracks(
        music_dlc: DLC | COMPOUND_DATA_TYPE,
        save_name_types: set[AudioSaveType],
        func_progress_bar_set_percent: PROGRESS_BAR_FUNC_TYPE = PROGRESS_BAR_FUNC_DEFAULT
) -> tuple[str, None] | tuple[None, str]:
    save_name_types.add(AudioSaveType.CODE_NAME)

    f_path = to_current_game_path(AUDIO_FOLDER)

    save_path = f_path / GENERATED

    music_data = data_module.DataHandler.get_data(music_dlc, data_module.DataType.MUSIC).data()

    datas = {}
    convert: dict[str, set[tuple[str, str, bool]]] = {}
    bgm_keys = ["bgm", "BGM", "sideBBGM"]
    if AudioSaveType.RELATIVE_NAME in save_name_types:
        not_found = []
        data_files: dict[str, tuple[LangTypeSur, str, str, DataType | None]] = {
            "unlockedByStage": (LangTypeSur.STAGE, "stageName", "Stage", DataType.STAGE),
            "unlockedByCharacter": (LangTypeSur.CHARACTER, "charName", "Character", DataType.CHARACTER),
            "unlockedByItem": (LangTypeSur.ITEM, "name", "Item", None),
        }

        for data_key, items in data_files.items():
            lang_type = items[0]
            en_lang = language_vs.LangHandler.get_lang_file(lang_type).get_lang(Lang.EN)
            dat = data_module.DataHandler.get_data(COMPOUND_DATA, items[3])
            if dat:
                dat = dat.data()
                for data_entry_id, vv in dat.items():
                    for bgm_key in bgm_keys:
                        if bgm := vv[0].get(bgm_key):
                            if bgm not in convert:
                                convert[bgm] = set()

                            is_b_side = (bgm_key == bgm_keys[-1]) and (
                                    convert[bgm] not in (data_key, data_entry_id, False))

                            convert[bgm].add((data_key, data_entry_id, is_b_side))

            datas.update({data_key: {
                "lang": en_lang,
                "key": items[1],
                "type": items[2]
            }})

        if len(datas) < len(data_files):
            return None, f"! Not found split lang files for relative generator: {not_found}"

    music_playlists = _get_music_playlists()

    audio_clips_path = _get_audio_clips_paths()
    audio_clips = {normalize_str(ac): ac for ac in audio_clips_path}

    total_len = len(music_playlists)

    print(f"Searching {total_len} tacks")

    args_gen_tracks = (
        (audio_clips, music_data, playlist_data)
        for playlist_data in music_playlists
    )
    timeit = Timeit()

    audio_tracks: list[MusicTrack] = starmap_multiprocess(_get_music_track, args_gen_tracks)
    audio_tracks = list(filter(MusicTrack.is_valid, audio_tracks))

    print(f"Found {len(audio_tracks)} tacks {timeit!r}")

    def path_dest(s_type: AudioSaveType, m_track: MusicTrack, *other):
        return save_path.joinpath(str(s_type), m_track.content_group, *other)

    timeit = Timeit()
    print("Saving tracks with code names")

    args_save_tracks = [
        (music_track, path_dest(AudioSaveType.CODE_NAME, music_track) / music_track.get_code_name_ext())
        for music_track in audio_tracks
    ]
    starmap_multithread(MusicTrack.save_track, args_save_tracks, max_workers=8, progress=func_progress_bar_set_percent)

    # for i, music_track in enumerate(audio_tracks):
    #     _save_track(music_track, path_dest(AudioSaveType.CODE_NAME, music_track) / music_track.get_code_name_ext())
    #     func_progress_bar_set_percent(i, len(audio_tracks))

    print(f"Saved tracks with code names {timeit!r}")

    if not save_name_types.difference({AudioSaveType.CODE_NAME}):
        return save_path, None

    timeit = Timeit()
    print("Saving tracks with other names:")

    already_generated = dict()
    for kk, (music_track, code_name_path) in enumerate(args_save_tracks):
        code_name = music_track.code_name
        tags = music_track.tags
        has_same_name = music_track.has_same_name
        ext = music_track.ext

        cur_data = music_data.get(code_name) or {}

        if AudioSaveType.TITLE_NAME in save_name_types and (title := tags.get(TITLE)):
            title_add = ""
            if (source := tags.get(SOURCE)) and ("Castlevania" in source):
                title_add = " (" + source.replace("Castlevania", "").strip() + ")"

            save_name = f"{title}{title_add}.{ext}"

            shutil.copy(code_name_path, path_dest(AudioSaveType.TITLE_NAME, music_track, save_name))
            shutil.copy(code_name_path,
                        path_dest(AudioSaveType.TITLE_NAME, music_track, "prefix", "Audio-" + save_name))

        if AudioSaveType.RELATIVE_NAME in save_name_types:

            related_objects: set = convert.get(code_name) or set()
            for data_key in ["unlockedByItem"]:
                if data_entry_id := cur_data.get(data_key):
                    related_objects.add((data_key, data_entry_id, ""))

            for data_key, data_entry_id, is_b_side in related_objects:
                key_name = datas[data_key]["key"]
                cur_type = datas[data_key]["type"]
                cur_obj = datas[data_key]["lang"].get(data_entry_id) or {}

                name = language_vs.get_lang_value(cur_obj, key_name) or code_name
                surname = language_vs.get_lang_value(cur_obj, 'surname') or " "
                prefix = language_vs.get_lang_value(cur_obj, 'prefix') or " "

                space2 = surname[0] not in [":", ","] and " " or ""
                name = f"{prefix} {name}{space2}{surname}".strip()

                # if prefix := cur_obj.get('prefix'):
                #     flt = lambda x: x and not x.get("prefix") and x.get("charName") == name
                #
                #     main_object = list(filter(flt, datas["unlockedByCharacter"]["lang"].values()))
                #     if main_object or "megalo" in prefix.lower():
                #         name = f"{prefix} {name}"

                if has_same_name or is_b_side:
                    name += " B"

                def pst(ii):
                    return ii if ii > 0 else ""

                j = 0
                save_name = f"{name}{pst(j)}.{ext}"
                while save_name in already_generated:
                    j += 1
                    save_name = f"{name}{pst(j)}.{ext}"

                already_generated.update({save_name: True})

                shutil.copy(code_name_path, path_dest(AudioSaveType.RELATIVE_NAME, music_track, cur_type, save_name))
                shutil.copy(code_name_path, path_dest(AudioSaveType.RELATIVE_NAME, music_track, cur_type, "prefix",
                                                      "Audio-" + save_name))

        print(f"\r{kk + 1}", end="")
        func_progress_bar_set_percent(kk + 1, total_len)

    print(f"\nFinished saving tracks with other names {timeit!r}")
    return save_path, None


if __name__ == "__main__":
    gen_music_tracks(COMPOUND_DATA, set())
