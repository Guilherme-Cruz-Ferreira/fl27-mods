#!/bin/bash
# Abre o Settings.exe oficial do jogo (teclado, controle, áudio, online...) com o mesmo Wine/prefixo do jogo.
source "$(dirname "$0")/lib.sh"
need_closed
if [ -n "$FL27_WINE_DIR" ] && [ -x "$FL27_WINE_DIR/wine64" ]; then WINE="$FL27_WINE_DIR/wine64"; export PATH="$FL27_WINE_DIR:$PATH"
elif command -v wine64 >/dev/null; then WINE=wine64; else WINE=wine; fi
export WINEPREFIX="$FL27_PREFIX" WINEDEBUG=-all
cd "$FL27_GAME_DIR" || exit 1
[ -f Settings.exe ] || { echo "Settings.exe não encontrado em $FL27_GAME_DIR"; exit 1; }
"$WINE" Settings.exe
