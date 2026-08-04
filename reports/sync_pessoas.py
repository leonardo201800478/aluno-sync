#!/usr/bin/env python3
"""
reports/sync_pessoas.py

Ponto de entrada standalone para sincronização manual de pessoas pendentes.

Uso:
    python reports/sync_pessoas.py
"""

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.logger import logger
from core.database import get_db_connection
from core.config import config
from models.ly_pessoa import LyPessoaModel
from sync.sync_ly_pessoa_by_id import (
    _buscar_pessoas_pendentes,
    buscar_e_salvar_pessoa_por_id,
)

LOTE_TAMANHO = 100  # Número de IDs processados por lote


def verificar_e_sincronizar_pessoas() -> None:
    """
    Verifica pessoas em LY_ALUNO não existentes em LY_PESSOA e sincroniza,
    processando em lotes de 100 com commit parcial.
    """
    logger.info("Verificando estrutura da tabela LY_PESSOA...")
    if not LyPessoaModel._table_exists():
        logger.info("Tabela LY_PESSOA não existe. Criando...")
        if not LyPessoaModel.create_table():
            logger.error("Falha ao criar a tabela LY_PESSOA. Abortando.")
            return
        logger.info("Tabela LY_PESSOA criada com sucesso.")

    logger.info("Verificando pessoas faltantes na tabela LY_PESSOA...")
    try:
        faltantes = _buscar_pessoas_pendentes()
    except Exception as e:
        logger.error(f"Erro ao consultar pessoas pendentes: {e}")
        return

    if not faltantes:
        logger.info("Nenhuma pessoa faltante encontrada.")
        return

    total = len(faltantes)
    logger.info(f"Encontradas {total} pessoas faltantes. Iniciando sincronização em lotes de {LOTE_TAMANHO}...")

    sucessos, falhas = 0, 0

    for i in range(0, total, LOTE_TAMANHO):
        lote = faltantes[i:i + LOTE_TAMANHO]
        logger.info(f"Processando lote {i//LOTE_TAMANHO + 1} (IDs {i+1} a {min(i+LOTE_TAMANHO, total)})")

        for pessoa_id in lote:
            logger.info(f"Sincronizando pessoa ID: {pessoa_id}")
            resultado = buscar_e_salvar_pessoa_por_id(pessoa_id, buscar_alunos=False)
            if resultado:
                sucessos += 1
            else:
                falhas += 1
                logger.error(f"Falha ao sincronizar pessoa {pessoa_id}")

            # Pequeno delay entre requisições (respeita config)
            time.sleep(config.API_DELAY_BETWEEN_REQUESTS)

        # Commit explícito após cada lote
        try:
            with get_db_connection(database_name='lyceum') as conn:
                conn.commit()
            logger.info(f"Lote {i//LOTE_TAMANHO + 1} concluído. Sucessos: {sucessos}, Falhas: {falhas}")
        except Exception as e:
            logger.error(f"Erro ao commitar lote: {e}")

    logger.info(f"Sincronização concluída: {sucessos}/{total} com sucesso | {falhas} falhas.")


if __name__ == "__main__":
    verificar_e_sincronizar_pessoas()