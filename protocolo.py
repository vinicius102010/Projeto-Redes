import json
import socket
import threading


# parte do servidor tcp que vai estar escutando.
def iniciar_server_tcp():
    """vai iniciar o servidor tcp pra receber conversas de outros nos"""
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # colocar pra fazer o bind na porta 0 pra alocar uma porta livre qualquer na hora de começar
    servidor.bind(("", 0))
    porta_atribuida = servidor.getsockname()[1]  # vai pergar a porta
    servidor.listen(5)  # fila de ate 5 conexoes simultaneas
    print(f"Servidor iniciado e escutando conecçoes na porta {porta_atribuida}")
    while True:
        # o accept vai travar a thread ate que alguems e conecte
        cliente_socket, endereço_cliente = servidor.accept()
        print(f"Nova conexão de {endereço_cliente}")

        # vai criar uma thread so pra atender ao cliente e voltar a escutar
        threading.Thread(
            target=atender_cliente, args=(cliente_socket,), daemon=True
        ).start()


def atender_cliente(cliente_socket):
    # vai ler a mensagem em JSON entender e fechar a conexao
    try:
        # vai receber ate 4096 bytes
        dados = cliente_socket.recv(4096)
        if not dados:
            return
        # vai transformar os bytes de volta em um dicionario
        mensagem = json.loads(dados.decode("utf-8"))
        print(f"Mensagem recebida:Ação -> {mensagem.get('acao')}")

        # fazer um roteador de açoes (onde o protocolo vai funcionar)
        if mensagem["acao"] == "COMPARAR_INDEX":
            index_do_colega = mensagem["dados"]
            print(
                f"o no quer comparar indices, ele tem {len(index_do_colega)} arquivos no index dele"
            )
            # depois cruzar os outros indexes com o nosso
            resposta = json.dumps(
                {"status": "sucesso", "mensagem": "index recebido com sucesso"}
            )
            cliente_socket.send(resposta.encode("utf-8"))
    except Exception as e:
        print(f"Erro ao atender cliente: {e}")
    finally:
        cliente_socket.close()  # fecha a conexao com o cliente depois de atender


# cliente tcp
def simular_envio_mensagem(porta_destino):
    # função para simular o nó B mandando mensagem para o A
    try:
        # criar um socket tcp para o cliente, conecta e monta a mensagem
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect(("127.0.0.1", porta_destino))
        mensagem_teste = {
            "acao": "COMPARAR_INDEX",
            "dados": {"arquivo1.txt": {"hash": "abc123", "tamanho": 1024}},
        }
        # envia a requisição
        print(f"\n Enviando requisição")
        cliente.send(json.dumps(mensagem_teste).encode("utf-8"))
        # recebe a resposta
        resposta = cliente.recv(4096)
        print(f"Resposta recebida: {json.loads(resposta.decode('utf-8'))}")
        cliente.close()
    except Exception as e:
        print(f"Erro ao simular envio de mensagem: {e}")


if __name__ == "__main__":
    t_servidor = threading.Thread(target=iniciar_server_tcp, daemon=True)
    t_servidor.start()
    import time

    time.sleep(1)
    porta = int(input("\nDigite a porta que apareceu lá em cima para testar o envio: "))

    simular_envio_mensagem(porta)

    # Segura o programa aberto para você ler a tela
    time.sleep(2)
