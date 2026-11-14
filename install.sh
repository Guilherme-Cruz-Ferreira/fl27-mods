#!/bin/bash
# Instala o atalho "FL27 Mods" no menu de aplicativos e cria a configuração (se ainda não existir).
set -e
D="$(cd "$(dirname "$0")" && pwd)"
python3 -c "import gi; gi.require_version('Gtk','3.0'); from gi.repository import Gtk" 2>/dev/null || {
  echo "Falta o GTK3 para Python. Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-3.0   |  Fedora: sudo dnf install python3-gobject gtk3"; exit 1; }
chmod +x "$D"/scripts/*.sh "$D"/scripts/*.py "$D"/app/*.py
if python3 -I "$D/app/fl27paths.py" --show 2>/dev/null | grep -q '^game_dir *$'; then
  echo "Configuração inicial:"; python3 -I "$D/app/fl27paths.py" --setup
fi
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/fl27-mods.desktop <<EOF
[Desktop Entry]
Type=Application
Name=FL27 Mods
Comment=Liga/desliga e ajusta mods do SP Football Life 2027
Exec=python3 $D/app/fl27_mods.py
Icon=preferences-system
Categories=Utility;
Terminal=false
EOF
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Pronto. Abra 'FL27 Mods' no menu, ou:  python3 $D/app/fl27_mods.py"
