#!/usr/bin/env python3
"""
sync/sync_ly_pessoas.py

SINCRONIZAÇÃO LY_PESSOA via endpoint específico por ID,
com upsert incremental a cada 100 pessoas coletadas.

Características:
- Busca IDs de alunos em LY_ALUNO que não estão em LY_PESSOA
- Para cada ID, chama /v2/pessoas/idPessoa/{id}/obterPessoa
- Coleta em lotes de 100 e faz UPSERT imediato
- Processamento em lote de upsert de 1000 (ajustável)
- Logs detalhados de progresso
- Resumo final da execução
"""

import os
import sys
import time
import logging
from typing import List, Dict, Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.api_client import PessoaAPIClient
from core.database import fetch_all
from core.config import config
from models.ly_pessoa import LyPessoaModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Tamanho do lote de coleta (quantas pessoas buscar antes de fazer UPSERT)
COLETAR_LOTE = 100
# Tamanho do lote de upsert (quantas enviar por vez no MERGE)
UPSERT_BATCH = 1000


def obter_ids_pendentes() -> List[int]:
    """
    Retorna lista de IDs (pessoa) de LY_ALUNO que NÃO estão em LY_PESSOA.
    """
    query = """
        SELECT DISTINCT a.pessoa
        FROM lyceum.dbo.LY_ALUNO a
        LEFT JOIN lyceum.dbo.LY_PESSOA p ON a.pessoa = p.pessoa
        WHERE p.pessoa IS NULL
    """
    rows = fetch_all(query, database_name="lyceum")
    return [row[0] for row in rows] if rows else []


def sincronizar_pessoas() -> Dict[str, Any]:
    logger.info("=" * 80)
    logger.info("INICIANDO SINCRONIZAÇÃO LY_PESSOA (via endpoint específico)")
    logger.info(f"Coleta em lotes de: {COLETAR_LOTE}")
    logger.info(f"UPSERT em lotes de: {UPSERT_BATCH}")
    logger.info("=" * 80)

    inicio_execucao = time.time()

    try:
        # ------------------------------------------------------------------
        # Garantir existência da tabela
        # ------------------------------------------------------------------
        logger.info("Verificando estrutura da tabela...")
        LyPessoaModel.create_table()

        resumo_inicial = LyPessoaModel.get_summary()
        total_inicial = resumo_inicial.get("total_pessoas", 0)
        logger.info(f"Total atual na tabela: {total_inicial:,}")

        # ------------------------------------------------------------------
        # Buscar IDs pendentes no banco
        # ------------------------------------------------------------------
        logger.info("Consultando IDs de alunos pendentes na tabela LY_PESSOA...")
        ids_pendentes = obter_ids_pendentes()

        if not ids_pendentes:
            logger.info("Nenhuma pessoa pendente para sincronizar.")
            return {
                "success": True,
                "total_api": 0,
                "validos": 0,
                "processados": 0,
                "tempo_total": time.time() - inicio_execucao,
            }

        total_ids = len(ids_pendentes)
        logger.info(f"Encontrados {total_ids:,} IDs pendentes.")

        # ------------------------------------------------------------------
        # Loop principal: coleta em lotes e upsert incremental
        # ------------------------------------------------------------------
        client = PessoaAPIClient()
        total_obtidos = 0
        total_validos = 0
        total_processados = 0
        erros_api = 0
        lote_coleta = []  # buffer de pessoas coletadas

        inicio_api_geral = time.time()

        for idx, pid in enumerate(ids_pendentes, 1):
            # Busca a pessoa
            logger.info(f"Buscando pessoa {pid} ({idx}/{total_ids})...")
            pessoa = client.get_pessoa_detalhada(pid)
            if pessoa:
                lote_coleta.append(pessoa)
                total_obtidos += 1
            else:
                erros_api += 1
                logger.warning(f"Falha ao obter dados para ID {pid}")

            # Respeita o delay da API
            time.sleep(config.API_DELAY_BETWEEN_REQUESTS)

            # Se atingiu o tamanho do lote de coleta OU é o último ID, processa o lote
            if len(lote_coleta) >= COLETAR_LOTE or idx == total_ids:
                if lote_coleta:
                    # Validar registros do lote
                    validos = []
                    invalidos = 0
                    for p in lote_coleta:
                        if isinstance(p, dict) and p.get("pessoa") is not None:
                            validos.append(p)
                        else:
                            invalidos += 1
                    total_validos += len(validos)
                    if invalidos:
                        logger.warning(f"Registros inválidos neste lote: {invalidos}")

                    # Upsert do lote válido
                    if validos:
                        logger.info(f"Upsert de {len(validos)} pessoas (lote de coleta)...")
                        processados = LyPessoaModel.batch_upsert(validos, batch_size=UPSERT_BATCH)
                        total_processados += processados
                        logger.info(f"Lote processado: {processados} registros inseridos/atualizados.")
                    else:
                        logger.warning("Nenhum registro válido neste lote para upsert.")

                    # Limpa o buffer para o próximo lote
                    lote_coleta = []

        tempo_api_geral = time.time() - inicio_api_geral

        # ------------------------------------------------------------------
        # Resumo final
        # ------------------------------------------------------------------
        resumo_final = LyPessoaModel.get_summary()
        total_final = resumo_final.get("total_pessoas", 0)
        tempo_total = time.time() - inicio_execucao

        logger.info("=" * 80)
        logger.info("RESUMO DA SINCRONIZAÇÃO")
        logger.info("=" * 80)
        logger.info(f"Total de IDs pendentes: {total_ids:,}")
        logger.info(f"Registros obtidos da API: {total_obtidos:,}")
        logger.info(f"Erros na API: {erros_api:,}")
        logger.info(f"Registros válidos: {total_validos:,}")
        logger.info(f"Registros processados (UPSERT): {total_processados:,}")
        logger.info(f"Total antes: {total_inicial:,}")
        logger.info(f"Total depois: {total_final:,}")
        logger.info(f"Tempo total de API (incluindo delays): {tempo_api_geral:.2f}s")
        logger.info(f"Tempo total de execução: {tempo_total:.2f}s")
        ultima_atualizacao = resumo_final.get("ultima_atualizacao")
        if ultima_atualizacao:
            logger.info(f"Última atualização: {ultima_atualizacao}")
        logger.info("=" * 80)

        return {
            "success": True,
            "total_ids": total_ids,
            "total_obtidos": total_obtidos,
            "validos": total_validos,
            "processados": total_processados,
            "erros_api": erros_api,
            "tempo_api": tempo_api_geral,
            "tempo_total": tempo_total,
        }

    except Exception as e:
        logger.exception(f"Erro durante sincronização: {e}")
        return {
            "success": False,
            "erro": str(e),
        }


def run() -> Dict[str, Any]:
    return sincronizar_pessoas()


if __name__ == "__main__":
    resultado = run()
    sys.exit(0 if resultado.get("success") else 1)