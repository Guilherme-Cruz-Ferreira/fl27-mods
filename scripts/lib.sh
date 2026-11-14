#!/bin/bash
# Carrega a configuração (~/.config/fl27-mods/config.env) e define funções comuns. Use: source "$(dirname "$0")/lib.sh"
_LIBDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
eval "$(python3 -I "$_LIBDIR/../app/fl27paths.py" --shell)"
[ -n "$FL27_SD" ] || { echo "FL27 Mods não configurado. Rode:  python3 $_LIBDIR/../app/fl27paths.py --setup"; exit 2; }
game_running() { ps -eo args | awk '/FL_2027|sider\.exe/ && !/awk/ && !/fl27_mods/ {f=1} END{exit !f}'; }
need_closed() { [ -n "$FL27_SIDER_DIR" ] && return 0; if game_running; then echo "Feche o jogo antes."; exit 1; fi; }
