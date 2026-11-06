#!/usr/bin/env python3
"""mDNS simplificado: descoberta de dispositivos via multicast UDP + JSON.

Mensagens: ANNOUNCE (anuncio), QUERY (consulta), GOODBYE (despedida).
Exemplos:
  python3 mdns_simples.py --nome impressora --servico printer --porta-servico 631 --log no1.csv
  python3 mdns_simples.py --monitor --log monitor.csv          (so escuta)
  python3 mdns_simples.py --nome x --morrer-apos 40            (saida abrupta)
  python3 mdns_simples.py --nome y --sair-apos 40              (saida com GOODBYE)
"""
import argparse, csv, json, random, socket, struct, threading, time, uuid

GRUPO = "239.255.42.99"   # multicast administrativo (mDNS real usa 224.0.0.251)
PORTA = 5400              # mDNS real usa 5353


class No:
    def __init__(self, a):
        self.a = a
        self.id = uuid.uuid4().hex[:8]
        self.nome, self.servico = a.nome, a.servico
        self.ttl = a.ttl
        self.monitor = a.monitor
        self.tabela = {}                    # nome -> dict(ip, servico, porta, id, expira)
        self.lock = threading.Lock()
        self.rodando = True
        self.m = {"tx_pkts": 0, "tx_bytes": 0, "rx_pkts": 0, "rx_bytes": 0}
        self.f = open(a.log, "a", newline="") if a.log else None
        self.w = csv.writer(self.f) if self.f else None
        self.sock = self._socket(a.iface)

    # ---------- infraestrutura ----------
    def _socket(self, iface):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):          # varias instancias na mesma maquina (Linux/Mac)
            try: s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError: pass
        s.bind(("", PORTA))
        ip_if = iface or "0.0.0.0"
        mreq = struct.pack("4s4s", socket.inet_aton(GRUPO), socket.inet_aton(ip_if))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)   # entra no grupo
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)       # nao sai da rede local
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)      # recebe o que a propria maquina envia
        if iface:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface))
        s.settimeout(0.5)
        return s

    def log(self, ev, nome="", ip="", det=""):
        if self.w:
            with self.lock:
                self.w.writerow([f"{time.time():.6f}", ev, nome, ip, det])
                self.f.flush()

    def enviar(self, msg):
        msg["id"] = self.id
        data = json.dumps(msg).encode()
        self.sock.sendto(data, (GRUPO, PORTA))
        with self.lock:
            self.m["tx_pkts"] += 1
            self.m["tx_bytes"] += len(data)

    # ---------- protocolo ----------
    def anunciar(self):
        if self.monitor: return
        self.enviar({"type": "ANNOUNCE", "name": self.nome, "service": self.servico,
                     "port": self.a.porta_servico, "ttl": self.ttl})
        self.log("ANUNCIO_ENVIADO", self.nome)

    def consultar(self):
        self.enviar({"type": "QUERY", "service": "*"})
        self.log("QUERY_ENVIADA")

    def despedir(self):
        if self.monitor: return
        self.enviar({"type": "GOODBYE", "name": self.nome})
        self.log("GOODBYE_ENVIADO", self.nome)

    def tratar(self, msg, ip):
        t = msg.get("type")
        if t == "ANNOUNCE":
            nome = msg["name"]
            with self.lock:
                ent = self.tabela.get(nome)
                if ent and ent["id"] != msg["id"]:          # conflito de nome: vale quem chegou primeiro
                    conflito = True
                else:
                    conflito = False
                    novo = ent is None
                    self.tabela[nome] = {"ip": ip, "servico": msg["service"], "porta": msg["port"],
                                         "id": msg["id"], "expira": time.time() + msg["ttl"]}
            if conflito:
                self.log("CONFLITO_NOME", nome, ip)
            elif novo:
                self.log("DESCOBERTO", nome, ip)
                self.mostrar()
        elif t == "GOODBYE":
            with self.lock:
                ent = self.tabela.pop(msg["name"], None)
            if ent:
                self.log("SAIDA_GOODBYE", msg["name"], ent["ip"])
                self.mostrar()
        elif t == "QUERY" and not self.monitor:
            if msg.get("service") in ("*", self.servico):
                # atraso aleatorio evita que todos respondam no mesmo instante (ideia do mDNS real)
                threading.Timer(random.uniform(0.02, 0.12), self.anunciar).start()

    def escutar(self):
        while self.rodando:
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if msg.get("id") == self.id:        # ignora meus proprios pacotes (loopback)
                continue
            with self.lock:
                self.m["rx_pkts"] += 1
                self.m["rx_bytes"] += len(data)
            self.tratar(msg, addr[0])

    def mostrar(self):
        with self.lock:
            linhas = sorted(self.tabela.items())
        print(f"\n--- dispositivos ativos ({len(linhas)}) ---")
        for nome, e in linhas:
            print(f"{nome:<18} {e['ip']:<15} {e['servico']}:{e['porta']}  ttl_restante={e['expira']-time.time():.0f}s")

    def metricas(self):
        with self.lock:
            d = dict(self.m, tabela=len(self.tabela))
        self.log("METRICAS", det=";".join(f"{k}={v}" for k, v in d.items()))

    # ---------- laco principal ----------
    def manutencao(self):
        t0 = time.time()
        prox_anuncio = t0 + self.ttl / 2          # reanuncio periodico
        prox_metr = t0 + 60
        while self.rodando:
            time.sleep(0.25)
            agora = time.time()
            with self.lock:
                vencidos = [n for n, e in self.tabela.items() if e["expira"] <= agora]
                ips = {n: self.tabela[n]["ip"] for n in vencidos}
                for n in vencidos: del self.tabela[n]
            for n in vencidos:
                self.log("EXPIRADO", n, ips[n]); self.mostrar()
            if agora >= prox_anuncio:
                self.anunciar(); prox_anuncio = agora + self.ttl / 2
            if agora >= prox_metr:
                self.metricas(); prox_metr = agora + 60
            if self.a.morrer_apos and agora - t0 >= self.a.morrer_apos:
                self.log("MORTE_ABRUPTA", self.nome); self.metricas()
                import os; os._exit(0)             # sem GOODBYE: simula cabo puxado/queda
            if self.a.sair_apos and agora - t0 >= self.a.sair_apos:
                return

    def rodar(self):
        self.log("INICIO", self.nome, det="monitor" if self.monitor else "dispositivo")
        threading.Thread(target=self.escutar, daemon=True).start()
        self.consultar()
        self.anunciar()
        try:
            self.manutencao()
        except KeyboardInterrupt:
            pass
        self.despedir(); self.metricas()
        self.rodando = False
        time.sleep(0.2)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--nome", default=f"disp-{random.randint(100,999)}")
    p.add_argument("--servico", default="generico")
    p.add_argument("--porta-servico", type=int, default=8000)
    p.add_argument("--ttl", type=int, default=30, help="segundos de validade da entrada")
    p.add_argument("--iface", help="IP da interface (use se tiver varias: Wi-Fi, VM, VPN)")
    p.add_argument("--log", help="arquivo CSV de eventos")
    p.add_argument("--monitor", action="store_true", help="so escuta, nao se anuncia")
    p.add_argument("--morrer-apos", type=float, help="saida abrupta apos N segundos")
    p.add_argument("--sair-apos", type=float, help="saida com GOODBYE apos N segundos")
    No(p.parse_args()).rodar()
