
#!/usr/bin/env python3
"""
models/ly_turma_docente.py

Modelo para LY_TURMA_DOCENTE.

Características
---------------
- Inserção incremental.
- Atualização incremental (UPSERT).
- NÃO limpa LY_TURMA_DOCENTE.
- Chave natural: chave.
- Registros novos são inseridos.
- Registros existentes são comparados.
- Registros alterados são atualizados.
- Registros sem alteração não são modificados.
- Registros inválidos são contabilizados.
- Batch por página em uma única transação.
- COMMIT/ROLLBACK controlados pelo core.database.
- Checkpoint baseado na última página processada com sucesso.
- Compatível com tabelas de checkpoint de versões anteriores.
"""

import logging
from typing import Any, Dict, List, Optional

from core.database import (
    execute_query,
    fetch_one,
    get_db_connection,
)


logger = logging.getLogger(__name__)


class LyTurmaDocenteModel:
    """
    Model da tabela LY_TURMA_DOCENTE.

    A chave [chave] identifica o registro retornado pela API.
    """

    # ========================================================================
    # CONFIGURAÇÃO
    # ========================================================================

    TABLE_NAME = "LY_TURMA_DOCENTE"

    DB_NAME = "lyceum"

    CHECKPOINT_TABLE = (
        "SYNC_CHECKPOINT_TURMA_DOCENTE"
    )

    # ========================================================================
    # CAMPOS DA API
    # ========================================================================

    API_FIELDS = [
        "chave",
        "ano",
        "periodo",
        "turma",
        "disciplina",
        "num_func",
        "funcao",
        "carga_hor",
        "dt_inicio",
        "dt_fim",
        "dt_ultalt",
        "observacao",
        "usuario",
        "fl_field01",
        "fl_field02",
        "fl_field03",
        "fl_field04",
        "fl_field05",
        "fl_field06",
        "fl_field07",
        "fl_field08",
        "fl_field09",
        "fl_field10",
        "fl_field11",
        "fl_field12",
        "fl_field13",
        "fl_field14",
        "fl_field15",
        "fl_field16",
        "fl_field17",
        "fl_field18",
        "fl_field19",
        "fl_field20",
    ]

    # Campos existentes na tabela que são comparados com a API.
    DATA_FIELDS = [
        "ano",
        "periodo",
        "turma",
        "disciplina",
        "num_func",
        "funcao",
        "carga_hor",
        "dt_inicio",
        "dt_fim",
        "dt_ultalt",
        "observacao",
        "usuario",
        "fl_field01",
        "fl_field02",
        "fl_field03",
        "fl_field04",
        "fl_field05",
        "fl_field06",
        "fl_field07",
        "fl_field08",
        "fl_field09",
        "fl_field10",
        "fl_field11",
        "fl_field12",
        "fl_field13",
        "fl_field14",
        "fl_field15",
        "fl_field16",
        "fl_field17",
        "fl_field18",
        "fl_field19",
        "fl_field20",
    ]

    # ========================================================================
    # NORMALIZAÇÃO
    # ========================================================================

    @classmethod
    def _normalize_value(
        cls,
        value: Any,
    ) -> Any:
        """
        Normaliza valores recebidos da API.

        Regras:
            None -> None
            bool -> S/N
            int/float -> mantém
            string -> strip()
            '', 'null', 'none' -> None
            outros tipos -> string
        """

        if value is None:
            return None

        if isinstance(value, bool):
            return "S" if value else "N"

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):

            value = value.strip()

            if value.lower() in (
                "",
                "null",
                "none",
            ):
                return None

            return value

        return str(value)

    # ========================================================================
    # EXISTÊNCIA DE TABELA
    # ========================================================================

    @classmethod
    def _table_exists(
        cls,
        table_name: Optional[str] = None,
    ) -> bool:
        """
        Verifica se uma tabela existe no banco LYCEUM.
        """

        table_name = (
            table_name
            or cls.TABLE_NAME
        )

        row = fetch_one(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
              AND TABLE_TYPE = 'BASE TABLE'
            """,
            (
                table_name,
            ),
            database_name=cls.DB_NAME,
        )

        return row is not None

    # ========================================================================
    # EXISTÊNCIA DE COLUNA
    # ========================================================================

    @classmethod
    def _column_exists(
        cls,
        table_name: str,
        column_name: str,
    ) -> bool:
        """
        Verifica se uma coluna existe em determinada tabela.
        """

        row = fetch_one(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
              AND COLUMN_NAME = ?
            """,
            (
                table_name,
                column_name,
            ),
            database_name=cls.DB_NAME,
        )

        return row is not None

    # ========================================================================
    # EXISTÊNCIA DE ÍNDICE
    # ========================================================================

    @classmethod
    def _index_exists(
        cls,
        index_name: str,
    ) -> bool:
        """
        Verifica se um índice existe na tabela principal.
        """

        row = fetch_one(
            """
            SELECT 1
            FROM sys.indexes
            WHERE name = ?
              AND object_id = OBJECT_ID(?)
            """,
            (
                index_name,
                cls.TABLE_NAME,
            ),
            database_name=cls.DB_NAME,
        )

        return row is not None

    # ========================================================================
    # CRIAÇÃO DA TABELA
    # ========================================================================

    @classmethod
    def create_table(cls) -> bool:
        """
        Cria LY_TURMA_DOCENTE caso ela ainda não exista.

        Se já existir, preserva os dados e garante os índices.
        """

        if cls._table_exists(
            cls.TABLE_NAME
        ):

            logger.info(
                "Tabela %s já existe.",
                cls.TABLE_NAME,
            )

            return cls.create_indexes()

        sql = f"""
        CREATE TABLE [{cls.TABLE_NAME}] (

            [id] INT IDENTITY(1,1) PRIMARY KEY,

            [chave] BIGINT NOT NULL,

            [ano] BIGINT,
            [periodo] BIGINT,

            [turma] NVARCHAR(100),
            [disciplina] NVARCHAR(100),

            [num_func] BIGINT,
            [funcao] NVARCHAR(50),
            [carga_hor] BIGINT,

            [dt_inicio] NVARCHAR(20),
            [dt_fim] NVARCHAR(20),
            [dt_ultalt] NVARCHAR(20),

            [observacao] NVARCHAR(MAX),
            [usuario] NVARCHAR(100),

            [fl_field01] NVARCHAR(255),
            [fl_field02] NVARCHAR(255),
            [fl_field03] NVARCHAR(255),
            [fl_field04] NVARCHAR(255),
            [fl_field05] NVARCHAR(255),
            [fl_field06] NVARCHAR(255),
            [fl_field07] NVARCHAR(255),
            [fl_field08] NVARCHAR(255),
            [fl_field09] NVARCHAR(255),
            [fl_field10] NVARCHAR(255),
            [fl_field11] NVARCHAR(255),
            [fl_field12] NVARCHAR(255),
            [fl_field13] NVARCHAR(255),
            [fl_field14] NVARCHAR(255),
            [fl_field15] NVARCHAR(255),
            [fl_field16] NVARCHAR(255),
            [fl_field17] NVARCHAR(255),
            [fl_field18] NVARCHAR(255),
            [fl_field19] NVARCHAR(255),
            [fl_field20] NVARCHAR(255),

            [data_importacao] DATETIME
                DEFAULT GETDATE(),

            [data_atualizacao] DATETIME
                DEFAULT GETDATE()
        )
        """

        try:

            execute_query(
                sql,
                database_name=cls.DB_NAME,
            )

            logger.info(
                "Tabela %s criada.",
                cls.TABLE_NAME,
            )

            return cls.create_indexes()

        except Exception as exc:

            logger.exception(
                "Erro ao criar %s: %s",
                cls.TABLE_NAME,
                exc,
            )

            return False

    # ========================================================================
    # ÍNDICES
    # ========================================================================

    @classmethod
    def create_indexes(cls) -> bool:
        """
        Garante a criação dos índices utilizados pela sincronização.
        """

        indexes = [

            (
                "idx_turma_docente_chave",
                f"""
                CREATE INDEX [idx_turma_docente_chave]
                ON [{cls.TABLE_NAME}]
                ([chave])
                """,
            ),

            (
                "idx_turma_docente_paginacao",
                f"""
                CREATE INDEX [idx_turma_docente_paginacao]
                ON [{cls.TABLE_NAME}]
                (
                    [ano],
                    [periodo],
                    [chave]
                )
                """,
            ),

            (
                "idx_turma_docente_ano_periodo",
                f"""
                CREATE INDEX [idx_turma_docente_ano_periodo]
                ON [{cls.TABLE_NAME}]
                (
                    [ano],
                    [periodo]
                )
                """,
            ),

            (
                "idx_turma_docente_turma",
                f"""
                CREATE INDEX [idx_turma_docente_turma]
                ON [{cls.TABLE_NAME}]
                ([turma])
                """,
            ),

            (
                "idx_turma_docente_disciplina",
                f"""
                CREATE INDEX [idx_turma_docente_disciplina]
                ON [{cls.TABLE_NAME}]
                ([disciplina])
                """,
            ),

            (
                "idx_turma_docente_num_func",
                f"""
                CREATE INDEX [idx_turma_docente_num_func]
                ON [{cls.TABLE_NAME}]
                ([num_func])
                """,
            ),
        ]

        for index_name, sql in indexes:

            if cls._index_exists(
                index_name
            ):
                continue

            try:

                execute_query(
                    sql,
                    database_name=cls.DB_NAME,
                )

                logger.info(
                    "Índice %s criado.",
                    index_name,
                )

            except Exception as exc:

                logger.warning(
                    "Não foi possível criar índice %s: %s",
                    index_name,
                    exc,
                )

        return True

    # ========================================================================
    # CHECKPOINT
    # ========================================================================

    @classmethod
    def _create_checkpoint_table(cls) -> bool:
        """
        Cria ou migra a tabela de checkpoint.

        Compatível com uma tabela antiga que não possua as colunas:

            last_written_page
            last_written_chave
            updated_at

        Nenhum dado da tabela principal é removido.
        """

        try:

            # ----------------------------------------------------------------
            # Criação
            # ----------------------------------------------------------------

            if not cls._table_exists(
                cls.CHECKPOINT_TABLE
            ):

                execute_query(
                    f"""
                    CREATE TABLE [{cls.CHECKPOINT_TABLE}] (

                        [id] INT IDENTITY(1,1) PRIMARY KEY,

                        [last_written_page] INT NOT NULL
                            DEFAULT 0,

                        [last_written_chave] BIGINT NULL
                            DEFAULT 0,

                        [updated_at] DATETIME
                            DEFAULT GETDATE()
                    )
                    """,
                    database_name=cls.DB_NAME,
                )

                logger.info(
                    "Tabela de checkpoint %s criada.",
                    cls.CHECKPOINT_TABLE,
                )

            # ----------------------------------------------------------------
            # last_written_page
            # ----------------------------------------------------------------

            if not cls._column_exists(
                cls.CHECKPOINT_TABLE,
                "last_written_page",
            ):

                logger.warning(
                    "Migrando %s: adicionando "
                    "last_written_page.",
                    cls.CHECKPOINT_TABLE,
                )

                execute_query(
                    f"""
                    ALTER TABLE [{cls.CHECKPOINT_TABLE}]
                    ADD [last_written_page] INT NULL
                    """,
                    database_name=cls.DB_NAME,
                )

                execute_query(
                    f"""
                    UPDATE [{cls.CHECKPOINT_TABLE}]
                    SET [last_written_page] = 0
                    WHERE [last_written_page] IS NULL
                    """,
                    database_name=cls.DB_NAME,
                )

            # ----------------------------------------------------------------
            # last_written_chave
            # ----------------------------------------------------------------

            if not cls._column_exists(
                cls.CHECKPOINT_TABLE,
                "last_written_chave",
            ):

                logger.warning(
                    "Migrando %s: adicionando "
                    "last_written_chave.",
                    cls.CHECKPOINT_TABLE,
                )

                execute_query(
                    f"""
                    ALTER TABLE [{cls.CHECKPOINT_TABLE}]
                    ADD [last_written_chave] BIGINT NULL
                    """,
                    database_name=cls.DB_NAME,
                )

                execute_query(
                    f"""
                    UPDATE [{cls.CHECKPOINT_TABLE}]
                    SET [last_written_chave] = 0
                    WHERE [last_written_chave] IS NULL
                    """,
                    database_name=cls.DB_NAME,
                )

            # ----------------------------------------------------------------
            # updated_at
            # ----------------------------------------------------------------

            if not cls._column_exists(
                cls.CHECKPOINT_TABLE,
                "updated_at",
            ):

                logger.warning(
                    "Migrando %s: adicionando updated_at.",
                    cls.CHECKPOINT_TABLE,
                )

                execute_query(
                    f"""
                    ALTER TABLE [{cls.CHECKPOINT_TABLE}]
                    ADD [updated_at] DATETIME NULL
                    """,
                    database_name=cls.DB_NAME,
                )

                execute_query(
                    f"""
                    UPDATE [{cls.CHECKPOINT_TABLE}]
                    SET [updated_at] = GETDATE()
                    WHERE [updated_at] IS NULL
                    """,
                    database_name=cls.DB_NAME,
                )

            # ----------------------------------------------------------------
            # Garante registro inicial
            # ----------------------------------------------------------------

            row = fetch_one(
                f"""
                SELECT TOP 1 [id]
                FROM [{cls.CHECKPOINT_TABLE}]
                ORDER BY [id] DESC
                """,
                database_name=cls.DB_NAME,
            )

            if row is None:

                execute_query(
                    f"""
                    INSERT INTO [{cls.CHECKPOINT_TABLE}]
                    (
                        [last_written_page],
                        [last_written_chave],
                        [updated_at]
                    )
                    VALUES
                    (
                        0,
                        0,
                        GETDATE()
                    )
                    """,
                    database_name=cls.DB_NAME,
                )

                logger.info(
                    "Registro inicial de checkpoint criado."
                )

            return True

        except Exception as exc:

            logger.exception(
                "Erro ao criar/migrar checkpoint %s: %s",
                cls.CHECKPOINT_TABLE,
                exc,
            )

            return False

    # ========================================================================
    # CHECKPOINT - LEITURA
    # ========================================================================

    @classmethod
    def get_checkpoint(
        cls,
    ) -> Dict[str, Any]:
        """
        Retorna o último checkpoint processado com sucesso.
        """

        if not cls._create_checkpoint_table():

            raise RuntimeError(
                "Não foi possível preparar a tabela "
                f"{cls.CHECKPOINT_TABLE}."
            )

        row = fetch_one(
            f"""
            SELECT TOP 1
                [last_written_page],
                [last_written_chave]
            FROM [{cls.CHECKPOINT_TABLE}]
            ORDER BY [id] DESC
            """,
            database_name=cls.DB_NAME,
        )

        if row is None:

            return {
                "last_written_page": 0,
                "last_written_chave": 0,
            }

        try:

            page = int(
                row[0] or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            page = 0

        try:

            chave = int(
                row[1] or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            chave = 0

        return {
            "last_written_page": page,
            "last_written_chave": chave,
        }

    # ========================================================================
    # CHECKPOINT - ATUALIZAÇÃO
    # ========================================================================

    @classmethod
    def update_checkpoint(
        cls,
        last_written_page: int,
        last_written_chave: int = 0,
    ) -> bool:
        """
        Atualiza o checkpoint.

        A função deve ser chamada somente depois que a página
        tiver sido processada com sucesso.

        A página pode ter:

            INSERT
            UPDATE
            nenhuma alteração

        Todos esses casos permitem avançar o checkpoint.
        """

        if not cls._create_checkpoint_table():

            return False

        try:

            execute_query(
                f"""
                UPDATE [{cls.CHECKPOINT_TABLE}]
                SET
                    [last_written_page] = ?,
                    [last_written_chave] = ?,
                    [updated_at] = GETDATE()
                WHERE [id] = (
                    SELECT MAX([id])
                    FROM [{cls.CHECKPOINT_TABLE}]
                )
                """,
                (
                    int(last_written_page),
                    int(last_written_chave or 0),
                ),
                database_name=cls.DB_NAME,
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao atualizar checkpoint: %s",
                exc,
            )

            return False

    # ========================================================================
    # CHECKPOINT - RESET
    # ========================================================================

    @classmethod
    def reset_checkpoint(cls) -> bool:
        """
        Reseta somente o checkpoint.

        NÃO remove registros de LY_TURMA_DOCENTE.
        """

        if not cls._create_checkpoint_table():

            return False

        try:

            execute_query(
                f"""
                UPDATE [{cls.CHECKPOINT_TABLE}]
                SET
                    [last_written_page] = 0,
                    [last_written_chave] = 0,
                    [updated_at] = GETDATE()
                """,
                database_name=cls.DB_NAME,
            )

            logger.warning(
                "Checkpoint LY_TURMA_DOCENTE reiniciado."
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao resetar checkpoint: %s",
                exc,
            )

            return False

    # ========================================================================
    # CLEAR TABLE
    # ========================================================================

    @classmethod
    def clear_table(cls) -> bool:
        """
        Limpa LY_TURMA_DOCENTE.

        ATENÇÃO:
            Esta função NÃO é utilizada pelo sincronizador incremental.
        """

        try:

            execute_query(
                f"""
                DELETE FROM [{cls.TABLE_NAME}]
                """,
                database_name=cls.DB_NAME,
            )

            logger.warning(
                "Tabela %s limpa.",
                cls.TABLE_NAME,
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao limpar %s: %s",
                cls.TABLE_NAME,
                exc,
            )

            return False

    # ========================================================================
    # BATCH INSERT / UPDATE
    # ========================================================================

    @classmethod
    def batch_insert(
        cls,
        data_list: List[Dict],
    ) -> Dict[str, Any]:
        """
        Processa uma página da API usando INSERT ou UPDATE.

        Regras:

            chave inexistente:
                INSERT

            chave existente + dados iguais:
                nenhuma alteração

            chave existente + dados diferentes:
                UPDATE

            chave inválida:
                inválido

        A página inteira utiliza uma única transação.

        O COMMIT/ROLLBACK é realizado pelo core.database.

        Returns
        -------
        Dict[str, Any]
            {
                "inseridos": int,
                "atualizados": int,
                "duplicados": int,
                "invalidos": int,
                "ultima_chave_inserida": int
            }
        """

        result = {
            "inseridos": 0,
            "atualizados": 0,
            "duplicados": 0,
            "invalidos": 0,
            "ultima_chave_inserida": 0,
        }

        if not data_list:

            return result

        # ====================================================================
        # TRANSAÇÃO
        # ====================================================================

        with get_db_connection(
            database_name=cls.DB_NAME
        ) as conn:

            cursor = conn.cursor()

            # ================================================================
            # PROCESSA CADA REGISTRO
            # ================================================================

            for data in data_list:

                # ------------------------------------------------------------
                # Validação
                # ------------------------------------------------------------

                if not isinstance(
                    data,
                    dict,
                ):

                    result["invalidos"] += 1

                    continue

                # ------------------------------------------------------------
                # Chave
                # ------------------------------------------------------------

                chave = cls._normalize_value(
                    data.get("chave")
                )

                if chave is None:

                    result["invalidos"] += 1

                    continue

                try:

                    numeric_chave = int(
                        chave
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    result["invalidos"] += 1

                    logger.warning(
                        "Chave inválida ignorada: %r",
                        chave,
                    )

                    continue

                # ------------------------------------------------------------
                # Normaliza todos os campos
                # ------------------------------------------------------------

                api_values = {}

                for field in cls.DATA_FIELDS:

                    api_values[field] = (
                        cls._normalize_value(
                            data.get(field)
                        )
                    )

                # ============================================================
                # BUSCA REGISTRO EXISTENTE
                # ============================================================

                cursor.execute(
                    f"""
                    SELECT
                        [id],
                        [ano],
                        [periodo],
                        [turma],
                        [disciplina],
                        [num_func],
                        [funcao],
                        [carga_hor],
                        [dt_inicio],
                        [dt_fim],
                        [dt_ultalt],
                        [observacao],
                        [usuario],
                        [fl_field01],
                        [fl_field02],
                        [fl_field03],
                        [fl_field04],
                        [fl_field05],
                        [fl_field06],
                        [fl_field07],
                        [fl_field08],
                        [fl_field09],
                        [fl_field10],
                        [fl_field11],
                        [fl_field12],
                        [fl_field13],
                        [fl_field14],
                        [fl_field15],
                        [fl_field16],
                        [fl_field17],
                        [fl_field18],
                        [fl_field19],
                        [fl_field20]
                    FROM [{cls.TABLE_NAME}]
                    WHERE [chave] = ?
                    """,
                    (
                        numeric_chave,
                    ),
                )

                existing = cursor.fetchone()

                # ============================================================
                # NÃO EXISTE -> INSERT
                # ============================================================

                if existing is None:

                    columns = [
                        "chave",
                    ]

                    values = [
                        numeric_chave,
                    ]

                    for field in cls.DATA_FIELDS:

                        value = api_values[field]

                        # ----------------------------------------------------
                        # Mantemos o comportamento anterior:
                        # campos None não são enviados no INSERT.
                        #
                        # Assim o DEFAULT/NULL do SQL Server é utilizado.
                        # ----------------------------------------------------

                        if value is not None:

                            columns.append(field)
                            values.append(value)

                    column_sql = ", ".join(
                        f"[{column}]"
                        for column in columns
                    )

                    placeholders = ", ".join(
                        "?"
                        for _ in values
                    )

                    cursor.execute(
                        f"""
                        INSERT INTO [{cls.TABLE_NAME}]
                        (
                            {column_sql},
                            [data_atualizacao]
                        )
                        VALUES
                        (
                            {placeholders},
                            GETDATE()
                        )
                        """,
                        tuple(values),
                    )

                    result["inseridos"] += 1

                    if numeric_chave > result[
                        "ultima_chave_inserida"
                    ]:

                        result[
                            "ultima_chave_inserida"
                        ] = numeric_chave

                    continue

                # ============================================================
                # EXISTE -> COMPARAÇÃO
                # ============================================================

                existing_values = {}

                # existing[0] é o ID.
                #
                # Os demais valores seguem exatamente a ordem do SELECT.

                for index, field in enumerate(
                    cls.DATA_FIELDS,
                    start=1,
                ):

                    existing_values[field] = (
                        cls._normalize_value(
                            existing[index]
                        )
                    )

                # ============================================================
                # IDENTIFICA ALTERAÇÕES
                # ============================================================

                changed_fields = []

                for field in cls.DATA_FIELDS:

                    api_value = api_values[field]

                    database_value = (
                        existing_values[field]
                    )

                    if api_value != database_value:

                        changed_fields.append(
                            field
                        )

                # ============================================================
                # NENHUMA ALTERAÇÃO
                # ============================================================

                if not changed_fields:

                    result["duplicados"] += 1

                    continue

                # ============================================================
                # UPDATE
                # ============================================================

                set_clauses = []

                update_values = []

                for field in cls.DATA_FIELDS:

                    set_clauses.append(
                        f"[{field}] = ?"
                    )

                    update_values.append(
                        api_values[field]
                    )

                # ------------------------------------------------------------
                # Atualiza a data somente quando realmente houve alteração.
                # ------------------------------------------------------------

                set_clauses.append(
                    "[data_atualizacao] = GETDATE()"
                )

                set_sql = ", ".join(
                    set_clauses
                )

                update_values.append(
                    numeric_chave
                )

                cursor.execute(
                    f"""
                    UPDATE [{cls.TABLE_NAME}]
                    SET
                        {set_sql}
                    WHERE [chave] = ?
                    """,
                    tuple(update_values),
                )

                result["atualizados"] += 1

                logger.debug(
                    "Registro atualizado | "
                    "chave=%s | campos=%s",
                    numeric_chave,
                    ", ".join(
                        changed_fields
                    ),
                )

        # ====================================================================
        # IMPORTANTE
        #
        # O bloco with terminou normalmente.
        #
        # Portanto o core.database já executou COMMIT.
        # ====================================================================

        logger.info(
            "Batch LY_TURMA_DOCENTE | "
            "Inseridos=%d | "
            "Atualizados=%d | "
            "Sem alteração=%d | "
            "Inválidos=%d | "
            "Última chave inserida=%s",
            result["inseridos"],
            result["atualizados"],
            result["duplicados"],
            result["invalidos"],
            result["ultima_chave_inserida"],
        )

        return result

    # ========================================================================
    # RESUMO
    # ========================================================================

    @classmethod
    def get_summary(
        cls,
    ) -> Dict[str, Any]:
        """
        Retorna estatísticas da tabela LY_TURMA_DOCENTE.
        """

        queries = {

            "total_registros":
                f"""
                SELECT COUNT(*)
                FROM [{cls.TABLE_NAME}]
                """,

            "turmas_distintas":
                f"""
                SELECT COUNT(DISTINCT [turma])
                FROM [{cls.TABLE_NAME}]
                """,

            "disciplinas_distintas":
                f"""
                SELECT COUNT(DISTINCT [disciplina])
                FROM [{cls.TABLE_NAME}]
                """,

            "docentes_distintos":
                f"""
                SELECT COUNT(DISTINCT [num_func])
                FROM [{cls.TABLE_NAME}]
                """,

            "anos_distintos":
                f"""
                SELECT COUNT(DISTINCT [ano])
                FROM [{cls.TABLE_NAME}]
                """,

            "periodos_distintos":
                f"""
                SELECT COUNT(DISTINCT [periodo])
                FROM [{cls.TABLE_NAME}]
                """,

            "ultima_atualizacao":
                f"""
                SELECT MAX([data_atualizacao])
                FROM [{cls.TABLE_NAME}]
                """,
        }

        results: Dict[str, Any] = {}

        for key, query in queries.items():

            row = fetch_one(
                query,
                database_name=cls.DB_NAME,
            )

            results[key] = (
                row[0]
                if row is not None
                else 0
            )

        return results
