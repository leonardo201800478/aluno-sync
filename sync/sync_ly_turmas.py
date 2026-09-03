
#!/usr/bin/env python3
"""
sync/sync_ly_turmas.py

Sincronização incremental da LY_TURMA.

Regras:

    - API somente GET.
    - Filtro ano = 2026.
    - NÃO limpa LY_TURMA.
    - Cada página é processada e persistida antes do checkpoint avançar.
    - Checkpoint representa a última página PROCESSADA COM SUCESSO.
    - Página sem registros de 2026 também avança o checkpoint.
    - Página somente com duplicados também avança o checkpoint.
    - Página somente com registros inválidos também avança o checkpoint.
    - Na próxima execução começa na página seguinte.
    - Registros já existentes não são duplicados.
    - Falha de INSERT provoca rollback.
    - Falha ao salvar checkpoint interrompe a execução.
"""

import sys
import os
import time
import logging
import argparse


# ============================================================================
# PATH
# ============================================================================

BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


# ============================================================================
# IMPORTS
# ============================================================================

from core.config import config
from core.api_client import TurmaAPIClient
from models.ly_turma import LyTurmaModel


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
    "sync.ly_turma"
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
# API
# ============================================================================

def get_turmas_page(
    client: TurmaAPIClient,
    page: int,
):
    """
    Obtém uma página de turmas da API Lyceum.

    O método utilizado no API client permanece centralizado aqui,
    facilitando alterações futuras na assinatura da API.

    Parameters
    ----------
    client:
        Cliente da API Lyceum.

    page:
        Número da página.

    Returns
    -------
    list
        Registros retornados pela API.
    """

    return client.get_turmas_from_page(
        page,
        PAGE_SIZE,
        ano=ANO,
    )


# ============================================================================
# RETOMADA
# ============================================================================

def get_resume_page(
    last_processed_page: int,
) -> int:
    """
    Calcula a página inicial da próxima execução.

    O checkpoint representa a última página processada com sucesso.

    Portanto:

        checkpoint = 84
        próxima página = 85

    Não existe mais retorno de 100 páginas.

    Isso evita reprocessar páginas que já foram verificadas
    e que não continham registros do ano desejado.

    Parameters
    ----------
    last_processed_page:
        Última página processada com sucesso.

    Returns
    -------
    int
        Página que deve ser processada na próxima execução.
    """

    if last_processed_page < 0:
        return 0

    return last_processed_page + 1


# ============================================================================
# RUN
# ============================================================================

def run(
    max_pages: int = None,
    reset_checkpoint: bool = False,
    checkpoint_pages: int = DEFAULT_CHECKPOINT_PAGES,
) -> bool:
    """
    Executa a sincronização incremental da LY_TURMA.

    O parâmetro checkpoint_pages é mantido por compatibilidade
    com a CLI existente, mas não é utilizado para voltar páginas.

    A nova regra é:

        checkpoint = última página processada com sucesso

    Assim, uma página que não produziu INSERT também avança
    o checkpoint.

    Parameters
    ----------
    max_pages:
        Número máximo de páginas processadas nesta execução.
        None significa sem limite.

    reset_checkpoint:
        Quando True, reseta somente o checkpoint.
        A LY_TURMA nunca é limpa.

    checkpoint_pages:
        Mantido por compatibilidade com a interface anterior.

    Returns
    -------
    bool
        True quando a execução termina sem erro.
    """

    start_time = time.time()

    logger.info("=" * 90)
    logger.info(
        "INICIANDO SINCRONIZAÇÃO - LY_TURMA"
    )
    logger.info(
        "Modo: INSERT PROGRESSIVO"
    )
    logger.info(
        "Filtro: ano = %d",
        ANO,
    )
    logger.info(
        "Checkpoint: ÚLTIMA PÁGINA PROCESSADA COM SUCESSO"
    )
    logger.info(
        "Retomada: página seguinte ao checkpoint"
    )
    logger.info(
        "Leva configurada: %d páginas",
        checkpoint_pages,
    )
    logger.info(
        "Tabela será limpa? NÃO"
    )
    logger.info("=" * 90)

    try:

        # ====================================================================
        # TABELA
        # ====================================================================

        if not LyTurmaModel.create_table():

            logger.error(
                "Falha ao preparar LY_TURMA."
            )

            return False

        # ====================================================================
        # CHECKPOINT
        # ====================================================================

        if not LyTurmaModel._create_checkpoint_table():

            logger.error(
                "Falha ao preparar tabela de checkpoint."
            )

            return False

        # --------------------------------------------------------------------
        # RESET
        # --------------------------------------------------------------------

        if reset_checkpoint:

            logger.warning(
                "RESET solicitado."
            )

            logger.warning(
                "Somente o checkpoint será resetado."
            )

            logger.warning(
                "LY_TURMA NÃO será limpa."
            )

            if not LyTurmaModel.reset_checkpoint():

                logger.error(
                    "Falha ao resetar checkpoint."
                )

                return False

        # --------------------------------------------------------------------
        # LEITURA DO CHECKPOINT
        # --------------------------------------------------------------------

        checkpoint = (
            LyTurmaModel.get_checkpoint()
        )

        last_processed_page = checkpoint[
            "last_written_page"
        ]

        page = get_resume_page(
            last_processed_page
        )

        logger.info(
            "Última página processada com sucesso: %d",
            last_processed_page,
        )

        logger.info(
            "Página de retomada: %d",
            page,
        )

        # ====================================================================
        # CLIENTE
        # ====================================================================

        client = TurmaAPIClient()

        # ====================================================================
        # CONTADORES
        # ====================================================================

        total_api = 0
        total_2026 = 0
        total_inseridos = 0
        total_duplicados = 0
        total_invalidos = 0

        pages_processed = 0
        pages_with_2026 = 0
        pages_without_2026 = 0
        pages_only_duplicates = 0

        # ====================================================================
        # LOOP
        # ====================================================================

        while True:

            # ----------------------------------------------------------------
            # LIMITE DE PÁGINAS
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
            # LEITURA
            # ----------------------------------------------------------------

            logger.info(
                "Lendo página %d...",
                page,
            )

            items = get_turmas_page(
                client,
                page,
            )

            # ----------------------------------------------------------------
            # FIM DA API
            # ----------------------------------------------------------------

            if not items:

                logger.info(
                    "Página %d vazia. Fim da API.",
                    page,
                )

                # Não avançamos para uma página que não foi
                # efetivamente retornada pela API.
                break

            total_api += len(items)

            # =================================================================
            # FILTRO DO ANO
            # =================================================================

            valid_items = []

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

                    valid_items.append(item)

                else:

                    total_invalidos += 1

            total_2026 += len(valid_items)

            # -----------------------------------------------------------------
            # ESTATÍSTICAS DA PÁGINA
            # -----------------------------------------------------------------

            if valid_items:

                pages_with_2026 += 1

            else:

                pages_without_2026 += 1

            logger.info(
                "Página %d | API=%d | ano=%d=%d",
                page,
                len(items),
                ANO,
                len(valid_items),
            )

            # =================================================================
            # BATCH
            # =================================================================

            result = LyTurmaModel.batch_insert(
                valid_items
            )

            inseridos = result[
                "inseridos"
            ]

            duplicados = result[
                "duplicados"
            ]

            invalidos_batch = result[
                "invalidos"
            ]

            total_inseridos += inseridos
            total_duplicados += duplicados

            # -----------------------------------------------------------------
            # DUPLICADOS
            # -----------------------------------------------------------------

            if (
                valid_items
                and inseridos == 0
                and duplicados == len(valid_items)
            ):

                pages_only_duplicates += 1

            # =================================================================
            # CHECKPOINT
            #
            # IMPORTANTE:
            #
            # O checkpoint avança SEMPRE que o processamento da página
            # terminou com sucesso.
            #
            # Não importa se:
            #
            #     INSERT = 33
            #     INSERT = 0
            #     DUPLICADOS = 100
            #     ANO 2026 = 0
            #     INVÁLIDOS > 0
            #
            # Se não houve exceção, a página foi processada.
            # =================================================================

            if not LyTurmaModel.update_checkpoint(
                page
            ):

                raise RuntimeError(
                    "Falha ao salvar checkpoint da página "
                    f"{page}."
                )

            logger.info(
                "CHECKPOINT AVANÇADO: página %d | "
                "INSERT=%d | DUPLICADOS=%d | INVÁLIDOS=%d | "
                "ANO_%d=%d",
                page,
                inseridos,
                duplicados,
                invalidos_batch,
                ANO,
                len(valid_items),
            )

            # =================================================================
            # PRÓXIMA PÁGINA
            # =================================================================

            pages_processed += 1

            page += 1

            # -----------------------------------------------------------------
            # DELAY
            # -----------------------------------------------------------------

            if DEFAULT_DELAY > 0:

                time.sleep(
                    DEFAULT_DELAY
                )

        # ====================================================================
        # RESUMO
        # ====================================================================

        summary = (
            LyTurmaModel.get_summary()
        )

        elapsed = (
            time.time() - start_time
        )

        final_checkpoint = (
            LyTurmaModel.get_checkpoint()
        )

        logger.info("=" * 90)
        logger.info(
            "RESUMO - LY_TURMA"
        )
        logger.info(
            "Páginas processadas: %d",
            pages_processed,
        )
        logger.info(
            "Páginas com registros de %d: %d",
            ANO,
            pages_with_2026,
        )
        logger.info(
            "Páginas sem registros de %d: %d",
            ANO,
            pages_without_2026,
        )
        logger.info(
            "Páginas somente com duplicados: %d",
            pages_only_duplicates,
        )
        logger.info(
            "Registros API: %d",
            total_api,
        )
        logger.info(
            "Registros de %d: %d",
            ANO,
            total_2026,
        )
        logger.info(
            "INSERTs reais: %d",
            total_inseridos,
        )
        logger.info(
            "Duplicados ignorados: %d",
            total_duplicados,
        )
        logger.info(
            "Fora de %d: %d",
            ANO,
            total_invalidos,
        )
        logger.info(
            "Total LY_TURMA: %d",
            summary.get(
                "total_turmas",
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
            "Próxima página de retomada: %d",
            get_resume_page(
                final_checkpoint[
                    "last_written_page"
                ]
            ),
        )
        logger.info(
            "Tempo: %.2f s",
            elapsed,
        )
        logger.info(
            "Tabela limpa: NÃO"
        )
        logger.info("=" * 90)

        return True

    except Exception as exc:

        logger.exception(
            "Erro durante sincronização LY_TURMA: %s",
            exc,
        )

        return False


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:
    """
    Ponto de entrada da sincronização.

    Returns
    -------
    int
        0 para sucesso.
        1 para erro.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Sincronização incremental "
            "da LY_TURMA."
        )
    )

    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help=(
            "Quantidade máxima de páginas "
            "nesta execução."
        ),
    )

    parser.add_argument(
        "--checkpoint-pages",
        type=int,
        default=DEFAULT_CHECKPOINT_PAGES,
        help=(
            "Mantido por compatibilidade. "
            "Não existe mais retorno automático de páginas."
        ),
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help=(
            "Reseta somente o checkpoint. "
            "NÃO limpa LY_TURMA."
        ),
    )

    args = parser.parse_args()

    # ========================================================================
    # VALIDAÇÕES
    # ========================================================================

    if args.pages is not None and args.pages <= 0:

        logger.error(
            "--pages deve ser maior que zero."
        )

        return 1

    if args.checkpoint_pages <= 0:

        logger.error(
            "--checkpoint-pages deve ser maior que zero."
        )

        return 1

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


if __name__ == "__main__":
    sys.exit(main())
