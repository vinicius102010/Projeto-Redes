import hashlib
import json
import os
import time

PASTA_COMPARTILHADA = "./meu_drive"  # a apsta que vais er monitorada e criada dentro da pasta atual (se nao tiver)


def gerar_hash_arquivo(caminho_arquivo):
    """vai ler o arquivo em blocos para gerar um hash MD5
    vai ler em blocos de 4096 bytes pra nao estourar a ram com arquivos grandes"""
    hash_md5 = hashlib.md5()
    try:
        with open(caminho_arquivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"Erro ao ler arquivo {caminho_arquivo}: {e}")


def scan_pasta():
    """vai varrer a pasta e retornar um dicionario com o estado dos arquivos"""
    estado_atual = {}
    # criar a paste se ela nao existir
    if not os.path.exists(PASTA_COMPARTILHADA):
        os.makedirs(PASTA_COMPARTILHADA)
    # varre a pasta, pega os arquivos, subpastas e gera os hashes
    for raiz, subpastas, arquivos in os.walk(PASTA_COMPARTILHADA):
        for arquivo in arquivos:
            caminho_completo = os.path.join(raiz, arquivo)
            # pegar o caminho relativo relacionado a pasta em questao porque o caminho completo pode variar de maquina pra maquina
            caminho_relativo = os.path.relpath(caminho_completo, PASTA_COMPARTILHADA)
            hash_arquivo = gerar_hash_arquivo(caminho_completo)
            if hash_arquivo:
                estado_atual[caminho_relativo] = {
                    "hash": hash_arquivo,
                    "tamanho": os.path.getsize(caminho_completo),
                    "modificado_em": os.path.getmtime(caminho_completo),
                }
    return estado_atual


# teste rapido
if __name__ == "__main__":
    print("Monitorando a pasta compartilhada...")
    while True:
        # ve como a pasta ta quando incia o programa
        index_arquivos = scan_pasta()
        print("Estado inicial da pasta:")
        print(json.dumps(index_arquivos, indent=4))
        # depois fica escaneando a pasta a cada 10 segundos pra ver se tem
        time.sleep(5)
