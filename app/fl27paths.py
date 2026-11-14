#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuração única do FL27 Mods (lida pelo app e pelos scripts).

Arquivo: ~/.config/fl27-mods/config.env  (linhas CHAVE="valor"; veja config.example.env)
Uso:  python3 fl27paths.py --detect      procura a instalação do jogo
      python3 fl27paths.py --setup       cria/atualiza o config (pergunta no terminal)
      python3 fl27paths.py --shell       imprime 'export ...' (usado pelos scripts .sh)
      python3 fl27paths.py --show        mostra os caminhos resolvidos
"""
import glob
import os
import re
import shlex
import subprocess
import sys

HOME = os.path.expanduser('~')
CONF = os.path.join(os.environ.get('XDG_CONFIG_HOME', os.path.join(HOME, '.config')), 'fl27-mods', 'config.env')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, 'scripts')
GAME_FOLDER = 'SP Football Life 2027'


def _expand(v):
    return os.path.expandvars(os.path.expanduser(v)) if v else v


def read_conf(path=CONF):
    out = {}
    try:
        for line in open(path, encoding='utf-8'):
            m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$', line)
            if m and not line.lstrip().startswith('#'):
                v = m.group(2)
                try:
                    parts = shlex.split(v)
                    v = parts[0] if parts else ''
                except ValueError:
                    pass
                out[m.group(1)] = _expand(v)
    except OSError:
        pass
    return out


def write_conf(values, path=CONF):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cur = read_conf(path)
    cur.update({k: v for k, v in values.items() if v is not None})
    with open(path, 'w', encoding='utf-8') as f:
        f.write('# FL27 Mods — gerado por fl27paths.py --setup. Edite à vontade (veja config.example.env).\n')
        for k, v in cur.items():
            f.write('%s=%s\n' % (k, shlex.quote(v)))


def prefix_of(game_dir):
    m = re.match(r'^(.*)/drive_c/', game_dir.replace('\\', '/') + '/')
    return m.group(1) if m else ''


def detect_saves(prefix):
    pats = [os.path.join(prefix, 'drive_c/users/*/Documents/SPGAME/Football Life/2027/save'),
            os.path.join(prefix, 'drive_c/users/*/Documents/SPGAME/*/2027/save')]
    for p in pats:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[0]
    return ''


def detect_wine_dir():
    for pat in ('~/.var/app/net.lutris.Lutris/data/lutris/runners/wine/*/bin',
                '~/.local/share/lutris/runners/wine/*/bin',
                '~/.local/share/Steam/compatibilitytools.d/*/files/bin'):
        hits = sorted(glob.glob(os.path.expanduser(pat)), reverse=True)
        for h in hits:
            if os.path.exists(os.path.join(h, 'wine64')) or os.path.exists(os.path.join(h, 'wine')):
                return h
    return ''


def detect_game():
    """Procura FL_2027.exe nos lugares comuns. -> lista de pastas do jogo."""
    roots = [HOME, '/mnt', '/media', '/run/media', '/opt']
    found = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        try:
            out = subprocess.run(['find', r, '-maxdepth', '9', '-name', 'FL_2027.exe', '-not', '-path', '*/backup*'],
                                 capture_output=True, text=True, timeout=90).stdout
        except (OSError, subprocess.TimeoutExpired):
            continue
        found += [os.path.dirname(x) for x in out.split('\n') if x.strip()]
    return sorted(set(found))


def resolve():
    """Caminhos finais (config + padrões + variáveis de ambiente de teste)."""
    c = read_conf()
    g = c.get('GAME_DIR', '')
    p = c.get('WINEPREFIX') or prefix_of(g)
    bk = c.get('BACKUP_ROOT') or os.path.join(HOME, 'FL27-backups')
    sd = os.environ.get('FL27_SIDER_DIR') or (os.path.join(g, 'SiderAddons') if g else '')
    r = dict(
        game_dir=g, wineprefix=p,
        wine_dir=c.get('WINE_BIN_DIR') or detect_wine_dir(),
        sider_dir=sd, ini=os.path.join(sd, 'sider.ini') if sd else '', mods_dir=os.path.join(sd, 'modules') if sd else '',
        livecpk_dir=os.path.join(sd, 'livecpk') if sd else '',
        backup_root=bk,
        ini_backup=os.environ.get('FL27_BACKUP_DIR') or c.get('INI_BACKUP_DIR') or os.path.join(bk, 'ini'),
        saves_dir=c.get('SAVES_DIR') or (detect_saves(p) if p else ''),
        saves_backup=c.get('SAVES_BACKUP_DIR') or os.path.join(bk, 'saves'),
        orig_ini=c.get('ORIG_INI') or os.path.join(bk, 'original', 'sider.ini.original'),
        orig_exe=c.get('ORIG_EXE', ''), orig_dt13=c.get('ORIG_DT13', ''),
        anim_script=c.get('ANIM_SCRIPT', ''),
        dlloverrides=c.get('WINEDLLOVERRIDES', 'steam_api64=n,b;ddraw=n,b;lsteamclient=d;d3d9,d3d10core,d3d11,dxgi=n,b'),
        diag_dir=c.get('DIAG_DIR') or os.path.join(bk, 'diagnostics'),
        scripts_dir=SCRIPTS, guide=c.get('GUIDE_PDF', ''),
    )
    return r


def configured():
    g = read_conf().get('GAME_DIR', '')
    return bool(g) and os.path.isfile(os.path.join(g, 'FL_2027.exe'))


def snapshot_original(r):
    """Guarda uma cópia do sider.ini atual como 'original' (usada p/ separar mods da base do SP). Só se ainda não existe."""
    if os.path.exists(r['orig_ini']) or not os.path.exists(r['ini']):
        return False
    os.makedirs(os.path.dirname(r['orig_ini']), exist_ok=True)
    import shutil
    shutil.copy2(r['ini'], r['orig_ini'])
    return True


def shell_exports():
    r = resolve()
    names = {'FL27_GAME_DIR': 'game_dir', 'FL27_PREFIX': 'wineprefix', 'FL27_WINE_DIR': 'wine_dir', 'FL27_SD': 'sider_dir',
             'FL27_INI': 'ini', 'FL27_MODS': 'mods_dir', 'FL27_LIVE': 'livecpk_dir', 'FL27_BK': 'ini_backup',
             'FL27_SAVES': 'saves_dir', 'FL27_SAVES_BK': 'saves_backup', 'FL27_ORIG_INI': 'orig_ini', 'FL27_ORIG_EXE': 'orig_exe',
             'FL27_ORIG_DT13': 'orig_dt13', 'FL27_ANIM': 'anim_script', 'FL27_DLL': 'dlloverrides', 'FL27_DIAG': 'diag_dir',
             'FL27_SCRIPTS': 'scripts_dir', 'FL27_BKROOT': 'backup_root'}
    return '\n'.join('export %s=%s' % (k, shlex.quote(r[v])) for k, v in names.items())


def _ask(q, default=''):
    a = input('%s%s: ' % (q, ' [%s]' % default if default else '')).strip()
    return a or default


def setup_cli():
    cands = detect_game()
    g = ''
    if cands:
        print('Instalações encontradas:')
        for i, c in enumerate(cands, 1):
            print('  %d) %s' % (i, c))
        a = _ask('Número (ou caminho completo)', '1')
        g = cands[int(a) - 1] if a.isdigit() and 1 <= int(a) <= len(cands) else a
    else:
        g = _ask('Pasta do jogo (a que contém FL_2027.exe)')
    if not os.path.isfile(os.path.join(g, 'FL_2027.exe')):
        sys.exit('FL_2027.exe não está em: %s' % g)
    vals = {'GAME_DIR': g}
    p = prefix_of(g)
    wd = _ask('Pasta bin do Wine/Proton (wine64, wineserver)', detect_wine_dir())
    if wd:
        vals['WINE_BIN_DIR'] = wd
    vals['WINEPREFIX'] = _ask('WINEPREFIX', p)
    vals['BACKUP_ROOT'] = _ask('Pasta para backups', os.path.join(HOME, 'FL27-backups'))
    write_conf(vals)
    print('Config salvo em', CONF)
    if snapshot_original(resolve()):
        print('Cópia do sider.ini atual guardada como "original" (para separar seus mods da base do SP).')


if __name__ == '__main__':
    a = sys.argv[1:]
    if '--shell' in a:
        print(shell_exports())
    elif '--detect' in a:
        print('\n'.join(detect_game()) or 'nenhuma instalação encontrada')
    elif '--setup' in a:
        setup_cli()
    else:
        for k, v in resolve().items():
            print('%-14s %s' % (k, v))
