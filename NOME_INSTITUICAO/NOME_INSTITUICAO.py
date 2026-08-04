import pandas as pd
import re
import os
from rapidfuzz import fuzz
from rapidfuzz.utils import default_process

def limpar_nome(nome):
    """
    Remove sufixos do tipo ' - 2023', ' -2023', ' 2023' ou ' 2023' no final da string.
    Retorna o nome limpo.
    """
    nome = str(nome).strip()
    # Remove padrões: espaço + hífen + espaço + 4 dígitos no final
    nome = re.sub(r'\s*-\s*\d{4}$', '', nome)
    # Remove padrões: espaço + 4 dígitos no final (caso não tenha hífen)
    nome = re.sub(r'\s*\d{4}$', '', nome)
    return nome.strip()

def agrupar_nomes_similares(caminho_entrada, caminho_saida, limiar=90):
    """
    Lê uma planilha Excel com coluna 'NOME_INSTITUICAO', agrupa nomes similares
    (ignorando sufixos de ano) e gera ID + nome comum padronizado.
    Mantém todas as colunas originais e adiciona as colunas 'ID' e 'SUGERIDO'.
    """
    # 1. Carregar a planilha (primeira linha é cabeçalho)
    df = pd.read_excel(caminho_entrada, header=0)
    
    # Verifica se a coluna existe
    if 'NOME_INSTITUICAO' not in df.columns:
        raise ValueError("A planilha deve ter uma coluna chamada 'NOME_INSTITUICAO'")
    
    nomes_originais = df['NOME_INSTITUICAO'].astype(str).tolist()
    
    # 2. Limpar os nomes (remover sufixos de ano) para comparação
    nomes_limpos = [limpar_nome(n) for n in nomes_originais]
    
    # 3. Agrupar usando os nomes limpos
    grupos = []
    processados = set()
    
    for i, nome_i in enumerate(nomes_limpos):
        if i in processados:
            continue
        grupo_atual = [i]
        processados.add(i)
        
        for j, nome_j in enumerate(nomes_limpos):
            if j in processados:
                continue
            similaridade = fuzz.ratio(nome_i, nome_j, processor=default_process)
            if similaridade >= limiar:
                grupo_atual.append(j)
                processados.add(j)
        
        grupos.append(grupo_atual)
    
    # 4. Atribuir ID e nome comum (baseado nos nomes limpos)
    id_por_indice = [None] * len(nomes_originais)
    sugerido_por_indice = [None] * len(nomes_originais)
    
    for id_grupo, grupo in enumerate(grupos, start=1):
        # Nomes limpos do grupo
        nomes_limpos_grupo = [nomes_limpos[idx] for idx in grupo]
        # Escolhe o mais longo como nome comum
        nome_comum = max(nomes_limpos_grupo, key=len)
        
        for idx in grupo:
            id_por_indice[idx] = id_grupo
            sugerido_por_indice[idx] = nome_comum
    
    # 5. Adicionar as novas colunas ao DataFrame original
    df['ID'] = id_por_indice
    df['SUGERIDO'] = sugerido_por_indice
    
    # 6. Salvar
    df.to_excel(caminho_saida, index=False)
    print(f"Arquivo processado e salvo em: {caminho_saida}")

if __name__ == "__main__":
    # Obtém o diretório onde está o script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    entrada = os.path.join(base_dir, "DE_PARA_INSTITUICAO_LYCEUM.xlsx")
    saida = os.path.join(base_dir, "instituicoes_agrupadas.xlsx")
    
    # Verifica se o arquivo de entrada existe
    if not os.path.isfile(entrada):
        print(f"ERRO: Arquivo de entrada não encontrado: {entrada}")
        print("Certifique-se de que o arquivo está na mesma pasta do script.")
    else:
        agrupar_nomes_similares(
            caminho_entrada=entrada,
            caminho_saida=saida,
            limiar=90
        )