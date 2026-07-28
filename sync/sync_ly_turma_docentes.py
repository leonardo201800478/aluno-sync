#!/usr/bin/env python3
"""
sync/sync_ly_turma_docentes.py
Sincronização incremental com checkpoint baseado em páginas.

Uso:
  python sync_ly_turma_docentes.py                             # processa até o fim da API
  python sync_ly_turma_docentes.py --pages 10                  # processa apenas 10 páginas
  python sync_ly_turma_docentes.py --checkpoint-pages 50       # salva checkpoint a cada 50 páginas
  python sync_ly_turma_docentes.py --reset                     # reseta o checkpoint e limpa a tabela
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.config import config
from core.api_client import get_turma_docente_client
from models.ly_turma_docente import LyTurmaDocenteModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync.ly_turma_docente")

# Constantes
PAGE_SIZE = config.API_PAGE_SIZE              # geralmente 100
BATCH_SIZE = 1000                             # insere a cada 1000 registros
DEFAULT_DELAY = config.API_DELAY_BETWEEN_REQUESTS


def run(max_pages: int = None, reset_checkpoint: bool = False, checkpoint_pages: int = 100) -> bool:
    """
    Executa a sincronização.

    Args:
        max_pages: Número máximo de páginas a processar. None = até o fim.
        reset_checkpoint: Se True, reinicia da página 0 e limpa a tabela.
        checkpoint_pages: Frequência (em páginas) para salvar o checkpoint.
    """
    logger.info("=" * 70)
    logger.info("INICIANDO SINCRONIZAÇÃO - LY_TURMA_DOCENTE (INCREMENTAL)")
    if max_pages:
        logger.info(f"Modo: processar até {max_pages} páginas")
    else:
        logger.info("Modo: processar até o fim da API")
    logger.info(f"Checkpoint salvo a cada {checkpoint_pages} páginas")
    logger.info("Filtro: ano = 2026")
    logger.info("=" * 70)

    start_time = time.time()
    try:
        # 1. Criar tabelas
        LyTurmaDocenteModel.create_table()
        LyTurmaDocenteModel._create_checkpoint_table()

        # 2. Reset opcional
        if reset_checkpoint:
            logger.warning("Reset solicitado: limpando tabela e checkpoint.")
            LyTurmaDocenteModel.clear_table()
            LyTurmaDocenteModel.update_checkpoint(0, 0)
            logger.info("Reset concluído.")

        # 3. Obter checkpoint atual
        checkpoint = LyTurmaDocenteModel.get_checkpoint()
        current_page = checkpoint['last_page']
        last_chave = checkpoint['last_chave']
        logger.info("Checkpoint atual: página %s, última chave %s", current_page, last_chave)

        # 4. Preparar cliente e variáveis de controle
        client = get_turma_docente_client()
        page = current_page
        total_inseridos = 0
        buffer = []
        pages_processed = 0
        pages_since_last_checkpoint = 0

        while True:
            # Verificar se atingimos o limite de páginas
            if max_pages is not None and pages_processed >= max_pages:
                logger.info("Limite de páginas (%d) atingido. Encerrando.", max_pages)
                break

            logger.info("Lendo página %d...", page)
            items = client.get_turmas_docentes_from_page(page, PAGE_SIZE)

            # Se não houver dados, fim da API
            if not items:
                logger.info("Página %d vazia – fim da API.", page)
                # Inserir buffer restante e salvar checkpoint final
                if buffer:
                    inseridos = LyTurmaDocenteModel.batch_insert(buffer)
                    total_inseridos += inseridos
                # Atualiza checkpoint com a página atual (mesmo que vazia, indica que avançamos)
                LyTurmaDocenteModel.update_checkpoint(page, 0)
                logger.info("Checkpoint final salvo (página %d)", page)
                break

            # Filtrar apenas registros com ano=2026
            items_2026 = [item for item in items if item.get('ano') == 2026]
            logger.info("Página %d: %d registros, %d são de 2026", page, len(items), len(items_2026))

            # Adicionar ao buffer
            buffer.extend(items_2026)

            # Inserir se o buffer atingiu o tamanho do lote
            if len(buffer) >= BATCH_SIZE:
                inseridos = LyTurmaDocenteModel.batch_insert(buffer)
                total_inseridos += inseridos
                buffer = []
                logger.info("Buffer inserido (total %d registros)", total_inseridos)

            # Incrementar contador de páginas desde o último checkpoint
            pages_since_last_checkpoint += 1

            # Salvar checkpoint a cada 'checkpoint_pages' páginas
            if pages_since_last_checkpoint >= checkpoint_pages:
                # Forçar inserção do buffer restante antes de salvar checkpoint
                if buffer:
                    inseridos = LyTurmaDocenteModel.batch_insert(buffer)
                    total_inseridos += inseridos
                    buffer = []
                # Obter a maior chave da página atual (ou última chave conhecida)
                # Usamos a chave do último item da página (assumindo que a API ordena por chave crescente)
                last_key = items[-1].get('chave', 0) if items else 0
                LyTurmaDocenteModel.update_checkpoint(page, last_key)
                pages_since_last_checkpoint = 0
                logger.info("Checkpoint salvo na página %d (chave %d)", page, last_key)

            # Avançar para a próxima página
            pages_processed += 1
            page += 1
            time.sleep(DEFAULT_DELAY)

        # 5. Resumo final
        tempo_total = time.time() - start_time
        resumo = LyTurmaDocenteModel.get_summary()
        logger.info("=" * 70)
        logger.info("SINCRONIZAÇÃO FINALIZADA")
        logger.info("Total inseridos nesta execução: %d", total_inseridos)
        logger.info("Total no banco: %d", resumo.get('total_registros', 0))
        logger.info("Última página processada: %d", page - 1)
        logger.info("Tempo total: %.2f s", tempo_total)
        return True

    except Exception as e:
        logger.exception("Erro durante a sincronização: %s", e)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza LY_TURMA_DOCENTE de forma incremental.")
    parser.add_argument("--pages", type=int, default=None,
                        help="Número máximo de páginas a processar (default: todas)")
    parser.add_argument("--checkpoint-pages", type=int, default=100,
                        help="Frequência de checkpoint em páginas (default: 100)")
    parser.add_argument("--reset", action="store_true",
                        help="Reseta o checkpoint e limpa a tabela local")
    args = parser.parse_args()

    if not all([config.LYCEUM_BASE_URL, config.LYCEUM_USERNAME, config.LYCEUM_PASSWORD]):
        logger.error("Configuração da API incompleta")
        return 1

    success = run(
        max_pages=args.pages,
        reset_checkpoint=args.reset,
        checkpoint_pages=args.checkpoint_pages
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())