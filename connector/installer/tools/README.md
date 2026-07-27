# Place required Windows binaries here before building the installer.
# These files are NOT committed to git (see .gitignore).
#
# Required:
#   ffmpeg.exe      — Windows x64 build from https://www.gyan.dev/ffmpeg/builds/
#                     (essentials or full; only ffmpeg.exe is needed)
#   WinSW-x64.exe   — from https://github.com/winsw/winsw/releases
#                     (download WinSW-NET461.exe or WinSW-x64.exe and rename to WinSW-x64.exe)
#
# Expected layout:
#   connector/installer/tools/ffmpeg.exe
#   connector/installer/tools/WinSW-x64.exe
#
# Missing either file causes installer\build.ps1 to fail immediately.
