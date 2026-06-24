import hashlib
import json
import os
import random
import socket
import threading
import time
import uuid

# configs e estado global
PORTA_BROADCAST = 50000
IP_BROADCAST =  os.getenv("IP_BROADCAST","127.255.255.255")
PASTA_COMPARTILHADA = "./one_piece_drive"
meu_id = str(uuid.uuid4())[:8]
nos_conhecidos = {}  # Formato: {'id': {'ip': '...', 'tcp_port': 1234, 'ultima_vez': ...}}
lock = threading.Lock()
meu_tcp_port = 0

# garantir que a pasta existe
if not os.path.exists(PASTA_COMPARTILHADA):
    os.makedirs(PASTA_COMPARTILHADA)


# verificação dos arquivos locais
def gerar_hash_arquivo(caminho_arquivo):
    hash_md5 = hashlib.md5()
    try:
        with open(caminho_arquivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except:
        return None


def escanear_pasta():
    estado_atual = {}
    for raiz, _, arquivos in os.walk(PASTA_COMPARTILHADA):
        for arquivo in arquivos:
            caminho_completo = os.path.join(raiz, arquivo)
            caminho_relativo = os.path.relpath(caminho_completo, PASTA_COMPARTILHADA)
            hash_arquivo = gerar_hash_arquivo(caminho_completo)
            if hash_arquivo:
                estado_atual[caminho_relativo] = {
                    "hash": hash_arquivo,
                    "tamanho": os.path.getsize(caminho_completo),
                    "modificado_em": os.path.getmtime(caminho_completo),
                }
    return estado_atual


# descoberta dos outros nos
def ouvinte_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", PORTA_BROADCAST))
    while True:
        try:
            dados, ip_origem = sock.recvfrom(1024)
            msg = json.loads(dados.decode("utf-8"))
            if msg["id"] == meu_id:
                continue
            with lock:
                nos_conhecidos[msg["id"]] = {
                    "ip": ip_origem[0],
                    "tcp_port": msg[
                        "tcp_port"
                    ],  # pega a porta tcp do nó que tá anunciando
                    "ultima_vez": time.time(),
                }
        except:
            pass


def anunciante_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    while True:
        if meu_tcp_port != 0:
            msg = json.dumps({"id": meu_id, "tcp_port": meu_tcp_port})
            try:
                sock.sendto(msg.encode("utf-8"), (IP_BROADCAST, PORTA_BROADCAST))
            except:
                pass
        time.sleep(5)


def iniciar_servidor_tcp():
    global meu_tcp_port
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("", 0))
    meu_tcp_port = servidor.getsockname()[1]
    servidor.listen(5)

    print(f"[{meu_id}] Nó rodando. Escutando TCP na porta {meu_tcp_port}")

    while True:
        cliente_socket, _ = servidor.accept()
        threading.Thread(
            target=lidar_com_cliente, args=(cliente_socket,), daemon=True
        ).start()


def lidar_com_cliente(conexao):
    try:
        dados = conexao.recv(4096)
        if not dados:
            return
        msg = json.loads(dados.decode("utf-8"))
        if msg["acao"] == "GET_INDEX":
            meu_index = escanear_pasta()
            resposta = json.dumps({"acao": "INDEX", "dados": meu_index})
            conexao.sendall(resposta.encode("utf-8"))
        elif msg["acao"] == "GET_ARQUIVO":
            caminho_relativo = msg["arquivo"]
            caminho_completo = os.path.join(PASTA_COMPARTILHADA, caminho_relativo)
            if os.path.exists(caminho_completo):
                tamanho = os.path.getsize(caminho_completo)
                conexao.sendall(json.dumps({"tamanho": tamanho}).encode("utf-8"))
                time.sleep(0.1)
                with open(caminho_completo, "rb") as f:
                    while chunk := f.read(4096):
                        conexao.sendall(chunk)
    except Exception as e:
        print(f"Erro no servidor tcp {e}")
    finally:
        conexao.close()


# parte de sincronização
def baixar_arquivo(ip, porta, arquivo_relativo, tamanho_esperado):
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((ip, porta))

        req = json.dumps({"acao": "GET_ARQUIVO", "arquivo": arquivo_relativo})
        cliente.sendall(req.encode("utf-8"))

        resp = cliente.recv(1024)
        info = json.loads(resp.decode("utf-8"))

        if info.get("tamanho") == tamanho_esperado:
            caminho_salvamento = os.path.join(PASTA_COMPARTILHADA, arquivo_relativo)
            os.makedirs(os.path.dirname(caminho_salvamento) or ".", exist_ok=True)

            print(f"Baixando {arquivo_relativo} de {ip}:{porta}...")
            with open(caminho_salvamento, "wb") as f:
                bytes_recebidos = 0
                while bytes_recebidos < tamanho_esperado:
                    leitura = min(4096, tamanho_esperado - bytes_recebidos)
                    chunk = cliente.recv(leitura)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_recebidos += len(chunk)
            print(f"download do arquivo {arquivo_relativo} concluído!")
    except Exception as e:
        print(f"Erro ao baixar arquivo: {e}")
    finally:
        cliente.close()


def sincronização():
    while True:
        time.sleep(10)

        with lock:
            if not nos_conhecidos:
                continue
            id_alvo = random.choice(list(nos_conhecidos.keys()))
            alvo = nos_conhecidos[id_alvo]

        try:
            cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cliente.connect((alvo["ip"], alvo["tcp_port"]))
            cliente.sendall(json.dumps({"acao": "GET_INDEX"}).encode("utf-8"))

            resposta_raw = cliente.recv(65536)
            cliente.close()

            msg = json.loads(resposta_raw.decode("utf-8"))
            index_colega = msg.get("dados", {})
            meu_index = escanear_pasta()

            para_baixar = []
            for arquivo, info_colega in index_colega.items():
                if arquivo not in meu_index:
                    para_baixar.append((arquivo, info_colega["tamanho"]))
                elif (
                    meu_index[arquivo]["hash"] != info_colega["hash"]
                    and info_colega["modificado_em"]
                    > meu_index[arquivo]["modificado_em"]
                ):
                    para_baixar.append((arquivo, info_colega["tamanho"]))

            for arquivo, tamanho in para_baixar:
                baixar_arquivo(alvo["ip"], alvo["tcp_port"], arquivo, tamanho)
        except Exception as e:
            pass


if __name__ == "__main__":
    threading.Thread(target=ouvinte_udp, daemon=True).start()
    threading.Thread(target=iniciar_servidor_tcp, daemon=True).start()

    time.sleep(1)
    threading.Thread(target=anunciante_udp, daemon=True).start()
    threading.Thread(target=sincronização, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando nó...")
