#!/usr/bin/env python3
"""verificar_mod.py - confere se um modulo Lua do Sider (feito para PES 2021 / FL26) e compativel com o exe do FL27.

Uso:  python3 verificar_mod.py <modulo.lua> [mais.lua ...] [--exe caminho_do_exe]

O que faz (somente leitura, nao altera nada):
  1) Procura no modulo os padroes de bytes que ele busca no exe (memory.search_process / variaveis 'pat...')
     e conta quantas vezes cada um aparece no exe do FL27. 1 ocorrencia = OK.
  2) Lista enderecos fixos (0x14xxxxxxx) citados no modulo e mostra os bytes que existem neles no FL27 e no FL26 (se houver).
Interpretacao: tudo OK  -> provavelmente compativel.  Muitos 'NAO ENCONTRADO' -> o exe e diferente, o mod pode nao funcionar.
Padroes que dizem 'patched'/'already' (ja remendado) nao existem num exe limpo: isso e normal.
"""
import re, sys, mmap, struct, os
_c = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app')
sys.path.insert(0, _c)
try:
    import fl27paths
    _r = fl27paths.resolve()
    EXE27 = _r['orig_exe'] if _r['orig_exe'] and os.path.exists(_r['orig_exe']) else os.path.join(_r['game_dir'], 'FL_2027.exe')
except Exception:
    EXE27 = ''
EXE26 = os.environ.get('FL26_EXE', '')   # opcional: exe do FL26 para comparar enderecos
args = sys.argv[1:]
if '--exe' in args:
    i = args.index('--exe'); EXE27 = args[i+1]; del args[i:i+2]
if not args or not os.path.exists(EXE27):
    print(__doc__); sys.exit(1)

def sections(path):
    f = open(path, 'rb'); d = f.read(0x1000)
    pe = struct.unpack_from('<I', d, 0x3c)[0]; ns = struct.unpack_from('<H', d, pe+6)[0]; osz = struct.unpack_from('<H', d, pe+20)[0]; o = pe+24+osz
    return [struct.unpack_from('<IIII', d, o+8+40*i) for i in range(ns)]
def read_va(path, secs, va, n):
    rva = va - 0x140000000
    for vs, sva, rs, rp in secs:
        if sva <= rva < sva+max(vs, rs):
            with open(path, 'rb') as f: f.seek(rp+rva-sva); return f.read(n)
    return None

lit = r'"(?:\\x[0-9a-fA-F]{2}|[^"\\])*"'
part = rf'(?:{lit}|string\.char\([^)]*\))'
def ev(expr):
    out = b''
    for p in re.findall(rf'{lit}|string\.char\([^)]*\)', expr):
        if p.startswith('string.char'): return None
        body = p[1:-1]; i = 0
        while i < len(body):
            if body.startswith('\\x', i): out += bytes([int(body[i+2:i+4], 16)]); i += 4
            else: out += body[i].encode(); i += 1
    return out

_f27 = open(EXE27, 'rb')
mm = mmap.mmap(_f27.fileno(), 0, access=mmap.ACCESS_READ)
secs27 = sections(EXE27); secs26 = sections(EXE26) if os.path.exists(EXE26) else None
for path in args:
    s = open(path, encoding='utf8', errors='ignore').read()
    print('='*72); print('MODULO:', path); print('EXE   :', EXE27)
    pats = []
    for m in re.finditer(rf'local\s+([\w]*pat[\w]*)\s*=\s*(\s*{part}(?:\s*\.\.\s*{part})*)', s, re.S):
        pats.append((s.count('\n', 0, m.start())+1, m.group(1), ev(m.group(2))))
    for m in re.finditer(rf'search_process\(\s*({lit})\s*[,)]', s):
        pats.append((s.count('\n', 0, m.start())+1, 'search_process', ev(m.group(1))))
    seen = set(); ok = bad = multi = 0
    print('\n-- Padroes de bytes buscados no exe:')
    for line, name, b in pats:
        if b is None or len(b) < 5 or (line, b) in seen: continue
        seen.add((line, b))
        n = 0; pos = 0
        while n < 4:
            i = mm.find(b, pos)
            if i < 0: break
            n += 1; pos = i+1
        flag = 'OK' if n == 1 else (f'varias({n})' if n > 1 else 'NAO ENCONTRADO')
        nm = name.lower()
        if 'patched' in nm or 'already' in nm: flag += '  (assinatura de "ja remendado": normal nao existir)'
        elif n == 0 and ('patch' in nm or 'jmp' in nm or 'stub' in nm or 'cave' in nm): flag += '  (provavelmente bytes que o mod ESCREVE, nao busca)'
        ok += n == 1; multi += n > 1; bad += n == 0
        print(f'   linha {line:5d} {name:22s} {b.hex(" ")[:30]:32s} {flag}')
    print(f'   => {ok} OK | {multi} ambiguos | {bad} nao encontrados')
    addrs = sorted(set(int(x, 16) for x in re.findall(r'0x(14[0-9A-Fa-f]{7})\b', s)))
    print(f'\n-- Enderecos fixos 0x14xxxxxxx citados: {len(addrs)}')
    for a in addrs[:40]:
        b27 = read_va(EXE27, secs27, a, 8); b26 = read_va(EXE26, secs26, a, 8) if secs26 else None
        eq = '' if b26 is None else ('  (igual ao FL26)' if b26 == b27 else '  (DIFERENTE do FL26)')
        print(f'   0x{a:09X}  FL27: {b27.hex(" ") if b27 else "fora do exe"}{eq}')
    if len(addrs) > 40: print(f'   ... e mais {len(addrs)-40}')
