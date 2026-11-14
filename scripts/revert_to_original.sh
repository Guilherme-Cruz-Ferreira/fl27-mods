#!/bin/bash
# Volta ao estado original: restaura o sider.ini original (e exe/dt13 se ORIG_EXE/ORIG_DT13 estiverem no config).
# Os arquivos dos mods continuam no disco; só deixam de ser usados. Backup do sider.ini atual antes.
source "$(dirname "$0")/lib.sh"
need_closed
[ -f "$FL27_ORIG_INI" ] || { echo "Não há sider.ini original guardado em $FL27_ORIG_INI (rode fl27paths.py --setup numa instalação limpa)."; exit 1; }
read -p "Isso desliga TODOS os mods. Continuar? [s/N] " r; [ "$r" = s ] || [ "$r" = S ] || { echo cancelado; exit 0; }
mkdir -p "$FL27_BK"; cp "$FL27_INI" "$FL27_BK/sider.ini.antes-voltar-original-$(date +%Y%m%d-%H%M%S)"
cp -p "$FL27_ORIG_INI" "$FL27_INI"
[ -f "$FL27_ORIG_EXE" ] && cp -p "$FL27_ORIG_EXE" "$FL27_GAME_DIR/FL_2027.exe"
[ -f "$FL27_ORIG_DT13" ] && cp -p "$FL27_ORIG_DT13" "$FL27_GAME_DIR/Data/dt13_all.cpk"
echo "Pronto: sider.ini original restaurado${FL27_ORIG_EXE:+, exe}${FL27_ORIG_DT13:+, dt13}."
