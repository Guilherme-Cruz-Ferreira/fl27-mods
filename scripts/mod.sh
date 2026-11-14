#!/bin/bash
# mod.sh - liga/desliga modulos Lua e pastas livecpk no sider.ini do FL27 (com backup automatico do sider.ini).
#   mod.sh list                      mostra o que esta ligado e o que esta instalado mas desligado
#   mod.sh on  <modulo.lua>          liga um modulo que ja esta na pasta modules (ex.: mod.sh on camera_dinamica.lua)
#   mod.sh off <modulo.lua>          desliga (remove a linha do sider.ini; o arquivo continua na pasta)
#   mod.sh root-on  <pasta>          liga uma pasta de livecpk (ex.: mod.sh root-on FOX_ANIM)
#   mod.sh root-off <pasta>          desliga
#   mod.sh backups                   lista os backups do sider.ini
#   mod.sh restaurar <arquivo>       volta um backup do sider.ini
source "$(dirname "$0")/lib.sh"
SD="$FL27_SD"
export INI="$FL27_INI" MODS="$FL27_MODS" LIVE="$FL27_LIVE" BK="$FL27_BK"
cmd="$1"; arg="$2"
fechado() { need_closed; }
backup() { mkdir -p "$BK"; cp "$INI" "$BK/sider.ini.$(date +%Y%m%d-%H%M%S-%N)"; }
case "$cmd" in
  list)
    python3 -I - <<'PY'
import os,re
ini=open(os.environ['INI'],'rb').read().decode('utf8','ignore').replace('\r','')
mods=[m for m in re.findall(r'^\s*lua\.module\s*=\s*"([^"]+)"',ini,re.M)]
roots=[m for m in re.findall(r'^\s*cpk\.root\s*=\s*"([^"]+)"',ini,re.M)]
print("== Pastas livecpk ligadas (ordem do sider.ini):")
for r in roots: print("   ",r)
print("== Modulos Lua ligados:")
for m in mods:
    ok=os.path.exists(os.path.join(os.environ['MODS'],m.replace('\\','/')))
    print("   %-40s %s"%(m,"" if ok else "  <-- ARQUIVO NAO ENCONTRADO"))
allf=[]
for d,_,fs in os.walk(os.environ['MODS']):
    for f in fs:
        if f.endswith('.lua'): allf.append(os.path.relpath(os.path.join(d,f),os.environ['MODS']).replace('/','\\'))
off=[f for f in sorted(allf) if f not in mods]
print("== Instalados mas DESLIGADOS (use: mod.sh on <nome>):")
for f in off: print("   ",f)
ld=sorted(d for d in os.listdir(os.environ['LIVE']) if os.path.isdir(os.path.join(os.environ['LIVE'],d)))
offr=[d for d in ld if ".\\livecpk\\"+d not in roots]
print("== Pastas livecpk instaladas mas DESLIGADAS (use: mod.sh root-on <pasta>):")
for d in offr: print("   ",d)
PY
    ;;
  on|off|root-on|root-off)
    [ -n "$arg" ] || { echo "Falta o nome. Veja: mod.sh list"; exit 1; }
    fechado; backup
    export OP="$cmd" NAME="$arg"
    python3 -I - <<'PY'
import os,sys,re
ini=os.environ['INI']; op=os.environ['OP']; name=os.environ['NAME']
raw=open(ini,'rb').read(); txt=raw.decode('utf8')
nl='\r\n' if '\r\n' in txt else '\n'
lines=txt.split(nl)
def idx(pred): return [i for i,l in enumerate(lines) if pred(l)]
if op in('on','off'):
    key='lua.module'; val=name
    isl=lambda l: re.match(r'^\s*lua\.module\s*=\s*"([^"]+)"',l)
    match=lambda l: (isl(l) and (isl(l).group(1).lower()==val.lower() or isl(l).group(1).lower().endswith('\\'+val.lower())))
    if op=='on':
        p=os.path.join(os.environ['MODS'],val.replace('\\','/'))
        if not os.path.exists(p): sys.exit("Arquivo nao existe em modules: "+val+"  (veja: mod.sh list)")
        if idx(match): sys.exit("Ja esta ligado: "+val)
        last=idx(isl)[-1]
        lines.insert(last+1,'\tlua.module = "%s"'%val); print("Ligado:",val)
    else:
        hit=idx(match)
        if not hit: sys.exit("Nao estava ligado: "+val)
        for i in reversed(hit): print("Desligado:",lines[i].strip()); del lines[i]
else:
    isr=lambda l: re.match(r'^\s*cpk\.root\s*=\s*"([^"]+)"',l)
    full='.\\livecpk\\'+name
    match=lambda l: isr(l) and isr(l).group(1).lower()==full.lower()
    if op=='root-on':
        if not os.path.isdir(os.path.join(os.environ['LIVE'],name)): sys.exit("Pasta nao existe em livecpk: "+name)
        if idx(match): sys.exit("Ja esta ligada: "+name)
        last=idx(isr)[-1]; lines.insert(last+1,'\tcpk.root = "%s"'%full); print("Ligada:",full)
    else:
        hit=idx(match)
        if not hit: sys.exit("Nao estava ligada: "+name)
        for i in reversed(hit): print("Desligada:",lines[i].strip()); del lines[i]
open(ini,'wb').write(nl.join(lines).encode('utf8'))
PY
    ;;
  backups) ls -lt "$BK" 2>/dev/null | head -20 ;;
  restaurar)
    [ -f "$BK/$arg" ] || { echo "Informe o nome do arquivo (veja: mod.sh backups)"; exit 1; }
    fechado; backup; cp "$BK/$arg" "$INI"; echo "sider.ini restaurado de $arg" ;;
  *) sed -n 2,11p "$0" ;;
esac
