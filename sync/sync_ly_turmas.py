#!/usr/bin/env python3
"""
sync/sync_ly_turmas.py
Sincronização da tabela LY_TURMA
- APENAS método GET na API Lyceum
- Sincronização completa (full refresh)
- Filtro fixo: ano = 2026
- Sem chave primária fixa (similar a LY_CURRICULO e LY_DISCIPLINA)
"""

import sys
import os
import time
import logging
from datetime import datetime
from collections import Counter

# Adiciona diretório raiz ao PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Imports internos
from core.config import config
from core.api_client import TurmaAPIClient
from models.ly_turma import LyTurmaModel

# -----------------------------------------------------------------------------
# LOGGING
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync_ly_turma")


# -----------------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE SINCRONIZAÇÃO
# -----------------------------------------------------------------------------
def run() -> bool:
    logger.info("=" * 80)
    logger.info("INICIANDO SINCRONIZAÇÃO - LY_TURMA")
    logger.info("Modo: FULL REFRESH | API: GET ONLY")
    logger.info("Filtro: ano = 2026")
    logger.info("Início: %s", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    logger.info("=" * 80)

    start_time = time.time()

    try:
        # ---------------------------------------------------------------------
        # 1. Criar/verificar tabela local
        # ---------------------------------------------------------------------
        logger.info("[1/4] Criando/verificando tabela LY_TURMA (LOCAL)")
        LyTurmaModel.create_table()

        resumo_inicial = LyTurmaModel.get_summary()
        logger.info(
            "Resumo inicial | Total: %s | Ativas: %s | Anos: %s",
            resumo_inicial.get("total_turmas", 0),
            resumo_inicial.get("turmas_ativas", 0),
            resumo_inicial.get("anos_distintos", 0),
        )

        # ---------------------------------------------------------------------
        # 2. Buscar dados da API (APENAS GET) – apenas ano=2026
        # ---------------------------------------------------------------------
        logger.info("[2/4] Buscando dados da API Lyceum (GET) - ano=2026")
        logger.info("Endpoint: /v2/tabela/turmas?ano=2026")

        client = TurmaAPIClient()
        turmas = client.get_turmas_filtradas(ano=2026)  # 🔒 GET com filtro

        if not turmas:
            logger.warning("Nenhum registro retornado pela API para o ano 2026")
            return True  # execução válida, mas sem dados

        logger.info("Total retornado pela API: %d", len(turmas))

        # ---------------------------------------------------------------------
        # 3. Validação mínima dos registros
        # Campos obrigatórios: ano, semestre, turma, disciplina
        # ---------------------------------------------------------------------
        turmas_validas = []
        turmas_invalidas = 0

        for t in turmas:
            if all([t.get("ano"), t.get("semestre"), t.get("turma"), t.get("disciplina")]):
                turmas_validas.append(t)
            else:
                turmas_invalidas += 1

        logger.info(
            "Registros válidos: %d | Registros inválidos: %d",
            len(turmas_validas),
            turmas_invalidas,
        )

        if not turmas_validas:
            logger.warning("Nenhuma turma válida para processamento")
            return True

        # Estatísticas rápidas (diagnóstico)
        ativos = sum(1 for t in turmas_validas if t.get("sit_turma") == "A")
        anos = Counter(t.get("ano") for t in turmas_validas if t.get("ano"))

        logger.info("Turmas ativas: %d | Inativas: %d", ativos, len(turmas_validas) - ativos)
        logger.info("Distribuição por ano (top 5): %s", anos.most_common(5))

        # ---------------------------------------------------------------------
        # 4. Limpeza da tabela local
        # ---------------------------------------------------------------------
        logger.info("[3/4] Limpando tabela LY_TURMA (LOCAL)")
        LyTurmaModel.clear_table()

        # ---------------------------------------------------------------------
        # 5. Inserção no banco local
        # ---------------------------------------------------------------------
        logger.info("[4/4] Inserindo registros no banco LOCAL")
        total_inseridos = LyTurmaModel.batch_insert(turmas_validas)

        # ---------------------------------------------------------------------
        # 6. Resumo final
        # ---------------------------------------------------------------------
        tempo_total = time.time() - start_time
        resumo_final = LyTurmaModel.get_summary()

        logger.info("=" * 80)
        logger.info("RESUMO DA SINCRONIZAÇÃO - LY_TURMA")
        logger.info("API (GET): %d registros (ano=2026)", len(turmas))
        logger.info("Processados: %d", len(turmas_validas))
        logger.info("Inseridos no banco local: %d", total_inseridos)

        logger.info(
            "Banco | Antes: %s | Depois: %s",
            resumo_inicial.get("total_turmas", 0),
            resumo_final.get("total_turmas", 0),
        )

        logger.info(
            "Ativas: %s | Anos: %s | Semestres: %s | Disciplinas: %s",
            resumo_final.get("turmas_ativas", 0),
            resumo_final.get("anos_distintos", 0),
            resumo_final.get("semestres_distintos", 0),
            resumo_final.get("disciplinas_distintas", 0),
        )

        logger.info("Tempo total: %.2f s", tempo_total)
        logger.info("Taxa: %.2f turmas/s", len(turmas_validas) / tempo_total if tempo_total > 0 else 0)

        logger.info("SINCRONIZAÇÃO FINALIZADA COM SUCESSO")
        logger.info("=" * 80)

        return True

    except Exception as exc:
        logger.exception("Erro durante a sincronização: %s", exc)
        return False


# -----------------------------------------------------------------------------
# ENTRYPOINT
# -----------------------------------------------------------------------------
def main() -> int:
    if not all([config.LYCEUM_BASE_URL, config.LYCEUM_USERNAME, config.LYCEUM_PASSWORD]):
        logger.error("Configurações da API incompletas (.env)")
        return 1

    return 0 if run() else 1


if __name__ == "__main__":
    sys.exit(main())