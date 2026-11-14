#!/bin/bash
# Backup dos saves.   Uso: backup_saves.sh | listar | restaurar <pasta>
source "$(dirname "$0")/lib.sh"
SV="$FL27_SAVES"; BK="$FL27_SAVES_BK"
[ -d "$SV" ] || { echo "Pasta de saves não encontrada. Defina SAVES_DIR em ~/.config/fl27-mods/config.env"; exit 1; }
case "$1" in
  listar) ls -1 "$BK" 2>/dev/null ;;
  restaurar)
    [ -d "$BK/$2" ] || { echo "Informe uma pasta de: backup_saves.sh listar"; exit 1; }
    need_closed
    pre="$BK/$(date +%Y%m%d-%H%M%S)-antes-de-restaurar"; mkdir -p "$pre" && cp -p "$SV"/* "$pre"/ || exit 1
    cp -p "$BK/$2"/* "$SV"/ && echo "Saves restaurados de $2 (o estado anterior foi salvo em um novo backup)." ;;
  *) d="$BK/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$d" && cp -p "$SV"/* "$d"/ && echo "Backup em $d ($(ls "$d" | wc -l) arquivos, $(du -sh "$d" | cut -f1))" ;;
esac
