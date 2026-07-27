#!/usr/bin/env python3
"""
sync/sync_ly_turma_docentes.py
Sincronização da tabela LY_TURMA_DOCENTE

- API Lyceum: SOMENTE GET
- Escrita: APENAS banco local
- Estratégia: Full refresh (truncate + insert)
- Filtro fixo: ano = 2026
"""

import sys
import os
import time
import logging
from datetime import datetime
from collections import Counter

# Garante import absoluto a partir da raiz do projeto
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config import config
from core.api_client import get_turma_docente_client
from models.ly_turma_docente import LyTurmaDocenteModel

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync.ly_turma_docente")


# ------------------------------------------------------------------------------
# Sincronização
# ------------------------------------------------------------------------------

def run() -> bool:
    """
    Executa a sincronização completa da tabela LY_TURMA_DOCENTE,
    filtrando apenas registros com ano = 2026.
    """
    logger.info("=" * 70)
    logger.info("INICIANDO SINCRONIZAÇÃO - LY_TURMA_DOCENTE")
    logger.info("Modo: LEITURA (API GET) + ESCRITA LOCAL")
    logger.info("Filtro: ano = 2026")
    logger.info("=" * 70)

    start_time = time.time()

    try:
        # ------------------------------------------------------------------
        # 1. Preparação da tabela local
        # ------------------------------------------------------------------
        logger.info("Preparando tabela local...")
        LyTurmaDocenteModel.create_table()

        resumo_inicial = LyTurmaDocenteModel.get_summary()
        logger.info(
            "Estado inicial | total=%s | turmas=%s | docentes=%s",
            resumo_inicial.get("total_registros", 0),
            resumo_inicial.get("turmas_distintas", 0),
            resumo_inicial.get("docentes_distintos", 0),
        )

        # ------------------------------------------------------------------
        # 2. Leitura da API (SOMENTE GET) – com filtro de ano
        # ------------------------------------------------------------------
        logger.info("Conectando à API Lyceum (GET apenas)")
        logger.info("Base URL: %s", config.LYCEUM_BASE_URL)
        logger.info("Endpoint: /v2/tabela/turma-docente?ano=2026")

        client = get_turma_docente_client()

        # 🔽 ALTERAÇÃO PRINCIPAL: filtro por ano = 2026
        logger.info("Buscando dados com filtro ano=2026 via paginação...")
        registros_api = client.get_turmas_docentes_filtradas(ano=2026)
        # Caso o cliente não tenha esse método, use:
        # registros_api = client.get_paginated("/v2/tabela/turma-docente", params={"ano": 2026})

        if not registros_api:
            logger.warning("API retornou zero registros para o ano 2026")
            return True

        logger.info("Total retornado pela API: %d", len(registros_api))

        # Estatística rápida: verificar se todos têm ano=2026 (diagnóstico)
        anos_presentes = Counter(r.get("ano") for r in registros_api if r.get("ano") is not None)
        logger.info("Distribuição de anos nos dados retornados: %s", anos_presentes)

        # ------------------------------------------------------------------
        # 3. Validação mínima (chave obrigatória)
        # ------------------------------------------------------------------
        registros_validos = []
        registros_invalidos = 0

        for item in registros_api:
            if item.get("chave"):
                registros_validos.append(item)
            else:
                registros_invalidos += 1

        if registros_invalidos:
            logger.warning("Registros descartados (sem chave): %d", registros_invalidos)

        if not registros_validos:
            logger.warning("Nenhum registro válido para inserção")
            return True

        logger.info("Registros válidos: %d", len(registros_validos))

        # ------------------------------------------------------------------
        # 4. Limpeza e carga local
        # ------------------------------------------------------------------
        logger.info("Limpando tabela local...")
        LyTurmaDocenteModel.clear_table()

        logger.info("Inserindo registros no banco local...")
        inseridos = LyTurmaDocenteModel.batch_insert(registros_validos)

        # ------------------------------------------------------------------
        # 5. Resumo final
        # ------------------------------------------------------------------
        tempo_total = time.time() - start_time
        resumo_final = LyTurmaDocenteModel.get_summary()

        logger.info("=" * 70)
        logger.info("SINCRONIZAÇÃO FINALIZADA")
        logger.info("Inseridos: %d", inseridos)
        logger.info("Total final no banco local: %d", resumo_final.get("total_registros", 0))
        logger.info("Turmas distintas: %d", resumo_final.get("turmas_distintas", 0))
        logger.info("Disciplinas distintas: %d", resumo_final.get("disciplinas_distintas", 0))
        logger.info("Docentes distintos: %d", resumo_final.get("docentes_distintos", 0))
        logger.info("Anos presentes no banco: %d", resumo_final.get("anos_distintos", 0))
        logger.info("Tempo total: %.2f s", tempo_total)

        if inseridos != len(registros_validos):
            logger.warning(
                "Carga parcial (%d/%d)",
                inseridos,
                len(registros_validos),
            )
        else:
            logger.info("Carga concluída com sucesso")

        return True

    except Exception:
        logger.exception("Erro durante a sincronização")
        return False


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main() -> int:
    """
    Ponto de entrada do script.
    """
    if not all(
        [
            config.LYCEUM_BASE_URL,
            config.LYCEUM_USERNAME,
            config.LYCEUM_PASSWORD,
        ]
    ):
        logger.error("Configuração da API incompleta (.env)")
        return 1

    sucesso = run()
    return 0 if sucesso else 1


if __name__ == "__main__":
    sys.exit(main())