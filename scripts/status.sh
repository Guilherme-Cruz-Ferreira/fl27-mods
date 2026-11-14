#!/bin/bash
# Painel: estado do jogo, mods ligados e erros recentes do Sider.
source "$(dirname "$0")/lib.sh"
echo "================ FL27 - STATUS ================"
game_running && echo "Jogo: ABERTO" || echo "Jogo: fechado"
[ -n "$FL27_ANIM" ] && [ -x "$FL27_ANIM" ] && echo "Animações/física : $("$FL27_ANIM" status)"
echo
"$(dirname "$0")/mod.sh" list
echo
echo "== Últimos avisos/erros do Sider (sider.log):"
grep -i "error\|problem\|failed\|nao encontr\|NOT active" "$FL27_SD/sider.log" 2>/dev/null | grep -v "preview.dds\|texture" | tail -8 | cut -c1-160
echo "(se estiver vazio, não há erros relevantes)"
echo
df -h "$FL27_GAME_DIR" | tail -1 | awk '{print "Espaço no disco do jogo: "$4" livres de "$2}'
