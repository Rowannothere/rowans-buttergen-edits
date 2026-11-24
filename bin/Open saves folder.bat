@echo off
rem opens the folder where Buttergen.exe keeps your Clans (and makes it if it isn't there yet)
set "SAVES=%LocalAppData%\Buttergen\Buttergen\saves"
if not exist "%SAVES%" mkdir "%SAVES%"
start "" "%SAVES%"
