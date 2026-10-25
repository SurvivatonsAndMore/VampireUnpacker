set "venv_root=%1"
if [%venv_root%]==[] (
    set "venv_root=.venv"
)
if exist %venv_root% (
    if exist %venv_root%/Scripts call %venv_root%/Scripts/activate.bat
    if exist %venv_root%/bin call %venv_root%/bin/activate.bat
) else (
    echo Not found venv [%venv_root%]
)

pyinstaller --onedir --windowed --name VampireUnpacker ^
  --add-data "Source/Images/Components;Source/Images/Components" ^
  --add-data "Source/Images/Show;Source/Images/Show" ^
  --add-data "Source/Ripper/AssetRipper.Settings.json;Source/Ripper" ^
  unpacker.py