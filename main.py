import hashlib
import json
import os
import socket
import struct
import threading
import time
import uuid

# TODO: testar fora do docker
IP_BROADCAST = os.getenv("IP_BROADCAST", "127.255.255.255")
PASTA_COMPARTILHADA = "./one_piece_drive"
meu_id = str(uuid.uuid4())[:8]  # corta o id pra nao ficar gigante
minha_porta_tcp = 0
socket_tracker_global = None
TRACKER_HOST = os.getenv("TRACKER_HOST", "127.0.0.1")
TRACKER_PORT = int(os.getenv("TRACKER_PORT", 9000))

# se nao tem a pasta, cria
if not os.path.exists(PASTA_COMPARTILHADA):
    os.makedirs(PASTA_COMPARTILHADA)


# gera o hash pra monitorar o arquivo
def gerar_hash_arquivo(caminho_arquivo):
    hash_md5 = hashlib.md5()
    try:
        # picota o arquivo pra nao estourar a memoria
        with open(caminho_arquivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Erro gerando o hash: {e}")
        return None


def escanear_pasta():
    estado_atual = {}
    for raiz, _, arquivos in os.walk(
        PASTA_COMPARTILHADA
    ):  # tem o _ pq nao vai precisar usar as subpastas
        for arquivo in arquivos:
            # gambiarra pra nao tentar baixar um arquivo grande que nao ta baixado completo
            if arquivo.endswith(".tmp"):
                continue

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


def iniciar_servidor_tcp():
    global minha_porta_tcp
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("", 0))  # SO vai escolher a porta
    minha_porta_tcp = servidor.getsockname()[1]
    servidor.listen(5)

    print(f"[{meu_id}] subiu na porta {minha_porta_tcp}")

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

        if msg["acao"] == "GET_ARQUIVO":
            caminho_relativo = msg["arquivo"]
            caminho_completo = os.path.join(PASTA_COMPARTILHADA, caminho_relativo)
            if os.path.exists(caminho_completo):
                tamanho = os.path.getsize(caminho_completo)
                # transforma o json em bytes
                json_bytes = json.dumps({"tamanho": tamanho}).encode("utf-8")
                # pega o tamanho do json
                cabecalho = struct.pack("!I", len(json_bytes))
                # manda o tamanho do cabecalho primeiro
                conexao.sendall(cabecalho)
                # depois manda o cabecalho
                conexao.sendall(json_bytes)
                # depois manda o arquivo
                with open(caminho_completo, "rb") as f:
                    while chunk := f.read(4096):
                        conexao.sendall(chunk)
    except Exception as e:
        print(f"Erro no servidor tcp: {e}")
    finally:
        conexao.close()


def baixar_arquivo(ip, porta, arquivo_relativo, tamanho_esperado):
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((ip, porta))

        req = json.dumps({"acao": "GET_ARQUIVO", "arquivo": arquivo_relativo})
        cliente.sendall(req.encode("utf-8"))

        # vai receber o tamanho do cabecalho da outra funcao
        tamanho_cabecalho = cliente.recv(4)
        if not tamanho_cabecalho or len(tamanho_cabecalho) < 4:
            print("cabecalho nao chegou todo")
        tamanho_json = struct.unpack("!I", tamanho_cabecalho)[0]
        resposta = cliente.recv(tamanho_json)
        info = json.loads(resposta.decode("utf-8"))

        if info.get("tamanho") == tamanho_esperado:
            caminho_salvamento = os.path.join(PASTA_COMPARTILHADA, arquivo_relativo)
            caminho_tmp = caminho_salvamento + ".tmp"

            os.makedirs(os.path.dirname(caminho_salvamento) or ".", exist_ok=True)

            with open(caminho_tmp, "wb") as f:
                bytes_recebidos = 0
                while bytes_recebidos < tamanho_esperado:
                    leitura = min(4096, tamanho_esperado - bytes_recebidos)
                    chunk = cliente.recv(leitura)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_recebidos += len(chunk)
            if bytes_recebidos == tamanho_esperado:
                if os.path.exists(caminho_salvamento):
                    os.remove(caminho_salvamento)
                os.rename(caminho_tmp, caminho_salvamento)
                print(f"download do arquivo {arquivo_relativo} concluído!")
    except Exception as e:
        print(f"Erro ao baixar arquivo: {e}")
    finally:
        cliente.close()


def monitor_eventos():
    global socket_tracker_global
    estado_anterior = escanear_pasta()
    while True:
        time.sleep(3)
        if socket_tracker_global is None:
            continue
        estado_atual = escanear_pasta()
        arquivos_deletados = [arq for arq in estado_anterior if arq not in estado_atual]
        arquivos_novos = [arq for arq in estado_atual if arq not in estado_anterior]
        arquivos_modificados = []
        for arq in estado_atual:
            if (
                arq in estado_anterior
                and estado_atual[arq]["hash"] != estado_anterior[arq]["hash"]
            ):
                arquivos_modificados.append(arq)

        arquivos_renomeados = []
        for deletado in arquivos_deletados[:]:
            for novo in arquivos_novos[:]:
                if estado_anterior[deletado]["hash"] == estado_atual[novo]["hash"]:
                    arquivos_renomeados.append((deletado, novo))
                    arquivos_deletados.remove(deletado)
                    arquivos_novos.remove(novo)
                    break
        eventos_tracker = []
        for antigo, novo in arquivos_renomeados:
            eventos_tracker.append(
                {"acao": "RENAME", "arquivo": antigo, "novo_nome": novo}
            )
        for arq in arquivos_deletados:
            eventos_tracker.append({"acao": "DELETE", "arquivo": arq})
        for arq in arquivos_novos:
            eventos_tracker.append(
                {
                    "acao": "CREATE",
                    "arquivo": arq,
                    "tamanho": estado_atual[arq]["tamanho"],
                }
            )
        for arq in arquivos_modificados:
            eventos_tracker.append(
                {
                    "acao": "MODIFY",
                    "arquivo": arq,
                    "tamanho": estado_atual[arq]["tamanho"],
                }
            )

        for evento in eventos_tracker:
            evento["remetente"] = meu_id
            evento["tcp_port"] = minha_porta_tcp
            evento["ip"] = socket_tracker_global.getsockname()[0]
            try:
                msg = json.dumps(evento)
                socket_tracker_global.sendall(msg.encode("utf-8"))
                print(
                    f"[{meu_id}] Enviei evento para o Tracker: {evento['acao']} em '{evento['arquivo']}'"
                )
            except Exception as e:
                print(f"Erro ao enviar evento: {e}")
        estado_anterior = estado_atual


def escutar_tracker():
    global socket_tracker_global
    while True:
        cliente_tracker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            print(f"[{meu_id}] Tentando conectar ao tracker")
            cliente_tracker.connect((TRACKER_HOST, TRACKER_PORT))
            socket_tracker_global = cliente_tracker
            msg_registro = json.dumps({"acao": "REGISTRO", "id": meu_id})
            cliente_tracker.sendall(msg_registro.encode("utf-8"))
            print(f"[{meu_id}] Conectado ao tracker com sucesso")
            while True:
                dados = cliente_tracker.recv(4096)
                if not dados:
                    print(f"[{meu_id}] Conexao perdida, tentando reconectar")
                    break
                evento = json.loads(dados.decode("utf-8"))
                acao = evento.get("acao")
                arquivo = evento.get("arquivo")
                ip_remetente = evento.get("ip")
                porta_remetente = evento.get("tcp_port")
                print(
                    f"[{meu_id}] O nó {evento.get('remetente')} mandou fazer {acao} no arquivo{arquivo}"
                )
                caminho_completo = os.path.join(PASTA_COMPARTILHADA, arquivo)
                try:
                    if acao == "DELETE":
                        if os.path.exists(caminho_completo):
                            os.remove(caminho_completo)
                            print(f"[{meu_id}] Arquivo {arquivo} foi apagado.")
                    elif acao == "RENAME":
                        novo_nome = evento.get("novo_nome")
                        caminho_novo = os.path.join(PASTA_COMPARTILHADA, novo_nome)
                        if os.path.exists(caminho_completo) and not os.path.exists(
                            caminho_novo
                        ):
                            os.rename(caminho_completo, caminho_novo)
                            print(
                                f"[{meu_id}] Arquivo {arquivo} renomeado com sucesso."
                            )
                    elif acao in ["CREATE", "MODIFY"]:
                        tamanho = evento.get("tamanho")
                        if (
                            not os.path.exists(caminho_completo)
                            or os.path.getsize(caminho_completo) != tamanho
                        ):
                            if ip_remetente:
                                baixar_arquivo(
                                    ip_remetente, porta_remetente, arquivo, tamanho
                                )
                except Exception as e:
                    print(
                        f"[{meu_id}] Erro ao tentar fazer {acao} no arquivo {arquivo}: {e}"
                    )
        except Exception as e:
            print(f"Erro na conexao com o tracker: {e}")
            time.sleep(5)
        finally:
            cliente_tracker.close()


if __name__ == "__main__":
    threading.Thread(target=iniciar_servidor_tcp, daemon=True).start()

    time.sleep(1)
    threading.Thread(target=escutar_tracker, daemon=True).start()
    threading.Thread(target=monitor_eventos, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando nó...")
