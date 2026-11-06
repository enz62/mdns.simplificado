#!/usr/bin/env python3
"""
Automatiza os testes do mDNS simplificado.

Coloque este arquivo na mesma pasta de mdns_simples.py.

Exemplo de teste curto:
    py automatizar_testes.py --cenarios 2 --repeticoes 1 --duracao 30

Execução oficial:
    py automatizar_testes.py --cenarios 2 4 8 --repeticoes 5 --duracao 90 --ttl 30

Cada execução cria uma pasta própria, sem sobrescrever CSVs anteriores.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


PASTA_PROJETO = Path(__file__).resolve().parent
ARQUIVO_MDNS = PASTA_PROJETO / "mdns_simples.py"


def iniciar_processo(comando, arquivo_console):
    """Inicia um processo e guarda a saída dele em um arquivo de texto."""
    console = open(arquivo_console, "w", encoding="utf-8")
    try:
        processo = subprocess.Popen(
            comando,
            cwd=PASTA_PROJETO,
            stdout=console,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        console.close()
        raise
    return processo, console


def encerrar_se_necessario(processo):
    """Evita deixar processos do teste rodando caso ocorra algum erro."""
    if processo is not None and processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait()


def executar_teste(quantidade, numero_execucao, args, pasta_lote):
    pasta = pasta_lote / f"dispositivos_{quantidade}" / f"execucao_{numero_execucao:02d}"
    pasta.mkdir(parents=True, exist_ok=False)

    modo = args.modo
    margem = 10
    intervalo_inicio = args.intervalo_inicio

    # O monitor precisa ficar ativo até depois da saída dos dispositivos.
    # No modo abrupto, também esperamos o TTL expirar na tabela do monitor.
    duracao_monitor = args.duracao + (quantidade - 1) * intervalo_inicio + margem
    if modo == "abrupta":
        duracao_monitor += args.ttl

    monitor_csv = pasta / "monitor.csv"
    monitor_console_path = pasta / "monitor_console.txt"
    monitor_comando = [
        sys.executable, str(ARQUIVO_MDNS),
        "--monitor",
        "--ttl", str(args.ttl),
        "--sair-apos", str(duracao_monitor),
        "--log", str(monitor_csv),
    ]

    processos = []
    consoles = []
    try:
        monitor, console_monitor = iniciar_processo(
            monitor_comando, monitor_console_path
        )
        processos.append(monitor)
        consoles.append(console_monitor)

        # Dá tempo para o monitor entrar no grupo multicast antes dos nós.
        time.sleep(args.espera_monitor)
        if monitor.poll() is not None:
            raise RuntimeError(
                f"Monitor encerrou antes dos dispositivos (código {monitor.returncode}). "
                f"Veja {monitor_console_path}"
            )

        for indice in range(1, quantidade + 1):
            nome = f"d{indice}"
            csv_no = pasta / f"{nome}.csv"
            console_no_path = pasta / f"{nome}_console.txt"

            comando = [
                sys.executable, str(ARQUIVO_MDNS),
                "--nome", nome,
                "--servico", "web" if indice % 2 else "impressora",
                "--ttl", str(args.ttl),
                "--log", str(csv_no),
            ]

            if modo == "saida":
                comando += ["--sair-apos", str(args.duracao)]
            else:
                comando += ["--morrer-apos", str(args.duracao)]

            processo, console_no = iniciar_processo(comando, console_no_path)
            processos.append(processo)
            consoles.append(console_no)

            if indice < quantidade:
                time.sleep(intervalo_inicio)

        # Espera cada dispositivo terminar por conta própria.
        limite_no = args.duracao + args.ttl + 20
        for indice, processo in enumerate(processos[1:], start=1):
            try:
                codigo = processo.wait(timeout=limite_no)
            except subprocess.TimeoutExpired:
                raise RuntimeError(
                    f"O dispositivo d{indice} não terminou dentro do tempo esperado."
                )
            if codigo != 0:
                raise RuntimeError(
                    f"O dispositivo d{indice} terminou com código {codigo}. "
                    f"Consulte d{indice}_console.txt."
                )

        # O monitor termina sozinho e grava as métricas finais.
        try:
            codigo_monitor = monitor.wait(timeout=duracao_monitor + 20)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "O monitor não encerrou no tempo esperado. Consulte monitor_console.txt."
            )

        if codigo_monitor != 0:
            raise RuntimeError(
                f"O monitor terminou com código {codigo_monitor}. "
                "Consulte monitor_console.txt."
            )

        configuracao = {
            "quantidade_dispositivos": quantidade,
            "execucao": numero_execucao,
            "modo_saida": modo,
            "ttl_segundos": args.ttl,
            "duracao_dispositivos_segundos": args.duracao,
            "intervalo_inicio_segundos": intervalo_inicio,
            "duracao_monitor_segundos": duracao_monitor,
            "python": sys.version,
            "inicio_lote": pasta_lote.name,
        }
        (pasta / "configuracao.json").write_text(
            json.dumps(configuracao, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"  Concluído: {pasta.relative_to(PASTA_PROJETO)}")
        return True

    finally:
        # Se algo falhar, encerra os processos que ainda estiverem ativos.
        for processo in processos:
            encerrar_se_necessario(processo)
        for console in consoles:
            console.close()


def main():
    parser = argparse.ArgumentParser(
        description="Executa automaticamente os testes do mDNS simplificado."
    )
    parser.add_argument(
        "--cenarios", nargs="+", type=int, choices=[2, 4, 8],
        default=[2, 4, 8],
        help="quantidades de dispositivos (padrão: 2 4 8)",
    )
    parser.add_argument(
        "--repeticoes", type=int, default=5,
        help="quantas vezes repetir cada cenário (padrão: 5)",
    )
    parser.add_argument(
        "--duracao", type=int, default=90,
        help="tempo de funcionamento de cada dispositivo, em segundos (padrão: 90)",
    )
    parser.add_argument(
        "--ttl", type=int, default=30,
        help="TTL em segundos (padrão: 30)",
    )
    parser.add_argument(
        "--modo", choices=["saida", "abrupta"], default="saida",
        help="'saida' envia GOODBYE; 'abrupta' simula queda e espera o TTL",
    )
    parser.add_argument(
        "--espera-monitor", type=float, default=1.5,
        help="segundos para o monitor iniciar antes dos dispositivos",
    )
    parser.add_argument(
        "--intervalo-inicio", type=float, default=0.5,
        help="intervalo entre o início de cada dispositivo",
    )
    args = parser.parse_args()

    if not ARQUIVO_MDNS.is_file():
        print("ERRO: mdns_simples.py não foi encontrado.")
        print("Coloque automatizar_testes.py na mesma pasta de mdns_simples.py.")
        return 1
    if args.repeticoes < 1 or args.duracao < 1 or args.ttl < 1:
        print("ERRO: repeticoes, duracao e ttl precisam ser maiores que zero.")
        return 1

    identificador = datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta_lote = PASTA_PROJETO / "resultados_automatizados" / f"lote_{identificador}"
    pasta_lote.mkdir(parents=True, exist_ok=False)

    total = len(args.cenarios) * args.repeticoes
    atual = 0

    print(f"Modo: {args.modo}")
    print(f"Cenários: {args.cenarios}")
    print(f"Repetições por cenário: {args.repeticoes}")
    print(f"Duração por dispositivo: {args.duracao} s | TTL: {args.ttl} s")
    print(f"Resultados: {pasta_lote}")
    print(f"Total de execuções: {total}\n")

    falhas = []
    for quantidade in args.cenarios:
        print(f"=== Cenário com {quantidade} dispositivos ===")
        for repeticao in range(1, args.repeticoes + 1):
            atual += 1
            print(f"[{atual}/{total}] Execução {repeticao}/{args.repeticoes}...")
            try:
                executar_teste(quantidade, repeticao, args, pasta_lote)
            except Exception as erro:
                falhas.append((quantidade, repeticao, str(erro)))
                print(f"  FALHOU: {erro}")
                print("  O script encerrou os processos restantes desta execução.")
                # Continua para a próxima repetição; os dados da falha são preservados.

    print("\n=== Fim da automação ===")
    print(f"Resultados salvos em: {pasta_lote}")
    if falhas:
        print(f"Execuções com falha: {len(falhas)}")
        for quantidade, repeticao, erro in falhas:
            print(f"- {quantidade} dispositivos, execução {repeticao}: {erro}")
        return 1

    print("Todas as execuções terminaram com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
