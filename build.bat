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

pyinstaller --name VampireUnpacker ^
  --windowed ^
  --onedir ^
  --optimize 2 ^
  --icon "%CD%/Source/Images/Show/_Sprite-Atlas Gate.png" ^
  --add-data "%CD%/Source/Images/Components;Source/Images/Components" ^
  --add-data "%CD%/Source/Images/Show;Source/Images/Show" ^
  --add-data "%CD%/Source/Ripper/AssetRipper.Settings.json;Source/Ripper" ^
  --distpath "./build/dist" ^
  --workpath "./build/build" ^
  --specpath "./build" ^
  unpacker.py

pause
