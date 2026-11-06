#!/usr/bin/env python3
"""Referencia mDNS real (RFC 6762/6763) com python-zeroconf. pip install zeroconf
  python3 referencia_mdns_real.py anunciar nome1      (registra um servico)
  python3 referencia_mdns_real.py ouvir               (lista servicos _http._tcp)
Capture com Wireshark filtrando 'mdns' e compare com 'udp.port == 5400' do prototipo."""
import socket, sys, time
from zeroconf import ServiceBrowser, ServiceInfo, ServiceListener, Zeroconf

TIPO = "_http._tcp.local."

class L(ServiceListener):
    def add_service(self, zc, t, n):
        print(f"{time.time():.6f} DESCOBERTO {n}")
    def remove_service(self, zc, t, n):
        print(f"{time.time():.6f} REMOVIDO {n}")
    def update_service(self, zc, t, n): pass

zc = Zeroconf()
try:
    if sys.argv[1] == "anunciar":
        ip = socket.gethostbyname(socket.gethostname())
        info = ServiceInfo(TIPO, f"{sys.argv[2]}.{TIPO}", addresses=[socket.inet_aton(ip)], port=8000, properties={})
        zc.register_service(info); print("registrado; Ctrl+C para sair (envia goodbye)")
        while True: time.sleep(1)
    else:
        ServiceBrowser(zc, TIPO, L())
        while True: time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    zc.close()
