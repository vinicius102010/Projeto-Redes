import os
import socket
import threading
import time


# função de transferencia
def enviar_arquivo_fisico(caminho_arquivo, socket_conexao):
    """Lê o arquivo do disco em pedaços e injeta no socket."""
    tamanho_arquivo = os.path.getsize(caminho_arquivo)
    nome_arquivo = os.path.basename(caminho_arquivo)
    print(
        f"[Remetente] Preparando para enviar '{nome_arquivo}' ({tamanho_arquivo} bytes)..."
    )

    try:
        # 'rb' = Read Binary. Essencial para não corromper imagens/PDFs.
        with open(caminho_arquivo, "rb") as f:
            bytes_enviados = 0

            while bytes_enviados < tamanho_arquivo:
                # Lê um pedaço de 4096 bytes (4KB)
                chunk = f.read(4096)
                if not chunk:
                    break  # Fim do arquivo

                # sendall garante que todos os bytes do chunk vão para a rede
                socket_conexao.sendall(chunk)
                bytes_enviados += len(chunk)

        print(f"[Remetente] ✅ Arquivo {nome_arquivo} enviado com sucesso!")

    except Exception as e:
        print(f"[Remetente] Erro ao enviar arquivo: {e}")


def receber_arquivo_fisico(caminho_destino, tamanho_esperado, socket_conexao):
    """Lê X bytes exatos do socket e salva no disco."""
    print(
        f"[Destinatário] Preparando para receber arquivo de {tamanho_esperado} bytes..."
    )

    try:
        # 'wb' = Write Binary.
        with open(caminho_destino, "wb") as f:
            bytes_recebidos = 0

            while bytes_recebidos < tamanho_esperado:
                # O limite de leitura é 4096, MAS se faltarem apenas 100 bytes pro fim,
                # lemos apenas 100 para não "roubar" a próxima mensagem JSON do socket.
                tamanho_leitura = min(4096, tamanho_esperado - bytes_recebidos)

                chunk = socket_conexao.recv(tamanho_leitura)
                if not chunk:
                    break  # A conexão caiu antes do arquivo terminar

                f.write(chunk)
                bytes_recebidos += len(chunk)

        if bytes_recebidos == tamanho_esperado:
            print(f"[Destinatário] ✅ Arquivo salvo com sucesso em: {caminho_destino}")
        else:
            print(
                f"[Destinatário] ⚠️ Erro: Recebeu {bytes_recebidos} de {tamanho_esperado} bytes."
            )

    except Exception as e:
        print(f"[Destinatário] Erro ao receber arquivo: {e}")

    # AMBIENTE DE TESTE ISOLADO


def servidor_recebedor(porta):
    """Simula o Nó que vai receber o arquivo."""
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.bind(("", porta))
    servidor.listen(1)

    print(f"[Destinatário] Aguardando conexão na porta {porta}...")
    conexao, endereco = servidor.accept()

    # Aqui, na prática real, nós já teríamos recebido o JSON dizendo qual é o arquivo
    # e qual o tamanho. Para o teste isolado, vamos fixar o tamanho pelo que criamos.
    tamanho_do_teste = os.path.getsize("teste_envio.txt")

    # Chama a função principal de recebimento
    receber_arquivo_fisico("teste_recebido.txt", tamanho_do_teste, conexao)
    conexao.close()
    servidor.close()


def cliente_remetente(porta):
    """Simula o Nó que vai enviar o arquivo."""
    time.sleep(1)  # Dá tempo pro servidor subir

    # Cria um arquivo falso (com 100 mil linhas) para simular um arquivo pesado
    print("[Remetente] Criando arquivo de teste pesado...")
    with open("teste_envio.txt", "w") as f:
        for i in range(100000):
            f.write(
                f"Linha {i}: Este é um teste de transferência de arquivo em blocos.\n"
            )

    cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    cliente.connect(("127.0.0.1", porta))

    # Chama a função principal de envio
    enviar_arquivo_fisico("teste_envio.txt", cliente)
    cliente.close()


if __name__ == "__main__":
    PORTA_TESTE = 50005

    # Inicia o recebedor em uma thread
    t_servidor = threading.Thread(
        target=servidor_recebedor, args=(PORTA_TESTE,), daemon=True
    )
    t_servidor.start()

    # Inicia o remetente
    cliente_remetente(PORTA_TESTE)

    time.sleep(2)  # Segura a tela para vermos o print final
