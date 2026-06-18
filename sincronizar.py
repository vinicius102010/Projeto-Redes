def comparar_indices(meu_indice, indice_colega):
    """comparar o estado da pasta local com a pasta do colega"""
    arquivos_para_baixar = []
    for caminho_arquivo, info_colega in indice_colega.items():
        if caminho_arquivo not in meu_indice:
            print(f"arquivo novo encontrado na rede: {caminho_arquivo}")
            arquivos_para_baixar.append(caminho_arquivo)

        else:
            minha_info = meu_indice[caminho_arquivo]
            if minha_info["hash"] != info_colega["hash"]:
                print(f"arquivo modificado encontrado na rede: {caminho_arquivo}")
                arquivos_para_baixar.append(caminho_arquivo)
            else:
                print(f"arquivo igual encontrado na rede: {caminho_arquivo}")
    return arquivos_para_baixar
