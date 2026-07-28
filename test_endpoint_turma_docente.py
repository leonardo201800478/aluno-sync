#!/usr/bin/env python3
"""
test_paginas_estabilidade.py
Testa se as páginas 0 a 20 do endpoint turma-docente retornam os mesmos dados
em execuções sucessivas (estabilidade de paginação).
Guarda as chaves de cada página em um arquivo JSON para comparação.
"""

import sys
import os
import json
import hashlib
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.config import config
from core.api_client import get_turma_docente_client
from models.ly_turma_docente import LyTurmaDocenteModel

PAGES_TO_TEST = list(range(0, 21))  # 0 a 20
OUTPUT_FILE = "teste_paginas_estabilidade.json"


def get_chaves_por_pagina():
    """
    Obtém as chaves de todos os registros das páginas 0 a 20.
    Retorna um dicionário com a estrutura:
    {
        "execution_time": "2026-07-28 10:47:25",
        "pages": {
            "0": [chave1, chave2, ...],
            "1": [...],
            ...
        }
    }
    """
    client = get_turma_docente_client()
    resultados = {
        "execution_time": datetime.now().isoformat(),
        "pages": {}
    }

    for page in PAGES_TO_TEST:
        print(f"Lendo página {page}...")
        items = client.get_turmas_docentes_from_page(page, config.API_PAGE_SIZE)
        if not items:
            print(f"  Página {page} vazia ou sem dados.")
            resultados["pages"][str(page)] = []
        else:
            chaves = [item.get('chave') for item in items if item.get('chave') is not None]
            resultados["pages"][str(page)] = chaves
            print(f"  Página {page}: {len(chaves)} chaves (primeira: {chaves[0] if chaves else 'N/A'})")

    return resultados


def comparar_com_anterior(novo_resultado):
    """
    Compara o novo resultado com o arquivo salvo anteriormente.
    Retorna um dicionário com as diferenças.
    """
    if not os.path.exists(OUTPUT_FILE):
        print(f"Arquivo {OUTPUT_FILE} não existe. Esta é a primeira execução.")
        return None

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        anterior = json.load(f)

    print("\nComparando com execução anterior (arquivo salvo)...")
    diferencas = {
        "paginas_com_diferenca": [],
        "detalhes": {}
    }

    for page in PAGES_TO_TEST:
        page_str = str(page)
        chaves_novas = set(novo_resultado["pages"].get(page_str, []))
        chaves_antigas = set(anterior["pages"].get(page_str, []))

        if chaves_novas != chaves_antigas:
            diferencas["paginas_com_diferenca"].append(page_str)
            # Mostrar diferenças específicas
            added = chaves_novas - chaves_antigas
            removed = chaves_antigas - chaves_novas
            detalhe = {
                "tamanho_atual": len(chaves_novas),
                "tamanho_anterior": len(chaves_antigas),
                "chaves_adicionadas": list(added),
                "chaves_removidas": list(removed)
            }
            diferencas["detalhes"][page_str] = detalhe
        else:
            print(f"✅ Página {page}: OK (mesmas chaves)")

    if not diferencas["paginas_com_diferenca"]:
        print("\n✅ Todas as páginas comparadas são IDÊNTICAS à execução anterior.")
    else:
        print(f"\n⚠️  Diferenças encontradas nas páginas: {diferencas['paginas_com_diferenca']}")
        for page, detalhe in diferencas["detalhes"].items():
            print(f"\nPágina {page}:")
            print(f"  Tamanho atual: {detalhe['tamanho_atual']}")
            print(f"  Tamanho anterior: {detalhe['tamanho_anterior']}")
            if detalhe['chaves_adicionadas']:
                print(f"  Chaves adicionadas: {detalhe['chaves_adicionadas'][:10]}...")  # mostra até 10
            if detalhe['chaves_removidas']:
                print(f"  Chaves removidas: {detalhe['chaves_removidas'][:10]}...")

    return diferencas


def salvar_resultado(resultado):
    """Salva o resultado atual no arquivo JSON."""
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)
    print(f"\nResultado salvo em {OUTPUT_FILE}")


def main():
    print("=" * 60)
    print("TESTE DE ESTABILIDADE DE PAGINAÇÃO - TURMA-DOCENTE")
    print(f"Páginas testadas: {PAGES_TO_TEST[0]} a {PAGES_TO_TEST[-1]}")
    print("=" * 60)

    # Obter dados atuais
    print("\n🔍 Buscando dados atuais...")
    novo_resultado = get_chaves_por_pagina()

    # Comparar com anterior
    print("\n🔍 Comparando com execução anterior...")
    diff = comparar_com_anterior(novo_resultado)

    # Perguntar se deseja salvar como referência para próxima
    resposta = input("\nDeseja salvar este resultado como referência para a próxima execução? (s/N): ")
    if resposta.lower() == 's':
        salvar_resultado(novo_resultado)
    else:
        print("Resultado não salvo.")

    print("\nFim do teste.")


if __name__ == "__main__":
    main()