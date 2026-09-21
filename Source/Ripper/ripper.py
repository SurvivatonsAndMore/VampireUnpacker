import os
import shutil
import sys
import time
from pathlib import Path

import requests

from req_test import version_to_str, get_ripper_version
from Source.Config.config import CfgKey, Config, Game
from Source.Utility.constants import RIPPER_FOLDER, to_source_path
from Source.Utility.timer import Timeit
from Source.Utility.popups import ErrorPopup

ripper_port = 56636
ripper_url = f"http://127.0.0.1:{ripper_port}/"


def rip_files(games_to_rip: set[Game]):
    ripper_path: Path = Config[CfgKey.RIPPER]
    settings_name = "AssetRipper.Settings.json"

    ripper = None
    ripper_settings = None
    this_settings = to_source_path(RIPPER_FOLDER) / settings_name

    try:
        ripper = next(ripper_path.rglob("AssetRippe*.exe"))
    except StopIteration:
        pass

    try:
        ripper_settings = next(ripper_path.rglob("AssetRipper.Setting*[!(old)].json"))
    except StopIteration:
        pass

    if not ripper:
        _s = "AssetRipper not found"
        print(_s, file=sys.stderr)
        raise ErrorPopup("Ripper Error", _s)

    if empty_game_paths := [game for game in games_to_rip if Config[game.value.steam_folder] == Path()]:
        _s = f"Some config paths to steam folders are empty:\n{'\n'.join(map(str, empty_game_paths))}"
        print(_s, file=sys.stderr)
        raise ErrorPopup("Ripper Error", _s)

    if empty_asset_paths := [game for game in games_to_rip if Config[game.value.assets_folder] == Path()]:
        _s = f"Some config paths to asset folders are empty:\n{'\n'.join(map(str, empty_asset_paths))}"
        print(_s, file=sys.stderr)
        raise ErrorPopup("Ripper Error", _s)

    is_working = True
    try:
        requests.get(ripper_url)
    except requests.ConnectionError:
        is_working = False

    if not is_working:
        # copy existing setting, save as 'old' and copy needed settings in folder
        if not ripper_settings:
            ripper_settings = ripper_path / settings_name
            shutil.copy(this_settings, ripper_settings)

        else:
            old_ripper_settings = ripper_settings.with_suffix(".old.json")
            if not old_ripper_settings.exists():
                shutil.copy(ripper_settings, old_ripper_settings)

            with open(this_settings, "r") as settings_from:
                with open(ripper_settings, "w") as settings_to:
                    settings_to.write(settings_from.read())

        os.startfile(ripper, "open", f"--port {ripper_port} --headless")

        wait_time = 1
        while wait_time < 10:
            time.sleep(wait_time)
            try:
                requests.get(ripper_url)
                break
            except requests.ConnectionError:
                wait_time *= 2
                print(f"Ripper is not loaded. Trying reconnect in {wait_time} sec.")

    if ripper_version := get_ripper_version():
        print(f"Using Ripper version: {version_to_str(ripper_version)}")

    for game in sorted(games_to_rip):
        assets_path = Config[game.value.assets_folder]

        print(game.get_default_dlc().value.full_name, "Loading to", assets_path, end="... ", flush=True)

        timeit = Timeit()

        requests.post(ripper_url + "LoadFolder", data={"Path": Config[game.value.steam_folder]})

        assets_path.mkdir(parents=True, exist_ok=True)
        print("Exporting UnityProject", end="... ")
        requests.post(ripper_url + "Export/UnityProject", data={"Path": assets_path})

        # os.makedirs(f"{assets_path}_PrimaryContent", exist_ok=True)
        # print("Exporting PrimaryContent", end="... ")
        # requests.post(ripper_url + "Export/PrimaryContent", data={"Path": f"{assets_path}_PrimaryContent"})

        print(f" ({timeit:.2f} sec) Resetting")
        requests.post(ripper_url + "Reset")


if __name__ == "__main__":
    # rip_files({DLCType.MS, DLCType.OG, DLCType.FS})
    pass
