#!/bin/bash
# Testes sem jogo: monta uma instalação falsa numa pasta temporária e confere scripts e funções de arquivo.
set -e
D="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
G="$T/pfx/drive_c/Program Files (x86)/SP Football Life 2027"
mkdir -p "$G/SiderAddons/modules" "$G/SiderAddons/livecpk/FOX" "$T/pfx/drive_c/users/u/Documents/SPGAME/Football Life/2027/save"
touch "$G/FL_2027.exe"; echo save1 > "$T/pfx/drive_c/users/u/Documents/SPGAME/Football Life/2027/save/LG00"
printf 'cpk.root = ".\\livecpk\\root"\r\nlua.module = "lib\\CommonLib.lua"\r\n' > "$G/SiderAddons/sider.ini"
printf 'return {}\n' > "$G/SiderAddons/modules/camera.lua"
printf 'dist_open = 30\n# c\nfollow = 0.6\n' > "$G/SiderAddons/camera_dinamica.ini"
export XDG_CONFIG_HOME="$T/cfg"; mkdir -p "$T/cfg/fl27-mods"
printf 'GAME_DIR=%q\nBACKUP_ROOT=%q\n' "$G" "$T/bk" > "$T/cfg/fl27-mods/config.env"
ok() { echo "ok  - $1"; }; fail() { echo "FALHOU - $1"; exit 1; }
python3 -I "$D/app/fl27paths.py" --show | grep -q "saves_dir .*users/u" && ok "autodetecta saves" || fail saves
python3 -c "import sys; sys.path.insert(0,'$D/app'); import fl27paths as P; assert P.configured()" && ok "configured()" || fail configured
"$D/scripts/mod.sh" on camera.lua | grep -q Ligado && grep -q 'camera.lua' "$G/SiderAddons/sider.ini" && ok "mod.sh on" || fail on
grep -q $'\r' "$G/SiderAddons/sider.ini" && ok "mantém CRLF" || fail crlf
"$D/scripts/mod.sh" off camera.lua | grep -q Desligado && ! grep -q 'camera.lua' "$G/SiderAddons/sider.ini" && ok "mod.sh off" || fail off
"$D/scripts/mod.sh" root-on FOX | grep -q Ligada && ok "root-on" || fail rooton
[ "$(ls "$T/bk/ini" | wc -l)" -ge 3 ] && ok "backups do sider.ini" || fail inibk
"$D/scripts/backup_saves.sh" | grep -q "Backup em" && [ -n "$("$D/scripts/backup_saves.sh" listar)" ] && ok "backup de saves" || fail savesbk
echo save2 > "$T/pfx/drive_c/users/u/Documents/SPGAME/Football Life/2027/save/LG00"
B="$("$D/scripts/backup_saves.sh" listar | head -1)"; "$D/scripts/backup_saves.sh" restaurar "$B" && grep -q save1 "$T/pfx/drive_c/users/u/Documents/SPGAME/Football Life/2027/save/LG00" && "$D/scripts/backup_saves.sh" listar | grep -q antes-de-restaurar && ok "restaurar saves (com backup do estado anterior)" || fail restore
"$D/scripts/status.sh" | grep "Jogo: fechado" >/dev/null && ok "status.sh" || fail status
FL27_SIDER_DIR="$G/SiderAddons" python3 -I "$D/app/fl27_mods.py" --selftest >/dev/null && ok "selftest do app" || fail selftest
FL27_SIDER_DIR="$G/SiderAddons" python3 - "$D" "$T" <<'PY' && ok "ajustes/instalação (funções)" || fail extra
import sys, os, zipfile
sys.path.insert(0, sys.argv[1] + '/app'); import fl27_extra as X
cam = os.environ['FL27_SIDER_DIR'] + '/camera_dinamica.ini'
X.write_values(cam, {'dist_open': '33', 'novo': '1'}, True)
v = X.read_values(cam); assert v == {'dist_open': '33', 'follow': '0.6', 'novo': '1'}, v
assert '# c' in open(cam).read()
t = sys.argv[2] + '/pk'; os.makedirs(t + '/x')
open(t + '/x/m.lua', 'w').write('return {}')
z = zipfile.ZipFile(sys.argv[2] + '/a.zip', 'w'); z.write(t + '/x/m.lua', 'Mod/modules/m.lua'); z.close()
e = sys.argv[2] + '/ex'; os.makedirs(e); assert X.safe_extract(sys.argv[2] + '/a.zip', e)[0]
X.install_files(e, X.scan_archive_dir(e)['lua'], os.environ['FL27_SIDER_DIR'] + '/modules')
assert os.path.exists(os.environ['FL27_SIDER_DIR'] + '/modules/m.lua')
z = zipfile.ZipFile(sys.argv[2] + '/evil.zip', 'w'); z.writestr('../evil', 'x'); z.close()
e2 = sys.argv[2] + '/ex2'; os.makedirs(e2); assert not X.safe_extract(sys.argv[2] + '/evil.zip', e2)[0]
PY
python3 - "$D" "$T" <<'PY' && ok "settings.dat (tela/FPS/VSync)" || fail settingsdat
import sys, os, struct
sys.path.insert(0, sys.argv[1] + '/app'); import fl27_extra as X
f = sys.argv[2] + '/settings.dat'
d = bytearray(612); d[:4] = b'WECF'; struct.pack_into('<III', d, 8, 0x477, 1920, 1080)
open(f, 'wb').write(bytes(d)); os.environ['FL27_BACKUP_DIR'] = sys.argv[2] + '/bk'
assert X.read_display(f) == dict(fullscreen=True, w=1920, h=1080, fps_game60=True, fps_replay60=False, vsync='1', hdr=False)
X.write_display(f, False, 1280, 720, False, True, 'off', False)
r = X.read_display(f); assert r == dict(fullscreen=False, w=1280, h=720, fps_game60=False, fps_replay60=True, vsync='off', hdr=False), r
X.write_display(f, True, 1920, 1080, True, False, '1', False); assert open(f, 'rb').read() == bytes(d)
PY
echo "todos os testes passaram"
