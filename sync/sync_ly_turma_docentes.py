
#!/usr/bin/env python3
"""
sync/sync_ly_turma_docentes.py

Sincronização incremental de LY_TURMA_DOCENTE.

Regras
------

- API somente GET.
- Filtro ano = 2026.
- NÃO limpa LY_TURMA_DOCENTE.
- INSERT para registros novos.
- UPDATE para registros existentes com alteração.
- Registros existentes sem alteração não são modificados.
- Checkpoint representa a última página processada com sucesso.
- Página sem registros de 2026 também avança checkpoint.
- Página somente com duplicados também avança checkpoint.
- Página somente com UPDATE também avança checkpoint.
- Página somente com INSERT também avança checkpoint.
- Erro em INSERT/UPDATE impede avanço do checkpoint.
- Próxima execução retorna uma leva de páginas para trás.
"""

import argparse
import logging
import os
import sys
import time


# ============================================================================
# PATH
# ============================================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(
        0,
        PROJECT_ROOT,
    )


# ============================================================================
# IMPORTS
# ============================================================================

from core.api_client import (
    get_turma_docente_client,
)

from core.config import config

from models.ly_turma_docente import (
    LyTurmaDocenteModel,
)


# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(
    "sync.ly_turma_docente"
)


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

ANO = 2026

PAGE_SIZE = config.API_PAGE_SIZE

DEFAULT_DELAY = (
    config.API_DELAY_BETWEEN_REQUESTS
)

DEFAULT_CHECKPOINT_PAGES = 100


# ============================================================================
# RETOMADA
# ============================================================================

def get_resume_page(
    last_written_page: int,
    checkpoint_pages: int,
) -> int:
    """
    Calcula a página inicial da próxima execução.

    A sincronização retorna uma quantidade de páginas para trás,
    permitindo reprocessamento seguro.

    Exemplo:

        última página = 300
        leva = 100

        página inicial = 201

    O reprocessamento é seguro porque o model executa:

        INSERT
        UPDATE
        ou nenhuma alteração.
    """

    if last_written_page <= 0:

        return 0

    return max(
        0,
        last_written_page - checkpoint_pages + 1,
    )


# ============================================================================
# RUN
# ============================================================================

def run(
    max_pages: int = None,
    reset_checkpoint: bool = False,
    checkpoint_pages: int = DEFAULT_CHECKPOINT_PAGES,
) -> bool:
    """
    Executa a sincronização incremental.

    Parameters
    ----------
    max_pages:
        Limita a quantidade de páginas processadas nesta execução.

    reset_checkpoint:
        Reseta o checkpoint antes de iniciar.

    checkpoint_pages:
        Quantidade de páginas utilizada para o recuo da retomada.

    Returns
    -------
    bool
        True quando a sincronização termina normalmente.
    """

    start_time = time.time()

    logger.info("=" * 90)
    logger.info(
        "INICIANDO SINCRONIZAÇÃO - LY_TURMA_DOCENTE"
    )
    logger.info(
        "Modo: INSERT + UPDATE PROGRESSIVO"
    )
    logger.info(
        "Filtro: ano = %d",
        ANO,
    )
    logger.info(
        "Checkpoint: páginas processadas com sucesso"
    )
    logger.info(
        "Leva: %d páginas",
        checkpoint_pages,
    )
    logger.info(
        "Tabela será limpa? NÃO"
    )
    logger.info("=" * 90)

    try:

        # ====================================================================
        # TABELA PRINCIPAL
        # ====================================================================

        if not LyTurmaDocenteModel.create_table():

            logger.error(
                "Falha ao preparar LY_TURMA_DOCENTE."
            )

            return False

        # ====================================================================
        # CHECKPOINT
        # ====================================================================

        if not LyTurmaDocenteModel._create_checkpoint_table():

            logger.error(
                "Falha ao preparar tabela de checkpoint."
            )

            return False

        # ====================================================================
        # RESET
        # ====================================================================

        if reset_checkpoint:

            logger.warning(
                "RESET solicitado."
            )

            logger.warning(
                "Somente o checkpoint será resetado."
            )

            if not LyTurmaDocenteModel.reset_checkpoint():

                return False

        # ====================================================================
        # LÊ CHECKPOINT
        # ====================================================================

        checkpoint = (
            LyTurmaDocenteModel.get_checkpoint()
        )

        last_written_page = checkpoint[
            "last_written_page"
        ]

        last_written_chave = checkpoint[
            "last_written_chave"
        ]

        page = get_resume_page(
            last_written_page,
            checkpoint_pages,
        )

        logger.info(
            "Última página processada: %d",
            last_written_page,
        )

        logger.info(
            "Última chave registrada: %s",
            last_written_chave,
        )

        logger.info(
            "Página de retomada: %d",
            page,
        )

        # ====================================================================
        # CLIENTE
        # ====================================================================

        client = get_turma_docente_client()

        # ====================================================================
        # CONTADORES
        # ====================================================================

        total_api = 0
        total_2026 = 0

        total_inseridos = 0
        total_atualizados = 0
        total_duplicados = 0
        total_invalidos = 0

        pages_processed = 0

        # ====================================================================
        # LOOP PRINCIPAL
        # ====================================================================

        while True:

            # ----------------------------------------------------------------
            # Limite da execução
            # ----------------------------------------------------------------

            if (
                max_pages is not None
                and pages_processed >= max_pages
            ):

                logger.info(
                    "Limite de %d páginas atingido.",
                    max_pages,
                )

                break

            # ----------------------------------------------------------------
            # API
            # ----------------------------------------------------------------

            logger.info(
                "Lendo página %d...",
                page,
            )

            items = (
                client.get_turmas_docentes_from_page(
                    page,
                    PAGE_SIZE,
                )
            )

            # ----------------------------------------------------------------
            # FIM DA API
            # ----------------------------------------------------------------

            if not items:

                logger.info(
                    "Página %d vazia. Fim da API.",
                    page,
                )

                break

            total_api += len(items)

            # =================================================================
            # FILTRO DO ANO
            # =================================================================

            items_2026 = []

            for item in items:

                try:

                    item_ano = int(
                        item.get("ano")
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    item_ano = None

                if item_ano == ANO:

                    items_2026.append(
                        item
                    )

            total_2026 += len(
                items_2026
            )

            logger.info(
                "Página %d | API=%d | ano=%d=%d",
                page,
                len(items),
                ANO,
                len(items_2026),
            )

            # =================================================================
            # INSERT / UPDATE
            # =================================================================

            result = (
                LyTurmaDocenteModel.batch_insert(
                    items_2026
                )
            )

            inseridos = result[
                "inseridos"
            ]

            atualizados = result[
                "atualizados"
            ]

            duplicados = result[
                "duplicados"
            ]

            invalidos = result[
                "invalidos"
            ]

            ultima_chave = result[
                "ultima_chave_inserida"
            ]

            # -----------------------------------------------------------------
            # Acumula estatísticas
            # -----------------------------------------------------------------

            total_inseridos += inseridos
            total_atualizados += atualizados
            total_duplicados += duplicados
            total_invalidos += invalidos

            # =================================================================
            # CHECKPOINT
            # =================================================================
            #
            # CHEGAMOS AQUI SOMENTE SE:
            #
            #     batch_insert() terminou normalmente
            #
            # Portanto:
            #
            #     INSERT/UPDATE -> COMMIT OK
            #
            # O checkpoint deve avançar mesmo quando:
            #
            #     inseridos = 0
            #     atualizados = 0
            #
            # Isso inclui páginas:
            #
            #     - sem registros de 2026;
            #     - somente duplicados;
            #     - somente inválidos.
            # =================================================================

            checkpoint_chave = ultima_chave

            if checkpoint_chave <= 0:

                # -------------------------------------------------------------
                # Não houve INSERT nesta página.
                #
                # Mantemos a última chave conhecida.
                # -------------------------------------------------------------

                checkpoint_chave = (
                    last_written_chave
                )

            if not LyTurmaDocenteModel.update_checkpoint(
                last_written_page=page,
                last_written_chave=checkpoint_chave,
            ):

                raise RuntimeError(
                    "Falha ao atualizar checkpoint "
                    f"da página {page}."
                )

            # -----------------------------------------------------------------
            # Atualiza estado local
            # -----------------------------------------------------------------

            last_written_page = page
            last_written_chave = checkpoint_chave

            # -----------------------------------------------------------------
            # Log do resultado
            # -----------------------------------------------------------------

            if inseridos > 0:

                logger.info(
                    "CHECKPOINT AVANÇADO | "
                    "página=%d | chave=%s | "
                    "INSERTs=%d | UPDATEs=%d | "
                    "Sem alteração=%d",
                    page,
                    checkpoint_chave,
                    inseridos,
                    atualizados,
                    duplicados,
                )

            elif atualizados > 0:

                logger.info(
                    "CHECKPOINT AVANÇADO | "
                    "página=%d | chave=%s | "
                    "INSERTs=0 | UPDATEs=%d | "
                    "Sem alteração=%d",
                    page,
                    checkpoint_chave,
                    atualizados,
                    duplicados,
                )

            else:

                logger.info(
                    "CHECKPOINT AVANÇADO SEM ALTERAÇÃO | "
                    "página=%d | chave=%s | "
                    "Duplicados=%d | Inválidos=%d",
                    page,
                    checkpoint_chave,
                    duplicados,
                    invalidos,
                )

            # -----------------------------------------------------------------
            # Próxima página
            # -----------------------------------------------------------------

            pages_processed += 1

            page += 1

            # -----------------------------------------------------------------
            # Delay da API
            # -----------------------------------------------------------------

            if DEFAULT_DELAY > 0:

                time.sleep(
                    DEFAULT_DELAY
                )

        # ====================================================================
        # RESUMO
        # ====================================================================

        summary = (
            LyTurmaDocenteModel.get_summary()
        )

        elapsed = (
            time.time() - start_time
        )

        final_checkpoint = (
            LyTurmaDocenteModel.get_checkpoint()
        )

        logger.info("=" * 90)
        logger.info(
            "RESUMO - LY_TURMA_DOCENTE"
        )
        logger.info(
            "Páginas processadas: %d",
            pages_processed,
        )
        logger.info(
            "Registros API: %d",
            total_api,
        )
        logger.info(
            "Registros ano %d: %d",
            ANO,
            total_2026,
        )
        logger.info(
            "INSERTs reais: %d",
            total_inseridos,
        )
        logger.info(
            "UPDATEs reais: %d",
            total_atualizados,
        )
        logger.info(
            "Sem alteração: %d",
            total_duplicados,
        )
        logger.info(
            "Inválidos: %d",
            total_invalidos,
        )
        logger.info(
            "Total LY_TURMA_DOCENTE: %d",
            summary.get(
                "total_registros",
                0,
            ),
        )
        logger.info(
            "Última página processada: %d",
            final_checkpoint[
                "last_written_page"
            ],
        )
        logger.info(
            "Última chave registrada: %s",
            final_checkpoint[
                "last_written_chave"
            ],
        )
        logger.info(
            "Tempo: %.2f s",
            elapsed,
        )
        logger.info(
            "Tabela limpa: NÃO",
        )
        logger.info("=" * 90)

        return True

    except Exception as exc:

        logger.exception(
            "Erro durante sincronização "
            "LY_TURMA_DOCENTE: %s",
            exc,
        )

        return False


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """
    Ponto de entrada da sincronização.

    Processa os argumentos de linha de comando e inicia o processo.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Sincronização incremental "
            "de LY_TURMA_DOCENTE."
        )
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help=(
            "Número máximo de páginas "
            "nesta execução."
        ),
    )

    parser.add_argument(
        "--checkpoint-pages",
        type=int,
        default=DEFAULT_CHECKPOINT_PAGES,
        help=(
            "Quantidade de páginas da leva "
            "(default: 100)."
        ),
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Reseta somente o checkpoint. "
            "NÃO limpa a tabela."
        ),
    )

    args = parser.parse_args()

    # ========================================================================
    # VALIDAÇÕES
    # ========================================================================

    if (
        args.pages is not None
        and args.pages <= 0
    ):

        logger.error(
            "--pages deve ser maior que zero."
        )

        return 1

    if args.checkpoint_pages <= 0:

        logger.error(
            "--checkpoint-pages deve ser maior que zero."
        )

        return 1

    # ========================================================================
    # CONFIGURAÇÃO DA API
    # ========================================================================

    if not all([
        config.LYCEUM_BASE_URL,
        config.LYCEUM_USERNAME,
        config.LYCEUM_PASSWORD,
    ]):

        logger.error(
            "Configuração da API Lyceum incompleta."
        )

        return 1

    # ========================================================================
    # EXECUÇÃO
    # ========================================================================

    return (
        0
        if run(
            max_pages=args.pages,
            reset_checkpoint=args.reset,
            checkpoint_pages=args.checkpoint_pages,
        )
        else 1
    )


# ============================================================================
# EXECUÇÃO DIRETA
# ============================================================================

if __name__ == "__main__":

    sys.exit(
        main()
    )
