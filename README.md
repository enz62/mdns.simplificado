# mDNS Simplificado

Projeto acadêmico desenvolvido em Python para implementar uma versão simplificada do protocolo mDNS (*Multicast Domain Name System*), utilizando comunicação UDP multicast e mensagens no formato JSON.

O sistema permite a descoberta de dispositivos na rede, o envio periódico de anúncios e a remoção de dispositivos por meio de mensagens GOODBYE ou pela expiração do TTL (*Time to Live*).

## Arquivos do projeto

| Arquivo | Descrição |
|---|---|
| `mdns_simples.py` | Implementação principal do mDNS simplificado. Responsável pela comunicação entre dispositivos, descoberta, envio de anúncios, mensagens GOODBYE e controle de TTL. |
| `analisar.py` | Responsável por analisar os dados e métricas gerados durante as execuções do sistema. |
| `automatizar_testes.py` | Automatiza os experimentos, permitindo configurar cenários com diferentes quantidades de dispositivos, repetições, duração, TTL e modos de encerramento. |
| `referencia_mdns_real.py` | Implementação de referência utilizando a biblioteca Zeroconf, para observar o funcionamento de uma solução baseada em uma biblioteca especializada. |

## Tecnologias utilizadas

- Python
- UDP
- Multicast
- JSON
- Biblioteca Zeroconf
- Wireshark (análise do tráfego de rede)

## Experimentos

Foram realizados testes com cenários de 2, 4 e 8 dispositivos, com 5 repetições para cada cenário.

Foram avaliados dois modos de encerramento:

- **Saída normal:** os dispositivos enviam uma mensagem GOODBYE antes de encerrar.
- **Saída abrupta:** os dispositivos encerram sem enviar GOODBYE, sendo removidos pelos demais após a expiração do TTL.

Os experimentos têm como objetivo observar o funcionamento da descoberta de dispositivos, a remoção de participantes e as diferenças no tráfego de rede entre os dois modos.