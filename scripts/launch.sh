#!/bin/bash
# Abre o Sider e o jogo.   launch.sh            normal
#                          launch.sh --debug    grava erros do Wine em <backups>/diagnostics/wine-DATA.log
source "$(dirname "$0")/lib.sh"
[ -d "$FL27_GAME_DIR" ] || { echo "GAME_DIR inválido no config."; exit 1; }
if [ -n "$FL27_WINE_DIR" ] && [ -x "$FL27_WINE_DIR/wine64" ]; then WINE="$FL27_WINE_DIR/wine64"; export PATH="$FL27_WINE_DIR:$PATH"
elif command -v wine64 >/dev/null; then WINE=wine64; else WINE=wine; fi
export WINE WINEPREFIX="$FL27_PREFIX" WINEDLLOVERRIDES="$FL27_DLL" WINEESYNC=1 WINEFSYNC=1
cd "$FL27_GAME_DIR" || exit 1
if [ "$1" = "--debug" ]; then
  export WINEDEBUG=err+all; mkdir -p "$FL27_DIAG"; LOG="$FL27_DIAG/wine-$(date +%Y%m%d-%H%M%S).log"; echo "Log do Wine: $LOG"
  "$WINE" SiderAddons/sider.exe >> "$LOG" 2>&1 & SP=$!; sleep 4; "$WINE" FL_2027.exe >> "$LOG" 2>&1
else
  export WINEDEBUG=-all
  "$WINE" SiderAddons/sider.exe & SP=$!; sleep 4; "$WINE" FL_2027.exe
fi
kill $SP 2>/dev/null
