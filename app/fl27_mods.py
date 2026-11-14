#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FL27 Mods - janela para ligar/desligar mods do SP Football Life 2027 (Linux/Wine).

Nao tem logica propria de arquivos: chama os scripts da pasta scripts/
(mod.sh, alternar_animacoes.sh, backup_saves.sh, voltar_ao_original.sh, fl27_status.sh).
Descricoes dos mods: mods.json (ao lado deste arquivo).

Uso:  python3 fl27_mods.py            abre a janela
      python3 fl27_mods.py --selftest testa a leitura do sider.ini (sem janela)
      python3 fl27_mods.py --shot DIR salva uma imagem de cada aba e sai
"""
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fl27_extra  # noqa: E402

import fl27paths as P  # noqa: E402

HOME = os.path.expanduser('~')
HERE = os.path.dirname(os.path.abspath(__file__))
R = P.resolve()
SC = lambda name: os.path.join(R['scripts_dir'], name)  # noqa: E731
GAME_DIR, SD, INI, MODS_DIR = R['game_dir'], R['sider_dir'], R['ini'], R['mods_dir']
ORIG_INI, WINEPREFIX, WINE_BIN, GUIDE_PDF = R['orig_ini'], R['wineprefix'], R['wine_dir'], R['guide']
ANIM_SCRIPT = R['anim_script']

ANIM_MODES = [
    ('fox', 'Fox completo',
     'Animações e tabelas de movimento do Fox + as constantes dele. Barra de força padrão do jogo.',
     'FOX_ANIM'),
    ('leve', 'Leve (animações originais do FL27)',
     'Animações ORIGINAIS do FL27 + só as constantes do Fox. Fica de fora o que o Fox gravou nas tabelas de movimento.',
     'FOX_CONST'),
    ('ps9', 'PS9 Ignite',
     'Pacote PS9: animações, exe patchado e constantes dele. Barra de força MENOS sensível.',
     'FL26_GAMEPLAY'),
]


# ---------------------------------------------------------------- leitura (sem janela)
def parse_ini(path):
    """-> (modulos ligados na ordem, pastas livecpk ligadas). Ignora linhas comentadas com ; ou #."""
    mods, roots = [], []
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return mods, roots
    for line in txt.replace('\r', '').split('\n'):
        m = re.match(r'^\s*lua\.module\s*=\s*"([^"]+)"', line)
        if m:
            mods.append(m.group(1))
            continue
        r = re.match(r'^\s*cpk\.root\s*=\s*"([^"]+)"', line)
        if r:
            roots.append(r.group(1))
    return mods, roots


def installed_modules():
    out = []
    for d, _, fs in os.walk(MODS_DIR):
        for f in fs:
            if f.endswith('.lua'):
                out.append(os.path.relpath(os.path.join(d, f), MODS_DIR).replace('/', '\\'))
    return sorted(out, key=str.lower)


def load_catalog():
    try:
        d = json.load(open(os.path.join(HERE, 'mods.json'), encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    return {k.lower(): v for k, v in d.items() if not k.startswith('_')}


def catalog_entry(cat, key):
    k = key.lower()
    return cat.get(k) or cat.get(k.replace('/', '\\').split('\\')[-1]) or {}


def game_pids():
    out = subprocess.run(['ps', '-eo', 'pid,args'], capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        if re.search(r'FL_2027\.exe|SiderAddons/sider\.exe|sider\.exe', line) and 'fl27_mods' not in line and 'ps -eo' not in line:
            try:
                pids.append(int(line.split()[0]))
            except (ValueError, IndexError):
                pass
    return pids


def current_anim(roots):
    for key, _t, _d, root in ANIM_MODES:
        if any(r.lower().endswith('\\' + root.lower()) for r in roots):
            return key
    return None


def classify(cat):
    """-> (seus_mods, base) como listas de (chave, ligado). Base = modulos do sider.ini original do SP."""
    on, _ = parse_ini(INI)
    base_names = {m.lower() for m in parse_ini(ORIG_INI)[0]}
    on_l = {m.lower() for m in on}
    allm = {}
    for m in on + installed_modules():
        allm.setdefault(m.lower(), m)
    mine, base = [], []
    for low, m in sorted(allm.items(), key=lambda kv: kv[0]):
        (base if low in base_names else mine).append((m, low in on_l))
    return mine, base


# ---------------------------------------------------------------- autoteste
def selftest():
    cat = load_catalog()
    mine, base = classify(cat)
    on, roots = parse_ini(INI)
    print('INI:', INI)
    print('modulos ligados: %d | pastas livecpk: %s' % (len(on), roots))
    print('animacao detectada:', current_anim(roots))
    print('seus mods (%d):' % len(mine))
    for m, st in mine:
        e = catalog_entry(cat, m)
        print('   [%s] %-34s %s' % ('x' if st else ' ', m, e.get('titulo', '(sem descricao no mods.json)')))
    print('base do SP: %d modulos (%d ligados)' % (len(base), sum(1 for _, s in base if s)))
    print('jogo aberto:', bool(game_pids()))
    bad = [m for m, _ in mine if not catalog_entry(cat, m)]
    print('sem descricao:', bad or 'nenhum')


# ---------------------------------------------------------------- janela
class App(Gtk.Window):
    def __init__(self):
        super().__init__(title='FL27 Mods')
        self.set_default_size(820, 700)
        self.set_border_width(8)
        self.cat = load_catalog()
        self.busy = False
        self.running = False
        self.edit_widgets = []
        self.refreshing = False

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)

        # --- barra do jogo
        bar = Gtk.Box(spacing=8)
        self.lbl_game = Gtk.Label(xalign=0)
        bar.pack_start(self.lbl_game, True, True, 0)
        self.btn_open = Gtk.Button(label='Abrir o jogo')
        self.btn_open.connect('clicked', lambda *_: self.launch(False))
        self.btn_dbg = Gtk.Button(label='Abrir (modo depuração)')
        self.btn_dbg.set_tooltip_text('Grava os erros do Wine em a pasta de diagnósticos. Use para investigar travamentos.')
        self.btn_dbg.connect('clicked', lambda *_: self.launch(True))
        self.btn_kill = Gtk.Button(label='Fechar o jogo')
        self.btn_kill.get_style_context().add_class('destructive-action')
        self.btn_kill.connect('clicked', self.on_kill)
        for b in (self.btn_open, self.btn_dbg, self.btn_kill):
            bar.pack_start(b, False, False, 0)
        root.pack_start(bar, False, False, 0)

        # --- abas
        self.nb = Gtk.Notebook()
        root.pack_start(self.nb, True, True, 0)
        self.page_mods = Gtk.ScrolledWindow()
        self.nb.append_page(self.page_mods, Gtk.Label(label='Mods'))
        if ANIM_SCRIPT and os.path.exists(ANIM_SCRIPT):
            self.nb.append_page(self.build_anim_page(), Gtk.Label(label='Animações'))
        self.nb.append_page(self.build_saves_page(), Gtk.Label(label='Saves e backups'))
        self.settings = fl27_extra.SettingsPage(self, SD, MODS_DIR)
        self.nb.append_page(self.settings, Gtk.Label(label='Ajustes'))
        self.installer = fl27_extra.InstallPage(self, MODS_DIR, SC('verify_mod.py'))
        self.nb.append_page(self.installer, Gtk.Label(label='Instalar mod'))
        self.nb.append_page(self.build_tools_page(), Gtk.Label(label='Ferramentas'))

        # --- log
        self.lbl_busy = Gtk.Label(xalign=0)
        root.pack_start(self.lbl_busy, False, False, 0)
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(130)
        self.tv = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        sw.add(self.tv)
        root.pack_start(sw, False, True, 0)

        self.rebuild_mods()
        self.refresh_anim()
        self.refresh_backups()
        self.poll()
        GLib.timeout_add_seconds(2, self.poll)
        self.log('FL27 Mods pronto. Alterações de mods exigem o jogo FECHADO (o Sider só lê o sider.ini ao abrir).')

    # ---------- utilidades
    def log(self, text):
        buf = self.tv.get_buffer()
        buf.insert(buf.get_end_iter(), text + '\n')
        mark = buf.create_mark(None, buf.get_end_iter(), False)
        self.tv.scroll_to_mark(mark, 0, False, 0, 0)

    def info(self, text, kind=Gtk.MessageType.INFO):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=kind,
                              buttons=Gtk.ButtonsType.OK, text=text)
        d.run()
        d.destroy()

    def ask(self, text, detail=None):
        d = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION,
                              buttons=Gtk.ButtonsType.YES_NO, text=text)
        if detail:
            d.format_secondary_text(detail)
        r = d.run()
        d.destroy()
        return r == Gtk.ResponseType.YES

    def set_busy(self, busy, what=''):
        self.busy = busy
        self.lbl_busy.set_markup('<i>Trabalhando: %s ...</i>' % GLib.markup_escape_text(what) if busy else '')
        self.apply_sensitivity()

    def apply_sensitivity(self):
        ok = (not self.running) and (not self.busy)
        for w in self.edit_widgets:
            w.set_sensitive(ok)
        self.btn_open.set_sensitive(not self.running and not self.busy)
        self.btn_dbg.set_sensitive(not self.running and not self.busy)
        self.btn_kill.set_sensitive(self.running and not self.busy)

    def poll(self):
        pids = game_pids()
        running = bool(pids)
        if running != self.running or not self.lbl_game.get_text():
            self.running = running
            if running:
                self.lbl_game.set_markup('<b>Jogo: ABERTO</b>  (feche o jogo para mudar mods)')
            else:
                self.lbl_game.set_markup('<b>Jogo: fechado</b>')
            self.apply_sensitivity()
        return True

    def run_async(self, argv, what, stdin=None, after=None):
        if self.busy:
            return
        self.set_busy(True, what)
        self.log('$ ' + ' '.join(argv))

        def work():
            try:
                p = subprocess.run(argv, input=stdin, capture_output=True, text=True, timeout=1800)
                out, rc = (p.stdout + p.stderr).strip(), p.returncode
            except Exception as e:  # noqa: BLE001
                out, rc = str(e), -1
            GLib.idle_add(self.finished, what, out, rc, after)
        threading.Thread(target=work, daemon=True).start()

    def finished(self, what, out, rc, after):
        if out:
            self.log(out)
        self.log('-> %s: %s' % (what, 'concluído' if rc == 0 else 'terminou com código %d' % rc))
        self.set_busy(False)
        self.rebuild_mods()
        self.refresh_anim()
        self.refresh_backups()
        if after:
            after()
        return False

    def run_sync_script(self, module):
        p = subprocess.run([SC('mod.sh'), 'on', module], capture_output=True, text=True)
        self.log((p.stdout + p.stderr).strip() or ('mod.sh on ' + module))

    def reload_after_install(self):
        self.cat = load_catalog()
        self.rebuild_mods()
        self.settings.reload_all()

    # ---------- jogo
    def launch(self, debug):
        script = [SC('launch.sh')] + (['--debug'] if debug else [])
        self.log('Abrindo o jogo%s ...' % (' (depuração)' if debug else ''))
        try:
            subprocess.Popen(script, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.info('Não consegui abrir: %s' % e, Gtk.MessageType.ERROR)

    def on_kill(self, *_):
        if not self.ask('Fechar o jogo à força?',
                        'Isso encerra o jogo na hora, sem salvar. Qualquer coisa não salva (partida em andamento) será perdida.'):
            return
        self.set_busy(True, 'fechando o jogo')

        def work():
            pids = game_pids()
            for p in pids:
                try:
                    os.kill(p, signal.SIGTERM)
                except OSError:
                    pass
            time.sleep(4)
            for p in pids:
                try:
                    os.kill(p, signal.SIGKILL)
                except OSError:
                    pass
            env = dict(os.environ, WINEPREFIX=WINEPREFIX)
            try:
                subprocess.run([os.path.join(WINE_BIN, 'wineserver'), '-k'], env=env, timeout=30,
                               capture_output=True)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(2)
            GLib.idle_add(self.killed, len(pids))
        threading.Thread(target=work, daemon=True).start()

    def killed(self, n):
        self.log('Jogo encerrado (%d processo(s)).' % n)
        self.set_busy(False)
        self.poll()
        return False

    # ---------- aba Mods
    def rebuild_mods(self):
        self.refreshing = True
        child = self.page_mods.get_child()
        if child:
            self.page_mods.remove(child)
        for w in list(self.edit_widgets):
            if getattr(w, '_is_mod_switch', False):
                self.edit_widgets.remove(w)
        mine, base = classify(self.cat)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_border_width(8)
        t = Gtk.Label(xalign=0)
        t.set_markup('<b>Seus mods</b>  <small>(ligue ou desligue; vale na próxima vez que abrir o jogo)</small>')
        box.pack_start(t, False, False, 0)
        for key, st in mine:
            box.pack_start(self.make_row(key, st), False, False, 0)
        exp = Gtk.Expander(label='Base do SP (não mexa, a menos que saiba o que está fazendo)')
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        inner.set_border_width(6)
        for key, st in base:
            inner.pack_start(self.make_row(key, st), False, False, 0)
        exp.add(inner)
        box.pack_start(exp, False, False, 8)
        self.page_mods.add(box)
        self.page_mods.show_all()
        self.refreshing = False
        self.apply_sensitivity()

    def make_row(self, key, enabled):
        e = catalog_entry(self.cat, key)
        row = Gtk.Box(spacing=12)
        sw = Gtk.Switch()
        sw.set_active(enabled)
        sw.set_valign(Gtk.Align.CENTER)
        sw._is_mod_switch = True
        sw.connect('state-set', self.on_toggle, key)
        self.edit_widgets.append(sw)
        row.pack_start(sw, False, False, 0)
        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title = Gtk.Label(xalign=0)
        title.set_markup('<b>%s</b>  <small>%s</small>' % (GLib.markup_escape_text(e.get('titulo', key)),
                                                         GLib.markup_escape_text(key)))
        v.pack_start(title, False, False, 0)
        desc = e.get('descricao') or 'Sem descrição no mods.json (edite o arquivo para cadastrar).'
        d = Gtk.Label(xalign=0, wrap=True)
        d.set_max_width_chars(90)
        d.set_markup('<small>%s</small>' % GLib.markup_escape_text(desc))
        d.set_line_wrap(True)
        v.pack_start(d, False, False, 0)
        if e.get('aviso'):
            a = Gtk.Label(xalign=0, wrap=True)
            a.set_markup('<small><span foreground="#d97706">Atenção: %s</span></small>' % GLib.markup_escape_text(e['aviso']))
            v.pack_start(a, False, False, 0)
        if e.get('requer'):
            r = Gtk.Label(xalign=0)
            r.set_markup('<small><i>Precisa de: %s</i></small>' % GLib.markup_escape_text(', '.join(e['requer'])))
            v.pack_start(r, False, False, 0)
        row.pack_start(v, True, True, 0)
        return row

    def on_toggle(self, sw, state, key):
        if self.refreshing:
            return False
        if self.running or self.busy:
            return True
        on_now = {m.lower() for m in parse_ini(INI)[0]}
        if state:  # ligando: confere dependencias
            falta = [r for r in catalog_entry(self.cat, key).get('requer', []) if r.lower() not in on_now]
            if falta:
                self.info('Ligue antes: %s' % ', '.join(falta), Gtk.MessageType.WARNING)
                GLib.idle_add(self.rebuild_mods)
                return True
        else:      # desligando: avisa se algum modulo ligado depende deste
            deps = [m for m in on_now if key.lower() in [x.lower() for x in catalog_entry(self.cat, m).get('requer', [])]]
            if deps:
                if not self.ask('Outros mods dependem de %s: %s.' % (key, ', '.join(deps)),
                                'Desligar mesmo assim?'):
                    GLib.idle_add(self.rebuild_mods)
                    return True
        self.run_async([SC('mod.sh'), 'on' if state else 'off', key],
                       '%s %s' % ('ligando' if state else 'desligando', key))
        return True

    # ---------- aba Animacoes
    def build_anim_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        self.lbl_anim = Gtk.Label(xalign=0)
        box.pack_start(self.lbl_anim, False, False, 0)
        self.anim_radios = {}
        first = None
        for key, titulo, desc, _root in ANIM_MODES:
            rb = Gtk.RadioButton.new_with_label_from_widget(first, titulo)
            first = first or rb
            self.anim_radios[key] = rb
            self.edit_widgets.append(rb)
            box.pack_start(rb, False, False, 0)
            d = Gtk.Label(xalign=0, wrap=True)
            d.set_markup('<small>%s</small>' % GLib.markup_escape_text(desc))
            d.set_margin_start(28)
            box.pack_start(d, False, False, 0)
        note = Gtk.Label(xalign=0, wrap=True)
        note.set_markup('<small><i>Trocar copia alguns arquivos grandes (cerca de 0,5 GB) e leva alguns segundos. '
                        'Só funciona com o jogo fechado.</i></small>')
        box.pack_start(note, False, False, 6)
        self.btn_anim = Gtk.Button(label='Aplicar a opção escolhida')
        self.btn_anim.connect('clicked', self.on_apply_anim)
        self.edit_widgets.append(self.btn_anim)
        box.pack_start(self.btn_anim, False, False, 0)
        self.lbl_roots = Gtk.Label(xalign=0, wrap=True)
        box.pack_start(self.lbl_roots, False, False, 12)
        return box

    def refresh_anim(self):
        if not hasattr(self, 'lbl_anim'):
            return
        _m, roots = parse_ini(INI)
        cur = current_anim(roots)
        nome = {k: t for k, t, _d, _r in ANIM_MODES}
        self.lbl_anim.set_markup('<b>Ativo agora:</b> %s' % GLib.markup_escape_text(nome.get(cur, 'não reconhecido')))
        if cur in self.anim_radios:
            self.anim_radios[cur].set_active(True)
        self.lbl_roots.set_markup('<small>Pastas livecpk ligadas: %s</small>' %
                                  GLib.markup_escape_text(', '.join(r.split('\\')[-1] for r in roots)))

    def on_apply_anim(self, *_):
        sel = next((k for k, rb in self.anim_radios.items() if rb.get_active()), None)
        if not sel:
            return
        self.run_async([ANIM_SCRIPT, sel], 'trocando animações para ' + sel)

    # ---------- aba Saves
    def build_saves_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        b = Gtk.Button(label='Fazer backup dos saves agora')
        b.connect('clicked', lambda *_: self.run_async([SC('backup_saves.sh')], 'backup dos saves'))
        box.pack_start(b, False, False, 0)
        self.edit_widgets.append(b)
        t = Gtk.Label(xalign=0)
        t.set_markup('<b>Backups existentes</b> <small>(mais novo no fim)</small>')
        box.pack_start(t, False, False, 6)
        self.store = Gtk.ListStore(str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.append_column(Gtk.TreeViewColumn('Pasta de backup', Gtk.CellRendererText(), text=0))
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(150)
        sw.add(self.tree)
        box.pack_start(sw, True, True, 0)
        r = Gtk.Button(label='Restaurar o backup selecionado')
        r.connect('clicked', self.on_restore)
        self.edit_widgets.append(r)
        box.pack_start(r, False, False, 0)
        sep = Gtk.Separator()
        box.pack_start(sep, False, False, 8)
        v = Gtk.Button(label='Voltar o jogo 100% ao original (desliga todos os mods)')
        v.connect('clicked', self.on_vanilla)
        self.edit_widgets.append(v)
        box.pack_start(v, False, False, 0)
        n = Gtk.Label(xalign=0, wrap=True)
        n.set_markup('<small>Os arquivos dos mods continuam no disco; só deixam de ser usados. '
                     'O sider.ini atual fica guardado antes.</small>')
        box.pack_start(n, False, False, 0)
        return box

    def refresh_backups(self):
        self.store.clear()
        try:
            out = subprocess.run([SC('backup_saves.sh'), 'listar'], capture_output=True,
                                 text=True, timeout=20).stdout
        except Exception:  # noqa: BLE001
            out = ''
        for line in out.split():
            self.store.append([line])

    def on_restore(self, *_):
        model, it = self.tree.get_selection().get_selected()
        if not it:
            self.info('Selecione um backup na lista.')
            return
        name = model[it][0]
        if self.ask('Restaurar os saves de %s?' % name,
                    'Os saves atuais serão guardados num novo backup antes de serem substituídos.'):
            self.run_async([SC('backup_saves.sh'), 'restaurar', name], 'restaurando saves de ' + name)

    def on_vanilla(self, *_):
        if self.ask('Voltar o jogo ao original?',
                    'Desliga TODOS os mods (câmera, Fox, PS9, IA...) e restaura o exe, o dt13 e o sider.ini originais. '
                    'A narração e os rostos continuam instalados.'):
            self.run_async([SC('revert_to_original.sh')], 'voltando ao original', stdin='s\n')

    # ---------- aba Ferramentas
    def build_tools_page(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_border_width(12)
        items = [
            ('Ver o status completo (no painel de baixo)', lambda *_: self.run_async([SC('status.sh')], 'status')),
            ('Abrir o guia em PDF', lambda *_: self.open_path(GUIDE_PDF)),
            ('Abrir a pasta de configuração', lambda *_: self.open_path(os.path.dirname(P.CONF))),
            ('Abrir a pasta de mods (modules)', lambda *_: self.open_path(MODS_DIR)),
            ('Abrir a pasta de diagnósticos', lambda *_: self.open_path(R['diag_dir'])),
            ('Editar as descrições dos mods (mods.json)', lambda *_: self.open_path(os.path.join(HERE, 'mods.json'))),
        ]
        for label, cb in items:
            b = Gtk.Button(label=label)
            b.set_halign(Gtk.Align.START)
            b.connect('clicked', cb)
            box.pack_start(b, False, False, 0)
        n = Gtk.Label(xalign=0, wrap=True)
        n.set_markup('<small>Jogo travou? NÃO feche: abra um terminal e rode scripts/diagnose_freeze.sh (na pasta do FL27 Mods) '
                     '(veja a seção 12-A do guia). Depois use "Fechar o jogo" aqui.</small>')
        box.pack_start(n, False, False, 12)
        return box

    def open_path(self, path):
        if not os.path.exists(path):
            self.info('Não existe: %s' % path, Gtk.MessageType.WARNING)
            return
        subprocess.Popen(['xdg-open', path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def first_run_setup():
    """Janela de primeira configuração: escolher a pasta do jogo. -> True se configurou."""
    while True:
        dlg = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
                                text='Primeira vez: onde está o jogo?')
        dlg.format_secondary_text('Escolha a pasta que contém FL_2027.exe (dentro do prefixo Wine, algo como '
                                  '.../drive_c/Program Files (x86)/SP Football Life 2027).\n'
                                  'Ou clique em "Procurar sozinho" (pode levar até um minuto).')
        dlg.add_button('Cancelar', Gtk.ResponseType.CANCEL)
        dlg.add_button('Procurar sozinho', 1)
        dlg.add_button('Escolher a pasta…', Gtk.ResponseType.OK)
        r = dlg.run()
        dlg.destroy()
        path = None
        if r == 1:
            found = P.detect_game()
            path = found[0] if found else None
            if not path:
                continue
        elif r == Gtk.ResponseType.OK:
            fc = Gtk.FileChooserDialog(title='Pasta do jogo', action=Gtk.FileChooserAction.SELECT_FOLDER)
            fc.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Escolher', Gtk.ResponseType.OK)
            path = fc.get_filename() if fc.run() == Gtk.ResponseType.OK else None
            fc.destroy()
        else:
            return False
        if path and os.path.isfile(os.path.join(path, 'FL_2027.exe')):
            P.write_conf({'GAME_DIR': path})
            P.snapshot_original(P.resolve())
            return True
        if path:
            m = Gtk.MessageDialog(message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK,
                                  text='FL_2027.exe não está nessa pasta.')
            m.run()
            m.destroy()


def shots(outdir):
    os.makedirs(outdir, exist_ok=True)
    app = App()
    app.show_all()
    state = {'i': 0}

    def grab():
        i = state['i']
        if i >= app.nb.get_n_pages():
            Gtk.main_quit()
            return False
        app.nb.set_current_page(i)
        GLib.timeout_add(500, save, i)
        state['i'] += 1
        return False

    def save(i):
        win = app.get_window()
        w, h = app.get_size()
        pb = Gdk.pixbuf_get_from_window(win, 0, 0, w, h)
        if pb:
            pb.savev(os.path.join(outdir, 'aba%d.png' % i), 'png', [], [])
        GLib.timeout_add(100, grab)
        return False
    GLib.timeout_add(1200, grab)
    Gtk.main()


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    elif '--shot' in sys.argv:
        shots(sys.argv[sys.argv.index('--shot') + 1])
    else:
        if not os.environ.get('FL27_SIDER_DIR') and not P.configured():
            if not first_run_setup():
                sys.exit(1)
            os.execv(sys.executable, [sys.executable] + sys.argv)
        w = App()
        w.connect('destroy', Gtk.main_quit)
        w.show_all()
        Gtk.main()
