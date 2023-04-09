@echo off
set releaseDir=%cd%\ReleaseTemplate

echo Creating release directory %releaseDir% ...
if not exist %releaseDir% mkdir %releaseDir%

echo Copying gk.exe, extractor.exe, and goalc.exe ...
copy "..\..\out\build\Release\bin\gk.exe" "%releaseDir%\"
copy "..\..\out\build\Release\bin\extractor.exe" "%releaseDir%\"
copy "..\..\out\build\Release\bin\goalc.exe" "%releaseDir%\"

echo Copying data folder ...
mkdir "%releaseDir%\data\game"
xcopy /E /I "..\..\goal_src" "%releaseDir%\data\goal_src\"
xcopy /E /I "..\..\custom_levels" "%releaseDir%\data\custom_levels\"
xcopy /E /I "..\..\decompiler\config" "%releaseDir%\data\decompiler\config\"
xcopy /E /I "..\..\game\assets" "%releaseDir%\data\game\assets\"
xcopy /E /I "..\..\game\graphics" "%releaseDir%\data\\game\graphics\"

echo Done!
