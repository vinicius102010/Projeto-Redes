import socket
import threading
import json

PORTA_TRACKER = 9000
nos_conectados = {}
lock = threading.Lock()

def conectar_com_no(conexao, endereco):
    id_no = None
    try:
        dados_iniciais = conexao.recv(1024)
        if not dados_iniciais: return
        msg_inicial = json.loads(dados_iniciais.decode('utf-8'))
        if msg_inicial.get('acao') == 'REGISTRO':
            id_no = msg_inicial['id']
            with lock:
                nos_conectados[id_no] = conexao
            print(f"[Tracker] Nó '{id_no} entrou'")
            
        while True:
            dados = conexao.recv(4096)
            if not dados:
                break
            evento = json.loads(dados.decode('utf-8'))
            acao = evento.get('acao')
            arquivo = evento.get('arquivo')
            print(f"[Tracker]  repassando {acao} em '{arquivo}' de {id_no}")
            transmitir_evento(evento, remetente_id=id_no)
            
    except Exception as e:
        print(f"[Tracker]  nao conectou no {id_no}: {e}")
    finally:
        if id_no:
            with lock:
                if id_no in nos_conectados:
                    del nos_conectados[id_no]
            print(f"[Tracker] Nó '{id_no}' desconectou.")
        conexao.close()

def transmitir_evento(evento, remetente_id):
    mensagem_bytes = json.dumps(evento).encode('utf-8') 
    nos_encerrados = []
    with lock:
        for id_alvo, conexao in nos_conectados.items():
            if id_alvo != remetente_id:
                try:
                    conexao.sendall(mensagem_bytes)
                except Exception:
                    nos_encerrados.append(id_alvo)
        for id_encerrado in nos_encerrados:
            del nos_conectados[id_encerrado]
            
def iniciar_tracker():
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(('0.0.0.0', PORTA_TRACKER))
    servidor.listen()
    print(f"Tracker online na porta {PORTA_TRACKER}")
    while True:
        conexao, endereco = servidor.accept()
        threading.Thread(target=conectar_com_no, args=(conexao, endereco), daemon=True).start()

if __name__ == '__main__':
    iniciar_tracker()
        