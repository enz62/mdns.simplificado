#!/usr/bin/env python3
"""Uso: python3 analisar.py monitor.csv no1.csv no2.csv ...
Calcula tempo de descoberta, deteccao de saida e trafego. Maquinas diferentes precisam de relogios
sincronizados (NTP); na mesma maquina/VMs no mesmo host funciona direto."""
import csv, sys

def ler(p):
    return [dict(t=float(r[0]), ev=r[1], nome=r[2], det=r[4]) for r in csv.reader(open(p)) if r]

def primeiro(rows, ev, nome=None):
    for r in rows:
        if r["ev"] == ev and (nome is None or r["nome"] == nome): return r["t"]

def metr(rows):
    ult = [r for r in rows if r["ev"] == "METRICAS"]
    if not ult: return {}
    d = dict(kv.split("=") for kv in ult[-1]["det"].split(";"))
    return {k: int(v) for k, v in d.items()}

mon = ler(sys.argv[1])
print(f"{'dispositivo':<16}{'descoberta(s)':>14}{'det.GOODBYE(s)':>16}{'det.TTL(s)':>12}")
for p in sys.argv[2:]:
    no = ler(p)
    nome = next(r["nome"] for r in no if r["ev"] == "INICIO")
    ini = primeiro(no, "INICIO", nome)
    desc = primeiro(mon, "DESCOBERTO", nome)
    gb_env, gb_det = primeiro(no, "GOODBYE_ENVIADO", nome), primeiro(mon, "SAIDA_GOODBYE", nome)
    mo, ex = primeiro(no, "MORTE_ABRUPTA", nome), primeiro(mon, "EXPIRADO", nome)
    f = lambda a, b: f"{b-a:.3f}" if a and b else "-"
    print(f"{nome:<16}{f(ini,desc):>14}{f(gb_env,gb_det):>16}{f(mo,ex):>12}")

m = metr(mon)
if m:
    dur = (mon[-1]["t"] - mon[0]["t"]) / 60 or 1
    print(f"\nMonitor: {m['rx_pkts']} pacotes / {m['rx_bytes']} bytes recebidos em {dur:.1f} min "
          f"-> {m['rx_pkts']/dur:.1f} pkts/min, {m['rx_bytes']/dur:.0f} B/min; tabela final: {m['tabela']} dispositivos")
