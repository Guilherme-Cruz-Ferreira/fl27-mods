#!/bin/bash
# Rode isto com o jogo TRAVADO (sem fecha-lo). Coleta evidencias numa pasta para analise. Nao altera nada.
source "$(dirname "$0")/lib.sh"
SD="$FL27_SD"
D="$FL27_DIAG/travou-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$D"
PID=$(ps -eo pid,args | awk '/FL_2027.exe/ && !/awk/ {print $1; exit}')
if [ -z "$PID" ]; then echo "O jogo nao esta rodando (nada a coletar)."; exit 1; fi
{
echo "== processos relacionados (STAT: D=espera de disco, S=dormindo, R=rodando)"; ps -eo pid,stat,pcpu,etime,wchan:24,args | grep -i "FL_2027\|winedbg\|crashdlg\|wineserver\|sider.exe" | grep -v grep | cut -c1-150
echo; echo "== threads do jogo (CPU por thread, 3 amostras)"; for i in 1 2 3; do top -H -b -n1 -p $PID 2>/dev/null | sed -n '7,16p'; echo ---; sleep 2; done
} > "$D/processos.txt" 2>&1
if ps -eo comm | grep -qE "^winedbg|crashdlg"; then echo "ATENCAO: ha um depurador/dialogo de crash do Wine aberto => foi um CRASH." | tee -a "$D/processos.txt"; else echo "Sem depurador/dialogo de crash => nao foi crash (travamento/loop)." | tee -a "$D/processos.txt"; fi
# thread principal: CPU e chamadas de sistema por ~2 s (loop de espera ativa = muito sched_yield/futex)
python3 -I - "$PID" >> "$D/processos.txt" <<'PY'
import sys,time
pid=sys.argv[1]
def cpu():
    a=open(f'/proc/{pid}/task/{pid}/stat').read().split(); return int(a[13])+int(a[14])
c0=cpu(); t0=time.time(); time.sleep(1.5)
print("\n== CPU da thread principal: %.0f%%  (perto de 100%% = loop/espera ativa)"%((cpu()-c0)/100.0/(time.time()-t0)*100))
PY
if command -v strace >/dev/null; then timeout 4 strace -c -p $PID -o "$D/strace-resumo.txt" >/dev/null 2>&1 & sleep 2.5; kill -INT %1 2>/dev/null; wait 2>/dev/null
  echo "== chamadas de sistema da thread principal (2 s):" >> "$D/processos.txt"; head -8 "$D/strace-resumo.txt" >> "$D/processos.txt" 2>/dev/null; fi
echo "Coletando backtrace com o gdb (pode levar ~30 s)..."
timeout 90 gdb -batch -p $PID -ex "set pagination off" -ex "info threads" -ex "thread apply all bt 14" > "$D/gdb-backtrace.txt" 2>&1
tail -120 "$SD/sider.log" > "$D/sider.log.fim.txt"
cp "$FL27_DIAG"/wine-*.log "$D/" 2>/dev/null; ls -t "$FL27_DIAG"/wine-*.log 2>/dev/null | head -1 | xargs -r -I{} tail -200 {} > "$D/wine-debug.fim.txt"
"$(dirname "$0")/status.sh" > "$D/status.txt" 2>&1
cat > "$D/LEIA-ME.txt" <<'T'
Como ler:
- processos.txt     : estado do processo. Se uma thread estiver com ~100% de CPU, o jogo esta em LOOP; se tudo em 0%, esta ESPERANDO (deadlock).
- gdb-backtrace.txt : onde cada thread esta parada. Enderecos 0x14xxxxxxx = codigo do jogo; 0x033f0000..0x03490000 = ganchos do futsal (efutsal);
                      nomes de dll/modulos (sider, wined3d, dxvk...) mostram quem esta envolvido.
- wine-debug.fim.txt: ultimas mensagens de erro do Wine (procure "Unhandled exception" / "c0000005").
Mande este conteudo para alguem analisar (ou cole na IA com o guia).
T
echo "Evidencias salvas em: $D"
echo "Agora pode fechar o jogo (ou: kill $PID)."
