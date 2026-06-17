import json
import socket
import threading
import time
import uuid

# configuração de estado global
BROADCAST_PORT = 50000
BROADCAST_IP = "127.255.255.255"  # endereço universal de broadcast da rede

meu_id = str(uuid.uuid4())[:8]  # gerar um ID aleatorio de 8 caracteres para o nó
nos_conhecidos = {}  # dicionário para armazenar os nós conhecidos e seus tempos de última atualização
lock = threading.Lock()
# cadeado para proteger o dicionario de conflitos entre as threads


# thread 01 listener
def ouvinte_udp():
    """fica escutando a rede para descobrir os nos"""
    # criar o socket udp
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # config para permitir que multiplos terminais escutem a mesma porta ao mesmo tempo
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(
        ("", BROADCAST_PORT)
    )  # quando inicia, escuta em todas as interfaces de rede
    print(f"[{meu_id}] Ouvindo na porta {BROADCAST_PORT}...")
    while True:
        try:
            # recvfrom trava a thread ate chegar uma mensagem
            dados, endereco_ip = sock.recvfrom(1024)
            mensagem = json.loads(
                dados.decode("utf-8")
            )  # decodificar a mensagem recebida
            # pegar os dados antes de alterar a variavel dos nos conhecidos para evitar conflitos entre as threads
            if mensagem["id"] == meu_id:
                continue  # ignorar mensagens do proprio nó
            with lock:
                novo_no = mensagem["id"] not in nos_conhecidos
                # atualiza a lista de nos
                nos_conhecidos[mensagem["id"]] = {
                    "ip": endereco_ip[0],
                    "ultima_atualizacao": time.time(),  # marca o tempo da ultima atualização do nó
                }
                if novo_no:
                    print(
                        f"[{meu_id}] Novo nó descoberto: {mensagem['id']} ({endereco_ip[0]})"
                    )

        except Exception as e:
            print(f"Erro no ouvinte: {e}")


# thread 02 broadcaster
def anunciante_udp():
    """fica anunciando a presença do nó na rede a cada 5 segundos"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(
        socket.SOL_SOCKET, socket.SO_BROADCAST, 1
    )  # config para permitir broadcast
    # prepara a mensagem em formato json
    mensagem = json.dumps({"id": meu_id, "acao": "ANUNCIO"})
    print(f"[{meu_id}] Anunciando presença a cada 5 segundos...")
    while True:
        try:
            # converte para bytes e envia pra rede
            sock.sendto(
                mensagem.encode("utf-8"), (BROADCAST_IP, BROADCAST_PORT)
            )  # envia a mensagem para o endereço de broadcast
        except Exception as e:
            print(f"Erro no anunciante: {e}")
        time.sleep(5)  # espera 5 segundos antes de anunciar novamente


# nucleo do programa
if __name__ == "__main__":
    print(f"Iniciando nó com ID: {meu_id}")
    # cria as threads, utiliza o "deamon=true" para que se o programa fechar ele fecha junto com as threads
    t_ouvinte = threading.Thread(target=ouvinte_udp, daemon=True)
    t_anunciante = threading.Thread(target=anunciante_udp, daemon=True)

    # starta os dois
    t_ouvinte.start()
    t_anunciante.start()
    # loop principal para manter o programa rodando
    try:
        while True:
            time.sleep(10)
            with lock:
                agora = time.time()
                # lista os nos que nao mandam nada a mais de 15 segundos
                nos_mortos = [
                    id_no
                    for id_no, info in nos_conhecidos.items()
                    if agora - info["ultima_atualizacao"] > 15
                ]
                for id_no in nos_mortos:
                    print(
                        f"\n[{meu_id}] Nó {id_no} caiu ou desconectou, removendo da lista"
                    )
                    del nos_conhecidos[id_no]  # remove os nos mortos da lista
            # imprime como o sistema esta agora
            print(f"\n[{meu_id}] Nós ativos: {list(nos_conhecidos.keys())}")

    except KeyboardInterrupt:
        print(f"[{meu_id}] Encerrando nó...")
