import json
import sys

from Source.Config.config import PROJECT_SETTINGS, Game, DLC, Config
from Source.Data.meta_data import MetaDataHandler
from Source.Utility.constants import VERSION_DATA, VAMPIRE_SURVIVORS
from Source.Utility.unity_parser import UnityDoc
from Source.Utility.utility import get_parent_path_to, acf_to_json, to_pascalcase


def get_game_bundle_version() -> str | None:
    MetaDataHandler.assert_loaded_game()

    proj_settings = MetaDataHandler.get_path_by_name_no_meta(PROJECT_SETTINGS)
    if not proj_settings:
        return None

    doc = UnityDoc.yaml_parse_file_smart(proj_settings)
    if not doc:
        return None

    return doc.entry.data['bundleVersion']


def get_game_build_version() -> tuple[str | None, str | None]:
    MetaDataHandler.assert_loaded_game()

    version_data = MetaDataHandler.get_path_by_name_no_meta(VERSION_DATA)
    if not version_data:
        return None, None

    doc = UnityDoc.yaml_parse_file_smart(version_data)
    if not doc:
        return None, None

    data = doc.entry.data
    return data['_BuildId'], data['_BuildTime']


def get_dlc_version() -> list[tuple[DLC, str, str]]:
    MetaDataHandler.assert_loaded_game()

    assets = []
    match MetaDataHandler.loaded_game:
        case Game.VS:
            assets = [
                (dlc, to_pascalcase(dlc.value.code_name))
                for dlc in DLC.get_all_types_by_game(Game.VS, is_game_sorting=True)[1:]
            ]
            print(assets)
        case Game.VC:
            pass  ## Not implemented; not any DLC yet

    result = []
    for dlc, asset in assets:
        bundle = MetaDataHandler.get_path_by_name_no_meta_suffixes(asset, 'asset')
        if not bundle:
            print(f"Not found asset ({asset}) for DLC ({dlc})", file=sys.stderr)
            continue

        doc = UnityDoc.yaml_parse_file(bundle)
        data = doc.entry.data

        result.append((dlc, data['_Title'], data['_ExpectedVersion']))

    return result


def get_appmanifest(app_id: int | None = None) -> dict[str, str] | None:

    STEAMAPPS = "steamapps"

    MetaDataHandler.assert_loaded_game()

    game: Game = MetaDataHandler.loaded_game

    path = Config[game.value.steam_folder]
    path = get_parent_path_to(path, STEAMAPPS)

    if path is None or path.stem != STEAMAPPS:
        print(f"Not found steamapps path for {game}", file=sys.stderr)
        return None

    app_id = app_id or game.value.appid

    path /= f"appmanifest_{app_id}.acf"

    if not path.exists():
        print(f"Not found appmanifest path for {game} ({app_id})", file=sys.stderr)
        return None

    with open(path) as f:
        text = acf_to_json(f.read())
        text = json.loads(text)

    return text


def load_version_file(app_manifest: dict[str, str]):
    MetaDataHandler.assert_loaded_game()

    data_folder_key = MetaDataHandler.loaded_game.value.data_folder
    Config.assert_key(data_folder_key)
    data_folder = Config[data_folder_key]

    loaded_game = MetaDataHandler.loaded_game

    text = "SHOULD NOT BE PRINTED"
    match loaded_game:
        case Game.VC:
            build_info = MetaDataHandler.get_path_by_name_no_meta_suffixes("BuildInfo", 'txt')
            if not build_info:
                return None

            text = build_info.read_text() + "\n"

        case Game.VS | Game.WRHS | Game.JJKRS:
            game_version = get_game_bundle_version()
            build_num, build_time = get_game_build_version()
            dlc_list = get_dlc_version()

            text = ""
            for dlc, name, version in dlc_list:
                text += f"{name} - {version}\n"
            text = f"{loaded_game.get_default_dlc().value.full_name} - {game_version}\n" + text
            text += f"{build_time} [{build_num}{'R' if loaded_game == Game.VS else ''}]\n"

    manifest = app_manifest

    if manifest:
        assert manifest['buildid'] == manifest['TargetBuildID'], "Build ID and Target build ID do not match"

        text += "\n"
        text += f"\nappid - {int(manifest['appid'])}"
        text += f"\nbuildid - {int(manifest['buildid'])}"

        text += "\n\n\nInstalledDepots:"
        for depot, depot_data in manifest['InstalledDepots'].items():
            text += f"\n{int(depot)} - manifest: {depot_data['manifest']}"

    with open(data_folder / 'Game Version.txt', 'w') as f:
        print(text, file=f)

    return None


if __name__ == "__main__":
    # MetaDataHandler.load(Game.VS)
    MetaDataHandler.load(Game.VC)

    load_version_file()
