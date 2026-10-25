* [Game Files](https://github.com/orgs/SurvivatonsAndMore/repositories)

# Vampire Unpacker (v1.0.0) - Data manager and Image generator

Program can unpack images, get language strings and split them to different files and languages, unpack images based on
data files and make them with unified names, making (almost correct) animations of characters and enemies.

To start using unpacker, [download](https://github.com/SurvivatonsAndMore/VampireUnpacker/releases/latest) executable
(Windows only [[?](#running-from-source)]) and run it.

Configure paths with _**Change config**_. [[Info](#config)]

To get game files use [AssetRipper](https://github.com/AssetRipper/AssetRipper).
([v2.0.0](https://github.com/AssetRipper/AssetRipper/releases/latest)+)

* ! ***NOTE*** that ripping will **<u>REMOVE EVERYTHING</u>** in selected **<u>assets</u>** folders!
* Enter path to folder with AssetRipper.exe and Steam folder for Game in config.
* Press _**Rip data automatically**_ and select Games to rip.

### Config

| Entry           | Description                                                                                                                                         |
|-----------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| STEAM_'*game*'  | Path to folder with Steam game.<br/>Used by AssetRipper as _readonly_.                                                                              |
| ASSETS_'*game*' | Path to folder with ripped assets.<br/>Used by AssetRipper as _writable_. (removes **EVERYTHING** when ripping)<br/>Used by Unpacker as _readable_. |
| DATA_'*game*'   | Path to folder for processed and dumped data by Unpacker.<br/>Used by Unpacker as _writable_.                                                       |
| AS_RIPPER       | Path to folder with AssetRipper.<br/>Used by AssetRipper as _writable_ and _readable_.<br/>(Writes needed settings file for Ripper. Runs Ripper)    |

### Functions

| Button / Function / Feature             | Action                                                                                                                                                                                  |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Load Game Metadata                      | Select which game's ripped assets data will be loaded by Unpacker for additional features.<br>(Requires config _ASSETS_ for game)                                                       |
| Rip data automatically                  | Select which games' files to rip.<br>(Requires config _STEAM_, _ASSETS_ for games and _AS_RIPPER_)                                                                                      |
| Change config                           | Opens config GUI where you can enter paths and toggle settings.                                                                                                                         |
| Open last loaded folder                 | Opens folder that contains data from previous action.                                                                                                                                   |
| Select image atlas to unpack images     | Select png spritesheet (png atlas) from assets to split it into separate sprites.<br/>(Requires config _ASSETS_ and _DATA_)                                                             |
| Select image atlas to unpack animations | Select png spritesheet (png atlas) from assets to split it into separate animations.<br/>(Animations are defined by sorting names of sprites)<br/>(Requires config _ASSETS_ and _DATA_) |
| ... from spritesheets                   | For corresponding action opens _spritesheets_ folder of VS data.<br/>(Requires config _ASSETS_VS_ and _DATA_VS_)                                                                        |
| ... from any image                      | For corresponding action opens file selector.<br/>(Requires config _DATA_VS_)                                                                                                           |

#### Metadata Functions

* Requires _ASSETS_ and _DATA_ configs for respective game.

| Button / Function / Feature      | Action                                                                                                                                                                                                                                                    |
|----------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Create Game Version file         | Creates txt file with game version.                                                                                                                                                                                                                       |
| Get data                         | Dumps data files.                                                                                                                                                                                                                                         |
| Get merged data                  | Merges and dumps data files from different DLC into files by type.                                                                                                                                                                                        |
| Get language strings file        | Dumps file with translations language stings.<br/>(Original in .yaml/.asset or converted to json)                                                                                                                                                         |
| Get split language strings files | Splits languages (I2Languages) file into different json files by type (weapon, character, etc.)<br>with ability to select multiple languages.                                                                                                             |
| Get unified images               | Select DLC (or merged 'compound data') and select available data type to produce main image for every object.<br/>Tries to use english names from lang files.<br/>Has some additional options to produce images with frames, animations or other.         |
| Get stage tilemap                | Select prefab file with tilemap to generate 1:1 stage image.<br/>Big prefabs (> 5 MB) may have slow parse.<br/>Big one-block maps (e.g. from DLC) most likely will have file size higher 10 MB.<br/>Recommended to use **Enable multiprocessing** option. |
| Create inverse tilemap           | Select generated tilemap and enter tint value in base 10 to generate tinted and rotated version of map - inverse.<br>(See "tint" value in _Stage_ data files) .                                                                                           |
| Get unified audio                | Copies, makes and renames music files with ability to select change of names:<br/>"Code names", "Audio titles", "Relative object names".                                                                                                                  |

## Future plans

* Keep support for new content updates and DLC.
* Add VC image generator.

### Running from source

Use [Python 3.12](https://www.python.org/downloads/) with _**tkinter**_ and install dependencies
`pip install -r requirements.txt` (Can be done in global or venv. [run.bat](run.bat) has parameter of venv name when
using in terminal. Default name ".venv". If venv not found it starts in global.)

Run [unpacker.py](unpacker.py) with [run.bat](run.bat).

### Viewing code

* Vampire Survivors uses unity with il2cpp and can't be fully decompiled. However, there are tools to view some .dll
  files. Here are some of them:
    * [ILSpy](https://github.com/icsharpcode/ILSpy)
    * [Il2CppDumper](https://github.com/Perfare/Il2CppDumper)
    * [dnSpy](https://github.com/dnSpy/dnSpy)
