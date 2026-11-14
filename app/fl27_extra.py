# -*- coding: utf-8 -*-
"""Abas extras do FL27 Mods: 'Ajustes' (editar configs dos mods) e 'Instalar mod' (assistente).

Importado por fl27_mods.py. Funcoes de arquivo (sem janela) ficam no topo para poderem ser testadas.
Regras de seguranca: todo arquivo alterado ganha copia em BK_DIR antes; nada baixado e executado;
arquivos compactados sao extraidos numa pasta nova e isolada e so LIDOS/copiados.
"""
import datetime
import os
import re
import shutil
import subprocess
import tempfile
import threading
import zipfile

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib  # noqa: E402

import fl27paths  # noqa: E402
BK_DIR = fl27paths.resolve()['ini_backup']


# ================================================================ arquivos de configuracao (sem janela)
def _read(path):
    raw = open(path, 'rb').read().decode('utf-8', 'replace')
    return raw, ('\r\n' if '\r\n' in raw else '\n')


def backup_file(path):
    os.makedirs(BK_DIR, exist_ok=True)
    dst = os.path.join(BK_DIR, '%s.%s' % (os.path.basename(path), datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    shutil.copy2(path, dst)
    return dst


def read_values(path, keys=None):
    """-> {chave: valor(str)} das linhas ATIVAS 'chave = valor' (linhas com ; ou # no inicio sao ignoradas)."""
    out = {}
    try:
        txt, _ = _read(path)
    except OSError:
        return out
    for line in txt.split('\n'):
        m = re.match(r'^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*([^\r\n;#]*?)[ \t]*(?:[;#].*)?\r?$', line)
        if m and (keys is None or m.group(1) in keys):
            out.setdefault(m.group(1), m.group(2))
    return out


def write_values(path, values, spaced=False):
    """Atualiza (ou acrescenta) as chaves em `values` mantendo comentarios e quebra de linha. Faz backup antes."""
    txt, nl = _read(path)
    lines = txt.split(nl)
    pending = dict(values)
    for i, line in enumerate(lines):
        m = re.match(r'^([ \t]*)([A-Za-z_][A-Za-z0-9_]*)([ \t]*=[ \t]*)', line)
        if m and m.group(2) in pending:
            lines[i] = '%s%s%s%s' % (m.group(1), m.group(2), m.group(3), pending.pop(m.group(2)))
    if pending:
        while lines and lines[-1] == '':
            lines.pop()
        for k, v in pending.items():
            lines.append(('%s = %s' if spaced else '%s=%s') % (k, v))
        lines.append('')
    backup_file(path)
    open(path, 'wb').write(nl.join(lines).encode('utf-8'))


def fmt_num(x):
    s = ('%.4f' % x).rstrip('0').rstrip('.')
    return s or '0'


# Referee: presets (o arquivo guarda os presets comentados; aqui gravamos os valores ativos)
REFEREE_PRESETS = {
    'Original (Vanilla)': dict(T1_outside=40, T1_inside=40, T2=80, T3=110),
    'Moderado (recomendado pelo autor)': dict(T1_outside=38, T1_inside=35, T2=70, T3=110),
    'Rígido': dict(T1_outside=35, T1_inside=30, T2=65, T3=105),
    'Simulação (bem rígido)': dict(T1_outside=30, T1_inside=25, T2=60, T3=100),
}

# (chave, rotulo, min, max, passo, padrao, dica)
CAMERA_FIELDS = [
    ('Altura e distância', None),
    ('dist_open', 'Distância — câmera aberta (meio)', 10, 60, 0.5, 30, 'Maior = mais afastada.'),
    ('dist_close', 'Distância — câmera fechada (áreas)', 10, 60, 0.5, 25.5, ''),
    ('height_open', 'Altura — aberta', 10, 90, 1, 54, ''),
    ('height_close', 'Altura — fechada', 10, 90, 1, 34, ''),
    ('Onde a câmera fecha (distância do gol, em metros)', None),
    ('near_start', 'Ataque: começa a fechar a', 5, 50, 1, 23, ''),
    ('near_end', 'Ataque: totalmente fechada a', 0, 30, 1, 5, ''),
    ('def_start', 'Defesa: começa a fechar a', 5, 60, 1, 35, ''),
    ('def_end', 'Defesa: totalmente fechada a', 0, 40, 1, 17, ''),
    ('def_strength', 'Força do fechamento na defesa (0 a 1)', 0, 1, 0.05, 0.5, ''),
    ('Laterais', None),
    ('side_start', 'Lateral: começa em (m da linha)', 0, 40, 1, 12, ''),
    ('side_end', 'Lateral: termina em', 0, 60, 1, 28, ''),
    ('side_dist', 'Lateral: distância', 5, 60, 0.5, 15, ''),
    ('side_height', 'Lateral: altura', 5, 90, 1, 25, ''),
    ('side_top', 'Lado de cima: intensidade (0 a 1)', 0, 1, 0.05, 1, ''),
    ('side_bottom', 'Lado de baixo: intensidade (0 a 1)', 0, 1, 0.05, 0.3, ''),
    ('Suavidade das transições', None),
    ('follow', 'Acompanhar a jogada (0 a 1; menor = mais calmo)', 0.05, 1, 0.05, 0.6, ''),
    ('transition', 'Tempo para ganhar velocidade (s)', 0.1, 4, 0.1, 0.9, ''),
    ('min_time', 'Tempo mínimo de uma transição completa (s)', 0.5, 8, 0.1, 2.5, 'Maior = movimentos mais lentos.'),
    ('side_in_close', 'Lateral quando a câmera está fechada (0 a 1)', 0, 1, 0.05, 0.35, ''),
]

FOX_FIELDS = [
    ('T1', 'T1', 0.0, 1.0, 0.01, 0.25, ''),
    ('T2', 'T2', 0.0, 1.0, 0.01, 0.22, ''),
    ('T3', 'T3', 0.0, 1.0, 0.01, 0.25, ''),
    ('T4', 'T4', 0.0, 1.0, 0.01, 0.18, ''),
    ('T5', 'T5', 0.0, 1.0, 0.01, 0.22, ''),
    ('T6', 'T6', 0.0, 1.0, 0.01, 0.45, ''),
]


def scan_archive_dir(root):
    """Classifica o conteudo extraido -> dict(lua=[...], ini=[...], cpk=[...], outros=[...]) (caminhos relativos)."""
    res = dict(lua=[], ini=[], cpk=[], outros=[])
    for d, _, fs in os.walk(root):
        for f in fs:
            rel = os.path.relpath(os.path.join(d, f), root)
            low = f.lower()
            if low.endswith('.lua'):
                res['lua'].append(rel)
            elif low.endswith(('.ini', '.txt', '.cfg', '.json')):
                res['ini'].append(rel)
            elif low.endswith(('.cpk', '.bin', '.dds', '.mtar', '.exe', '.dll')) or '/livecpk/' in rel.lower() or rel.lower().startswith('livecpk'):
                res['cpk'].append(rel)
            else:
                res['outros'].append(rel)
    for k in res:
        res[k].sort()
    return res


def safe_extract(archive, dest):
    """Extrai zip/rar/7z para `dest` (pasta nova, vazia). Recusa caminhos que escapam da pasta. -> (ok, mensagem)"""
    low = archive.lower()
    if low.endswith('.zip'):
        with zipfile.ZipFile(archive) as z:
            base = os.path.realpath(dest)
            for n in z.namelist():
                if not os.path.realpath(os.path.join(dest, n)).startswith(base + os.sep) and n.strip('/'):
                    return False, 'Arquivo suspeito dentro do pacote (caminho fora da pasta): ' + n
            z.extractall(dest)
        return True, 'ZIP extraído.'
    if low.endswith('.rar'):
        cmd = ['unrar', 'x', '-y', '-idq', archive, dest + os.sep]
    elif low.endswith(('.7z', '.tar', '.gz', '.tgz', '.xz')):
        cmd = ['7z', 'x', '-y', '-o' + dest, archive]
    else:
        return False, 'Formato não suportado (use .lua, .zip, .rar ou .7z).'
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return False, (p.stdout + p.stderr).strip()[-800:]
    base = os.path.realpath(dest)
    for d, ds, fs in os.walk(dest):
        for n in ds + fs:
            if os.path.islink(os.path.join(d, n)):
                return False, 'O pacote contém link simbólico (recusado): ' + n
            if not os.path.realpath(os.path.join(d, n)).startswith(base):
                return False, 'Caminho suspeito: ' + n
    return True, 'Extraído.'


def dest_for(rel, mods_dir):
    parts = rel.replace('\\', '/').split('/')
    low = [p.lower() for p in parts]
    if 'modules' in low:
        parts = parts[low.index('modules') + 1:]
    else:
        sub = [i for i, p in enumerate(low[:-1]) if p in ('lib', 'common', 'switcher')]
        parts = parts[sub[0]:] if sub else parts[-1:]
    return os.path.join(mods_dir, *parts)


def install_files(src_root, rels, mods_dir):
    """Copia arquivos (caminhos relativos a src_root) para mods_dir, guardando copia dos que seriam sobrescritos.
    Se o pacote ja traz a pasta 'modules/', ela e removida do caminho. -> lista de (destino, sobrescreveu?)"""
    done = []
    for rel in rels:
        dst = dest_for(rel, mods_dir)
        over = os.path.exists(dst)
        if over:
            backup_file(dst)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(src_root, rel), dst)
        done.append((dst, over))
    return done


# ================================================================ interface
def _spin(lo, hi, step, val):
    sp = Gtk.SpinButton.new_with_range(lo, hi, step)
    sp.set_digits(2 if step < 0.1 else (1 if step < 1 else 0))
    sp.set_value(val)
    return sp


class FieldsEditor(Gtk.Box):
    """Lista de campos numericos ligados a um arquivo de config. Salvar = gravar so as chaves alteradas."""

    def __init__(self, app, path, fields, spaced, title, note=None, columns=1):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.app, self.path, self.spaced = app, path, spaced
        self.spins = {}
        self.defaults = {}
        self.extra_values = None
        t = Gtk.Label(xalign=0)
        t.set_markup('<b>%s</b>' % GLib.markup_escape_text(title))
        self.pack_start(t, False, False, 0)
        if note:
            n = Gtk.Label(xalign=0, wrap=True)
            n.set_markup('<small>%s</small>' % GLib.markup_escape_text(note))
            n.set_max_width_chars(95)
            self.pack_start(n, False, False, 0)
        self.grid = Gtk.Grid(column_spacing=12, row_spacing=3)
        self.pack_start(self.grid, False, False, 4)
        row = 0
        for f in fields:
            if f[1] is None:
                h = Gtk.Label(xalign=0)
                h.set_markup('\n<i>%s</i>' % GLib.markup_escape_text(f[0]))
                self.grid.attach(h, 0, row, 2, 1)
                row += 1
                continue
            key, label, lo, hi, step, default, hint = f
            lb = Gtk.Label(label=label, xalign=0)
            if hint:
                lb.set_tooltip_text(hint)
            sp = _spin(lo, hi, step, default)
            self.spins[key] = sp
            self.defaults[key] = default
            self.grid.attach(lb, 0, row, 1, 1)
            self.grid.attach(sp, 1, row, 1, 1)
            app.edit_widgets.append(sp)
            row += 1
        bb = Gtk.Box(spacing=8)
        self.btn_save = Gtk.Button(label='Salvar')
        self.btn_save.get_style_context().add_class('suggested-action')
        self.btn_save.connect('clicked', self.on_save)
        self.btn_def = Gtk.Button(label='Voltar aos valores padrão do mod')
        self.btn_def.connect('clicked', self.on_defaults)
        bb.pack_start(self.btn_save, False, False, 0)
        bb.pack_start(self.btn_def, False, False, 0)
        for b in (self.btn_save, self.btn_def):
            app.edit_widgets.append(b)
        self.pack_start(bb, False, False, 6)
        self.reload()

    def reload(self):
        vals = read_values(self.path, set(self.spins))
        for k, sp in self.spins.items():
            try:
                sp.set_value(float(vals[k]))
            except (KeyError, ValueError):
                sp.set_value(self.defaults[k])

    def on_defaults(self, *_):
        for k, sp in self.spins.items():
            sp.set_value(self.defaults[k])
        self.app.log('Valores padrão carregados na tela. Clique em Salvar para gravar.')

    def on_save(self, *_):
        if self.app.running or self.app.busy:
            self.app.info('Feche o jogo antes de salvar (o jogo pode regravar este arquivo).', Gtk.MessageType.WARNING)
            return
        if not os.path.exists(self.path):
            self.app.info('Arquivo não existe: %s' % self.path, Gtk.MessageType.WARNING)
            return
        cur = read_values(self.path, set(self.spins))
        new = {}
        for k, sp in self.spins.items():
            v = fmt_num(sp.get_value())
            try:
                same = abs(float(cur.get(k, 'x')) - float(v)) < 1e-9
            except ValueError:
                same = False
            if not same:
                new[k] = v
        if self.extra_values:
            ex = self.extra_values()
            cur_ex = read_values(self.path, set(ex))
            new.update({k: v for k, v in ex.items() if cur_ex.get(k) != v})
        if not new:
            self.app.log('Nada mudou em %s.' % os.path.basename(self.path))
            return
        write_values(self.path, new, self.spaced)
        self.app.log('Salvo em %s: %s (backup em %s)' % (os.path.basename(self.path),
                                                          ', '.join('%s=%s' % kv for kv in new.items()), BK_DIR))


class SettingsPage(Gtk.ScrolledWindow):
    def __init__(self, app, sider_dir, mods_dir):
        super().__init__()
        self.app = app
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_border_width(12)
        self.add(outer)
        intro = Gtk.Label(xalign=0, wrap=True)
        intro.set_max_width_chars(95)
        intro.set_markup('<small>Ajustes dos seus mods. Feche o jogo, altere, salve e abra o jogo de novo. '
                         'Cada salvamento guarda uma cópia do arquivo anterior em %s. '
                         'Dentro do jogo, o overlay (Espaço) continua funcionando para testar ao vivo.</small>' % GLib.markup_escape_text(BK_DIR))
        outer.pack_start(intro, False, False, 0)

        self.exp_cam = self._exp(outer, 'Câmera dinâmica', FieldsEditor(
            app, os.path.join(sider_dir, 'camera_dinamica.ini'), CAMERA_FIELDS, True, 'Arquivo camera_dinamica.ini',
            '"Aberta" = meio de campo; "fechada" = perto das áreas.'))
        self.fox = self._build_fox(os.path.join(sider_dir, 'fox_locomotion.txt'))
        self._exp(outer, 'Fox Locomotion (giro, parada e toque)', self.fox, expanded=False)
        self.ai = self._build_ai(os.path.join(mods_dir, 'AI_Tweaks.ini'))
        self._exp(outer, 'IA do adversário (AI_Tweaks)', self.ai, expanded=False)
        self.ref = self._build_ref(os.path.join(mods_dir, 'referee_strictness.ini'))
        self._exp(outer, 'Rigor do árbitro', self.ref, expanded=False)

    def _exp(self, outer, title, widget, expanded=True):
        e = Gtk.Expander(label='<b>%s</b>' % GLib.markup_escape_text(title))
        e.set_use_markup(True)
        e.set_expanded(False)
        e.add(widget)
        outer.pack_start(e, False, False, 0)
        return e

    # --- Fox
    def _build_fox(self, path):
        app = self.app
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        n = Gtk.Label(xalign=0, wrap=True)
        n.set_max_width_chars(95)
        n.set_markup('<small>Arquivo fox_locomotion.txt (também editável no jogo: F9 escolhe, setas ajustam, F6 preset, F5 salva).</small>')
        box.pack_start(n, False, False, 0)
        g = Gtk.Grid(column_spacing=12, row_spacing=4)
        box.pack_start(g, False, False, 0)
        self.fox_preset = Gtk.ComboBoxText()
        for i, t in enumerate(['1 — Fox completo (mais ágil)', '2', '3', '4 — Original do FL27 (desliga o efeito)']):
            self.fox_preset.append(str(i + 1), t)
        self.fox_preset.set_active(0)
        self.fox_micro = Gtk.CheckButton(label='Iniesta micro (toque curto e preciso)')
        self.fox_unclamp = Gtk.CheckButton(label='Passe 360° (remove o limite de direção do passe)')
        g.attach(Gtk.Label(label='Preset', xalign=0), 0, 0, 1, 1)
        g.attach(self.fox_preset, 1, 0, 1, 1)
        g.attach(self.fox_micro, 0, 1, 2, 1)
        g.attach(self.fox_unclamp, 0, 2, 2, 1)
        for w in (self.fox_preset, self.fox_micro, self.fox_unclamp):
            app.edit_widgets.append(w)
        self.fox_path = path
        self.fox_nums = FieldsEditor(app, path, FOX_FIELDS, False, 'Tempos (T1 a T6)',
                                     'Valores de transição do Fox. Mexa só se souber o que muda; o padrão do preset 1 já é o recomendado.')
        self.fox_nums.extra_values = lambda: {
            'preset': self.fox_preset.get_active_id() or '1',
            'iniesta_micro': '1' if self.fox_micro.get_active() else '0',
            'pass_unclamp': '1' if self.fox_unclamp.get_active() else '0'}
        box.pack_start(self.fox_nums, False, False, 0)
        self._fox_reload(None)
        return box

    def _fox_reload(self, *_):
        v = read_values(self.fox_path)
        self.fox_preset.set_active_id(v.get('preset', '1') if v.get('preset', '1') in '1234' else '1')
        self.fox_micro.set_active(v.get('iniesta_micro', '1') == '1')
        self.fox_unclamp.set_active(v.get('pass_unclamp', '0') == '1')

    # --- IA
    def _build_ai(self, path):
        app = self.app
        vals = read_values(path)
        fields = []
        for k in sorted(vals):
            try:
                float(vals[k])
            except ValueError:
                continue
            fields.append((k, k, 0, 100, 0.1, float(vals[k]), ''))
        self.ai_orig = {k: vals[k] for k in vals}
        ed = FieldsEditor(app, path, fields, False, 'Personalidade da IA (34 valores)',
                          'Os valores atuais do arquivo são os do nível Legend. Mudar aqui vale para QUALQUER dificuldade. '
                          'Não há descrição oficial de cada um (os nomes são do PES 2019); mude um de cada vez e teste.')
        ed.defaults = {k: float(v) for k, v in vals.items() if _isnum(v)}
        # padrao = valores que existiam quando o app abriu pela primeira vez (Legend do jogo); salvos ao lado
        snap = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_tweaks_legend.json')
        import json
        if os.path.exists(snap):
            try:
                ed.defaults.update({k: float(v) for k, v in json.load(open(snap)).items()})
            except (OSError, ValueError):
                pass
        elif ed.defaults:
            json.dump(ed.defaults, open(snap, 'w'))
        ed.btn_def.set_label('Voltar ao nível Legend original')
        return ed

    # --- Arbitro
    def _build_ref(self, path):
        app = self.app
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        n = Gtk.Label(xalign=0, wrap=True)
        n.set_max_width_chars(95)
        n.set_markup('<small>Muda a severidade das faltas já marcadas (o que é falta continua igual). '
                     'T1 = limiar de falta; T2 = amarelo; T3 = vermelho. Dentro/fora da área têm T1 separados.</small>')
        box.pack_start(n, False, False, 0)
        self.ref_path = path
        self.ref_combo = Gtk.ComboBoxText()
        for name in REFEREE_PRESETS:
            self.ref_combo.append(name, name)
        self.ref_combo.append('custom', 'Personalizado (valores atuais do arquivo)')
        self.ref_dogso = Gtk.CheckButton(label='Vermelho direto por DOGSO (anular chance clara) dentro da área')
        for w in (self.ref_combo, self.ref_dogso):
            app.edit_widgets.append(w)
        box.pack_start(self.ref_combo, False, False, 0)
        self.ref_lbl = Gtk.Label(xalign=0)
        self.ref_combo.connect('changed', self._ref_changed)
        box.pack_start(self.ref_lbl, False, False, 0)
        box.pack_start(self.ref_dogso, False, False, 0)
        b = Gtk.Button(label='Salvar')
        b.get_style_context().add_class('suggested-action')
        b.connect('clicked', self._ref_save)
        app.edit_widgets.append(b)
        box.pack_start(b, False, False, 6)
        self._ref_reload()
        return box

    def _ref_reload(self):
        v = read_values(self.ref_path)
        cur = {k: _num(v.get(k)) for k in ('T1_outside', 'T1_inside', 'T2', 'T3')}
        match = 'custom'
        for name, p in REFEREE_PRESETS.items():
            if all(cur.get(k) == p[k] for k in p):
                match = name
        self.ref_combo.set_active_id(match)
        self.ref_dogso.set_active(v.get('dogso_red', '0') == '1')
        self._ref_changed()

    def _ref_changed(self, *_):
        p = REFEREE_PRESETS.get(self.ref_combo.get_active_id())
        if p:
            self.ref_lbl.set_markup('<small>T1 fora=%(T1_outside)s  T1 dentro=%(T1_inside)s  T2=%(T2)s  T3=%(T3)s</small>' % p)
        else:
            v = read_values(self.ref_path)
            self.ref_lbl.set_markup('<small>Atual: ' + ', '.join('%s=%s' % (k, v.get(k, '?')) for k in ('T1_outside', 'T1_inside', 'T2', 'T3')) + '</small>')

    def _ref_save(self, *_):
        app = self.app
        if app.running or app.busy:
            app.info('Feche o jogo antes de salvar.', Gtk.MessageType.WARNING)
            return
        vals = {'dogso_red': '1' if self.ref_dogso.get_active() else '0'}
        p = REFEREE_PRESETS.get(self.ref_combo.get_active_id())
        if p:
            vals.update({k: str(v) for k, v in p.items()})
        write_values(self.ref_path, vals, True)
        app.log('Árbitro salvo: %s (backup em %s)' % (', '.join('%s=%s' % kv for kv in vals.items()), BK_DIR))
        self._ref_reload()

    def reload_all(self):
        for e in (self.exp_cam.get_child(), self.ai, self.fox_nums):
            e.reload()
        self._fox_reload()
        self._ref_reload()


def _isnum(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def _num(s):
    try:
        f = float(s)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return None


# ================================================================ assistente de instalacao
class InstallPage(Gtk.Box):
    def __init__(self, app, mods_dir, verificar_script):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.app, self.mods_dir, self.verificar = app, mods_dir, verificar_script
        self.set_border_width(12)
        self.tmp = None
        self.scan = None
        n = Gtk.Label(xalign=0, wrap=True)
        n.set_max_width_chars(95)
        n.set_markup('<small>Passo 1: escolha um módulo (.lua) ou um pacote (.zip, .rar, .7z) que você baixou. '
                     'O pacote é extraído numa pasta temporária isolada; nada é executado. '
                     'Passo 2: o app confere se os módulos Lua são compatíveis com o exe do FL27. '
                     'Passo 3: você escolhe o que copiar. Arquivos que seriam sobrescritos ganham backup.</small>')
        self.pack_start(n, False, False, 0)
        row = Gtk.Box(spacing=8)
        self.btn_pick = Gtk.Button(label='Escolher arquivo…')
        self.btn_pick.connect('clicked', self.on_pick)
        self.lbl_file = Gtk.Label(label='(nenhum)', xalign=0)
        row.pack_start(self.btn_pick, False, False, 0)
        row.pack_start(self.lbl_file, True, True, 0)
        self.pack_start(row, False, False, 0)
        self.store = Gtk.ListStore(bool, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        r = Gtk.CellRendererToggle()
        r.connect('toggled', lambda w, p: self.store.set_value(self.store.get_iter(p), 0, not self.store[p][0]))
        self.tree.append_column(Gtk.TreeViewColumn('Copiar', r, active=0))
        self.tree.append_column(Gtk.TreeViewColumn('Arquivo', Gtk.CellRendererText(), text=1))
        self.tree.append_column(Gtk.TreeViewColumn('Tipo', Gtk.CellRendererText(), text=2))
        sw = Gtk.ScrolledWindow()
        sw.set_min_content_height(150)
        sw.add(self.tree)
        self.pack_start(sw, True, True, 0)
        self.chk_on = Gtk.CheckButton(label='Ligar os módulos .lua copiados (adiciona ao sider.ini)')
        self.chk_on.set_active(True)
        self.pack_start(self.chk_on, False, False, 0)
        self.lbl_warn = Gtk.Label(xalign=0, wrap=True)
        self.lbl_warn.set_max_width_chars(95)
        self.pack_start(self.lbl_warn, False, False, 0)
        self.btn_inst = Gtk.Button(label='Instalar os arquivos marcados')
        self.btn_inst.get_style_context().add_class('suggested-action')
        self.btn_inst.set_sensitive(False)
        self.btn_inst.connect('clicked', self.on_install)
        self.pack_start(self.btn_inst, False, False, 0)
        app.edit_widgets.append(self.btn_pick)
        app.edit_widgets.append(self.btn_inst)

    def on_pick(self, *_):
        if self.app.running or self.app.busy:
            self.app.info('Feche o jogo antes.', Gtk.MessageType.WARNING)
            return
        dlg = Gtk.FileChooserDialog(title='Escolha o mod', parent=self.app, action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Abrir', Gtk.ResponseType.OK)
        dl = os.path.expanduser('~/Downloads')
        if os.path.isdir(dl):
            dlg.set_current_folder(dl)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            dlg.destroy()
            self.analyze(path)
        else:
            dlg.destroy()

    def analyze(self, path):
        self.cleanup()
        self.store.clear()
        self.btn_inst.set_sensitive(False)
        self.lbl_file.set_text(path)
        self.lbl_warn.set_text('')
        self.tmp = tempfile.mkdtemp(prefix='fl27_novo_mod_')
        if path.lower().endswith('.lua'):
            shutil.copy2(path, self.tmp)
            ok, msg = True, 'Módulo único.'
        else:
            try:
                ok, msg = safe_extract(path, self.tmp)
            except Exception as e:  # noqa: BLE001
                ok, msg = False, str(e)
        if not ok:
            self.lbl_warn.set_markup('<span foreground="#dc2626">%s</span>' % GLib.markup_escape_text(msg))
            return
        self.scan = scan_archive_dir(self.tmp)
        for rel in self.scan['lua']:
            ex = os.path.exists(dest_for(rel, self.mods_dir))
            self.store.append([True, rel, 'ATUALIZAÇÃO de módulo já instalado (o antigo vai para backup)' if ex else 'módulo Lua (novo)'])
        keep = 0
        for rel in self.scan['ini']:
            ex = os.path.exists(dest_for(rel, self.mods_dir))
            keep += ex
            self.store.append([not ex, rel, 'configuração JÁ EXISTE: mantida (marque só para sobrescrever)' if ex else 'configuração (nova)'])
        for rel in self.scan['cpk'] + self.scan['outros']:
            self.store.append([False, rel, 'NÃO instalável aqui (dados do jogo/exe/dll)'])
        luas = [os.path.join(self.tmp, r) for r in self.scan['lua']]
        txt = []
        if self.scan['cpk']:
            txt.append('Este pacote também traz arquivos de dados do jogo (cpk/bin/exe/dll...). Eles NÃO são copiados por este assistente: '
                       'veja a seção "Mods que mexem em coisas diferentes" do guia.')
        if keep:
            txt.append('É uma atualização: suas configurações existentes foram mantidas. Se o mod novo tiver opções novas, compare com o arquivo do pacote.')
        if not luas:
            txt.append('Nenhum módulo .lua encontrado.')
        self.lbl_warn.set_markup('<small><span foreground="#d97706">%s</span></small>' % GLib.markup_escape_text(' '.join(txt)))
        if luas:
            self.app.log('Conferindo compatibilidade de %d módulo(s) com o exe do FL27…' % len(luas))
            self.app.run_async(['python3', '-I', self.verificar] + luas, 'conferindo compatibilidade')
        self.btn_inst.set_sensitive(any(r[0] for r in self.store))

    def on_install(self, *_):
        app = self.app
        if app.running or app.busy or not self.tmp:
            return
        rels = [r[1] for r in self.store if r[0]]
        if not rels:
            return
        if not app.ask('Copiar %d arquivo(s) para a pasta de mods?' % len(rels),
                       'Arquivos já existentes terão cópia de segurança em %s.\n'
                       'Dica: veja no painel de baixo o resultado da conferência de compatibilidade antes de continuar.' % BK_DIR):
            return
        try:
            done = install_files(self.tmp, rels, self.mods_dir)
        except OSError as e:
            app.info('Falha ao copiar: %s' % e, Gtk.MessageType.ERROR)
            return
        for dst, over in done:
            app.log('copiado%s: %s' % (' (sobrescreveu, com backup)' if over else '', dst))
        luas = [os.path.relpath(d, self.mods_dir).replace('/', '\\') for d, _ in done if d.endswith('.lua')]
        if self.chk_on.get_active() and luas:
            for m in luas:
                app.run_sync_script(m)
        app.log('Pronto. Abra o jogo e confira no overlay/console. Se der problema: desligue o mod na aba Mods.')
        app.reload_after_install()
        self.cleanup()
        self.store.clear()
        self.btn_inst.set_sensitive(False)
        self.lbl_file.set_text('(nenhum)')

    def cleanup(self):
        if self.tmp and os.path.isdir(self.tmp) and os.path.basename(self.tmp).startswith('fl27_novo_mod_'):
            shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp = None
