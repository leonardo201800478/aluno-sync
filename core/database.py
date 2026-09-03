
# core/database.py

"""
Camada de acesso ao banco de dados SQL Server.

Responsabilidades:
    - Criar e gerenciar conexões pyodbc.
    - Controlar automaticamente COMMIT e ROLLBACK.
    - Executar comandos SQL.
    - Buscar múltiplos registros.
    - Buscar um único registro.

IMPORTANTE
----------
get_db_connection() é um context manager.

Uso correto:

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(...)

O context manager executa:

    sucesso -> COMMIT
    exceção -> ROLLBACK

e sempre fecha a conexão ao final.

Não utilizar:

    conn = get_db_connection()

para obter diretamente uma conexão pyodbc.
"""


import logging
from contextlib import contextmanager
from typing import Any, Iterator, Optional

import pyodbc

from core.config import config


# ============================================================================
# LOGGING
# ============================================================================

logger = logging.getLogger(__name__)


# ============================================================================
# RESOLUÇÃO DO BANCO
# ============================================================================

def _resolve_database_name(
    database_name: Optional[str],
) -> str:
    """
    Resolve o nome do banco de dados que será utilizado.

    Parameters
    ----------
    database_name:
        Nome explícito do banco.
        Caso seja None, utiliza o banco Lyceum configurado.

    Returns
    -------
    str
        Nome do banco de dados.

    Raises
    ------
    ValueError
        Quando o nome do banco não estiver configurado.
    """

    if database_name is not None:

        database = str(
            database_name
        ).strip()

        if database:

            return database

    database = str(
        config.SQL_SERVER_DATABASE_LYCEUM or ""
    ).strip()

    if not database:

        raise ValueError(
            "Banco de dados não configurado em "
            "SQL_SERVER_DATABASE_LYCEUM."
        )

    return database


# ============================================================================
# CONNECTION STRING
# ============================================================================

def _build_connection_string(
    database_name: Optional[str] = None,
) -> str:
    """
    Monta a connection string do SQL Server.

    Parameters
    ----------
    database_name:
        Banco de dados que será utilizado.

    Returns
    -------
    str
        Connection string pronta para pyodbc.
    """

    database = _resolve_database_name(
        database_name
    )

    driver = str(
        config.SQL_SERVER_DRIVER or ""
    ).strip()

    host = str(
        config.SQL_SERVER_HOST or ""
    ).strip()

    port = str(
        config.SQL_SERVER_PORT or ""
    ).strip()

    user = str(
        config.SQL_SERVER_USER or ""
    ).strip()

    password = (
        config.SQL_SERVER_PASSWORD
        or ""
    )

    if not driver:

        raise ValueError(
            "SQL_SERVER_DRIVER não configurado."
        )

    if not host:

        raise ValueError(
            "SQL_SERVER_HOST não configurado."
        )

    if not port:

        raise ValueError(
            "SQL_SERVER_PORT não configurado."
        )

    if not user:

        raise ValueError(
            "SQL_SERVER_USER não configurado."
        )

    return (
        f"DRIVER={driver};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )


# ============================================================================
# CONNECTION
# ============================================================================

@contextmanager
def get_db_connection(
    database_name: Optional[str] = None,
) -> Iterator[pyodbc.Connection]:
    """
    Abre uma conexão com o SQL Server e controla a transação.

    Parameters
    ----------
    database_name:
        Nome do banco de dados.

        Quando None:
            utiliza config.SQL_SERVER_DATABASE_LYCEUM.

    Yields
    ------
    pyodbc.Connection
        Conexão ativa com o banco.

    Comportamento transacional
    --------------------------
    Se o bloco terminar normalmente:

        COMMIT

    Se ocorrer qualquer exceção:

        ROLLBACK
        exceção propagada

    Em qualquer situação:

        conexão fechada

    Example
    -------
        with get_db_connection("lyceum") as conn:

            cursor = conn.cursor()

            cursor.execute(
                "UPDATE tabela SET campo = ?",
                ("valor",)
            )
    """

    connection_string = _build_connection_string(
        database_name
    )

    conn: Optional[pyodbc.Connection] = None

    try:

        logger.debug(
            "Abrindo conexão SQL Server | banco=%s",
            _resolve_database_name(
                database_name
            ),
        )

        conn = pyodbc.connect(
            connection_string
        )

        # --------------------------------------------------------------------
        # O context manager controla explicitamente a transação.
        #
        # O commit será feito somente se todo o bloco terminar normalmente.
        # --------------------------------------------------------------------

        yield conn

        conn.commit()

        logger.debug(
            "COMMIT realizado | banco=%s",
            _resolve_database_name(
                database_name
            ),
        )

    except Exception:

        if conn is not None:

            try:

                conn.rollback()

                logger.debug(
                    "ROLLBACK realizado | banco=%s",
                    _resolve_database_name(
                        database_name
                    ),
                )

            except Exception as rollback_exc:

                logger.error(
                    "Erro durante ROLLBACK: %s",
                    rollback_exc,
                )

        raise

    finally:

        if conn is not None:

            try:

                conn.close()

                logger.debug(
                    "Conexão SQL Server fechada."
                )

            except Exception as close_exc:

                logger.warning(
                    "Erro ao fechar conexão SQL Server: %s",
                    close_exc,
                )


# ============================================================================
# EXECUTE QUERY
# ============================================================================

def execute_query(
    query: str,
    params: tuple = (),
    database_name: Optional[str] = None,
) -> None:
    """
    Executa um comando SQL sem retornar registros.

    Ideal para:

        INSERT
        UPDATE
        DELETE
        CREATE TABLE
        ALTER TABLE
        CREATE INDEX
        DROP
        etc.

    Parameters
    ----------
    query:
        Comando SQL.

    params:
        Parâmetros posicionais utilizados pelos placeholders '?'.

    database_name:
        Banco de dados de destino.

    Returns
    -------
    None

    Notes
    -----
    O COMMIT é realizado automaticamente pelo
    get_db_connection() quando a função termina normalmente.

    Em caso de exceção, o ROLLBACK é automático.
    """

    if not query or not query.strip():

        raise ValueError(
            "A consulta SQL não pode ser vazia."
        )

    with get_db_connection(
        database_name
    ) as conn:

        cursor = conn.cursor()

        try:

            cursor.execute(
                query,
                params,
            )

        finally:

            try:

                cursor.close()

            except Exception:

                pass


# ============================================================================
# FETCH ALL
# ============================================================================

def fetch_all(
    query: str,
    params: tuple = (),
    database_name: Optional[str] = None,
) -> list[Any]:
    """
    Executa uma consulta SQL e retorna todos os registros.

    Parameters
    ----------
    query:
        Consulta SELECT.

    params:
        Parâmetros posicionais utilizados pelos placeholders '?'.

    database_name:
        Banco de dados de destino.

    Returns
    -------
    list
        Lista contendo todas as linhas retornadas.

    Example
    -------
        rows = fetch_all(
            '''
            SELECT id, nome
            FROM alunos
            WHERE ano = ?
            ''',
            (2026,),
        )
    """

    if not query or not query.strip():

        raise ValueError(
            "A consulta SQL não pode ser vazia."
        )

    with get_db_connection(
        database_name
    ) as conn:

        cursor = conn.cursor()

        try:

            cursor.execute(
                query,
                params,
            )

            return cursor.fetchall()

        finally:

            try:

                cursor.close()

            except Exception:

                pass


# ============================================================================
# FETCH ONE
# ============================================================================

def fetch_one(
    query: str,
    params: tuple = (),
    database_name: Optional[str] = None,
) -> Optional[Any]:
    """
    Executa uma consulta SQL e retorna somente o primeiro registro.

    Parameters
    ----------
    query:
        Consulta SELECT.

    params:
        Parâmetros posicionais utilizados pelos placeholders '?'.

    database_name:
        Banco de dados de destino.

    Returns
    -------
    Optional[Any]
        Primeiro registro encontrado.

        Retorna None quando nenhuma linha é encontrada.

    Example
    -------
        row = fetch_one(
            '''
            SELECT id, nome
            FROM alunos
            WHERE id = ?
            ''',
            (123,),
        )
    """

    if not query or not query.strip():

        raise ValueError(
            "A consulta SQL não pode ser vazia."
        )

    with get_db_connection(
        database_name
    ) as conn:

        cursor = conn.cursor()

        try:

            cursor.execute(
                query,
                params,
            )

            return cursor.fetchone()

        finally:

            try:

                cursor.close()

            except Exception:

                pass
