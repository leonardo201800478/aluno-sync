
#!/usr/bin/env python3
"""
models/ly_turma.py

Modelo para a tabela LY_TURMA usando core.database.

Características:
    - Inserção incremental/progressiva.
    - NÃO limpa a tabela durante a sincronização.
    - Checkpoint representa a última página processada com sucesso.
    - Página sem registros do ano desejado também gera checkpoint.
    - Página com registros somente duplicados também gera checkpoint.
    - Proteção contra duplicidade por:
          ano + semestre + turma + disciplina
    - Transação explícita no batch_insert().
    - Rollback em caso de falha.
    - Índices para consultas e paginação.
"""

import logging
from typing import List, Dict, Any

from core.database import (
    get_db_connection,
    execute_query,
    fetch_all,
    fetch_one,
)

logger = logging.getLogger(__name__)


class LyTurmaModel:

    TABLE_NAME = "LY_TURMA"
    DB_NAME = "lyceum"

    CHECKPOINT_TABLE = "SYNC_CHECKPOINT_TURMA"

    API_FIELDS = [
        "ano",
        "semestre",
        "turma",
        "disciplina",
        "curso",
        "curriculo",
        "sit_turma",
        "dt_inicio",
        "dt_fim",
        "dt_criacao",
        "dt_ultalt",
        "dt_limite_enturma",
        "dt_confirma_dol",
        "stamp_atualizacao",
        "num_alunos",
        "vagas_calouros",
        "vagas_veteranos",
        "aulas_previstas",
        "aulas_dadas",
        "min_aulas",
        "duracao_aula",
        "serie",
        "nivel",
        "turno",
        "horario",
        "tem_horario",
        "faculdade",
        "unidade_responsavel",
        "centro_de_custo",
        "disciplina_multipla",
        "dependencia",
        "especial",
        "turma_integracao",
        "em_elaboracao",
        "lancamento_historico",
        "permite_choque_horario",
        "permite_desfaz_fecham",
        "utiliza_indice",
        "utiliza_proc_seletivo",
        "exibe_somente_lista_sel",
        "interf_ens_dist",
        "nivel_presenca",
        "idioma",
        "classificacao",
        "num_func",
        "ult_num_chamada",
        "formula_mf1",
        "formula_mf2",
        "formula_mf3",
        "formula_ca1",
        "formula_ca2",
        "formula_ca3",
        "obs_formula_mf1",
        "obs_formula_mf2",
        "obs_formula_mf3",
        "conceito_min1",
        "conceito_min2",
        "conceito_min3",
        "conceito_min_ex",
        "conceito_min_ex2",
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
    def _normalize_value(cls, value: Any) -> Any:
        """
        Normaliza valores provenientes da API.

        Regras:
            - None permanece None.
            - bool vira 'S'/'N'.
            - números permanecem números.
            - strings recebem strip().
            - 'null', 'none' e string vazia viram None.
            - demais objetos são convertidos para string.

        Parameters
        ----------
        value:
            Valor recebido da API.

        Returns
        -------
        Any
            Valor normalizado.
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
                "null",
                "none",
                "",
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
        table_name: str = None,
    ) -> bool:
        """
        Verifica se uma tabela existe no banco Lyceum.

        Parameters
        ----------
        table_name:
            Nome da tabela. Se omitido, usa TABLE_NAME.

        Returns
        -------
        bool
            True quando a tabela existe.
        """

        table_name = (
            table_name
            or cls.TABLE_NAME
        )

        sql = """
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
              AND TABLE_TYPE = 'BASE TABLE'
        """

        row = fetch_one(
            sql,
            (table_name,),
            database_name=cls.DB_NAME,
        )

        return row is not None

    # ========================================================================
    # CRIAÇÃO DA TABELA
    # ========================================================================

    @classmethod
    def create_table(cls) -> bool:
        """
        Cria a LY_TURMA caso ainda não exista.

        Se a tabela já existir, nenhum dado é alterado ou removido.

        Returns
        -------
        bool
            True quando a tabela está disponível.
        """

        if cls._table_exists(cls.TABLE_NAME):

            logger.info(
                "Tabela %s já existe.",
                cls.TABLE_NAME,
            )

            cls.create_indexes()

            return True

        sql = f"""
        CREATE TABLE [{cls.TABLE_NAME}] (

            [id] INT IDENTITY(1,1) PRIMARY KEY,

            [ano] BIGINT NOT NULL,
            [semestre] BIGINT NOT NULL,
            [turma] NVARCHAR(100) NOT NULL,
            [disciplina] NVARCHAR(100) NOT NULL,

            [curso] NVARCHAR(100),
            [curriculo] NVARCHAR(100),
            [sit_turma] NVARCHAR(20),

            [dt_inicio] NVARCHAR(30),
            [dt_fim] NVARCHAR(30),
            [dt_criacao] NVARCHAR(30),
            [dt_ultalt] NVARCHAR(30),
            [dt_limite_enturma] NVARCHAR(30),
            [dt_confirma_dol] NVARCHAR(30),
            [stamp_atualizacao] NVARCHAR(50),

            [num_alunos] BIGINT,
            [vagas_calouros] BIGINT,
            [vagas_veteranos] BIGINT,
            [aulas_previstas] BIGINT,
            [aulas_dadas] BIGINT,
            [min_aulas] BIGINT,
            [duracao_aula] BIGINT,
            [serie] BIGINT,

            [nivel] NVARCHAR(50),
            [turno] NVARCHAR(20),
            [horario] NVARCHAR(255),
            [tem_horario] NVARCHAR(2),

            [faculdade] NVARCHAR(50),
            [unidade_responsavel] NVARCHAR(100),
            [centro_de_custo] NVARCHAR(50),

            [disciplina_multipla] NVARCHAR(2),
            [dependencia] NVARCHAR(20),
            [especial] NVARCHAR(20),
            [turma_integracao] NVARCHAR(20),
            [em_elaboracao] NVARCHAR(20),
            [lancamento_historico] NVARCHAR(20),

            [permite_choque_horario] NVARCHAR(20),
            [permite_desfaz_fecham] NVARCHAR(20),
            [utiliza_indice] NVARCHAR(20),
            [utiliza_proc_seletivo] NVARCHAR(20),
            [exibe_somente_lista_sel] NVARCHAR(20),
            [interf_ens_dist] NVARCHAR(20),

            [nivel_presenca] NVARCHAR(50),
            [idioma] NVARCHAR(50),
            [classificacao] NVARCHAR(50),

            [num_func] BIGINT,
            [ult_num_chamada] BIGINT,

            [formula_mf1] NVARCHAR(MAX),
            [formula_mf2] NVARCHAR(MAX),
            [formula_mf3] NVARCHAR(MAX),

            [formula_ca1] NVARCHAR(MAX),
            [formula_ca2] NVARCHAR(MAX),
            [formula_ca3] NVARCHAR(MAX),

            [obs_formula_mf1] NVARCHAR(MAX),
            [obs_formula_mf2] NVARCHAR(MAX),
            [obs_formula_mf3] NVARCHAR(MAX),

            [conceito_min1] NVARCHAR(50),
            [conceito_min2] NVARCHAR(50),
            [conceito_min3] NVARCHAR(50),
            [conceito_min_ex] NVARCHAR(50),
            [conceito_min_ex2] NVARCHAR(50),

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

            [data_importacao] DATETIME DEFAULT GETDATE(),
            [data_atualizacao] DATETIME DEFAULT GETDATE()
        )
        """

        try:

            execute_query(
                sql,
                database_name=cls.DB_NAME,
            )

            logger.info(
                "Tabela %s criada com sucesso.",
                cls.TABLE_NAME,
            )

            cls.create_indexes()

            return True

        except Exception as exc:

            logger.exception(
                "Erro ao criar tabela %s: %s",
                cls.TABLE_NAME,
                exc,
            )

            return False

    # ========================================================================
    # ÍNDICES
    # ========================================================================

    @classmethod
    def _index_exists(
        cls,
        index_name: str,
    ) -> bool:
        """
        Verifica se um índice existe na LY_TURMA.

        Parameters
        ----------
        index_name:
            Nome do índice.

        Returns
        -------
        bool
            True quando o índice existe.
        """

        sql = """
            SELECT 1
            FROM sys.indexes
            WHERE name = ?
              AND object_id = OBJECT_ID(?)
        """

        row = fetch_one(
            sql,
            (
                index_name,
                cls.TABLE_NAME,
            ),
            database_name=cls.DB_NAME,
        )

        return row is not None

    @classmethod
    def create_indexes(cls) -> bool:
        """
        Cria os índices necessários caso ainda não existam.

        A criação é idempotente: índices existentes são ignorados.

        Returns
        -------
        bool
            True após tentar criar todos os índices.
        """

        indexes = [

            (
                "idx_turma_ano_semestre",
                f"""
                CREATE INDEX [idx_turma_ano_semestre]
                ON [{cls.TABLE_NAME}]
                ([ano], [semestre])
                """,
            ),

            (
                "idx_turma_paginacao",
                f"""
                CREATE INDEX [idx_turma_paginacao]
                ON [{cls.TABLE_NAME}]
                (
                    [ano],
                    [semestre],
                    [disciplina],
                    [turma]
                )
                """,
            ),

            (
                "idx_turma_chave_logica",
                f"""
                CREATE INDEX [idx_turma_chave_logica]
                ON [{cls.TABLE_NAME}]
                (
                    [ano],
                    [semestre],
                    [turma],
                    [disciplina]
                )
                """,
            ),

            (
                "idx_turma_disciplina",
                f"""
                CREATE INDEX [idx_turma_disciplina]
                ON [{cls.TABLE_NAME}]
                ([disciplina])
                """,
            ),

            (
                "idx_turma_curso",
                f"""
                CREATE INDEX [idx_turma_curso]
                ON [{cls.TABLE_NAME}]
                ([curso])
                """,
            ),

            (
                "idx_turma_sit_turma",
                f"""
                CREATE INDEX [idx_turma_sit_turma]
                ON [{cls.TABLE_NAME}]
                ([sit_turma])
                """,
            ),

            (
                "idx_turma_faculdade",
                f"""
                CREATE INDEX [idx_turma_faculdade]
                ON [{cls.TABLE_NAME}]
                ([faculdade])
                """,
            ),
        ]

        for index_name, index_sql in indexes:

            if cls._index_exists(index_name):
                continue

            try:

                execute_query(
                    index_sql,
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
        Cria a tabela de checkpoint caso ela ainda não exista.

        IMPORTANTE:
            O checkpoint representa a última página PROCESSADA
            COM SUCESSO, independentemente de a página ter produzido
            INSERT, duplicados, registros inválidos ou zero registros
            do ano desejado.

        Returns
        -------
        bool
            True quando a tabela está disponível.
        """

        if cls._table_exists(cls.CHECKPOINT_TABLE):
            return True

        sql = f"""
        CREATE TABLE [{cls.CHECKPOINT_TABLE}] (

            [id] INT IDENTITY(1,1) PRIMARY KEY,

            [last_written_page] INT NOT NULL,
            [updated_at] DATETIME DEFAULT GETDATE()
        )
        """

        try:

            execute_query(
                sql,
                database_name=cls.DB_NAME,
            )

            execute_query(
                f"""
                INSERT INTO [{cls.CHECKPOINT_TABLE}]
                    ([last_written_page])
                VALUES
                    (0)
                """,
                database_name=cls.DB_NAME,
            )

            logger.info(
                "Tabela de checkpoint %s criada.",
                cls.CHECKPOINT_TABLE,
            )

            return True

        except Exception as exc:

            logger.exception(
                "Erro ao criar checkpoint: %s",
                exc,
            )

            return False

    @classmethod
    def get_checkpoint(cls) -> Dict[str, int]:
        """
        Retorna a última página processada com sucesso.

        Returns
        -------
        Dict[str, int]
            Exemplo:
                {
                    "last_written_page": 84
                }
        """

        if not cls._create_checkpoint_table():

            raise RuntimeError(
                "Não foi possível preparar a tabela de checkpoint."
            )

        sql = f"""
            SELECT TOP 1
                [last_written_page]
            FROM [{cls.CHECKPOINT_TABLE}]
            ORDER BY [id] DESC
        """

        row = fetch_one(
            sql,
            database_name=cls.DB_NAME,
        )

        if not row:

            return {
                "last_written_page": 0,
            }

        return {
            "last_written_page": int(
                row[0] or 0
            ),
        }

    @classmethod
    def update_checkpoint(
        cls,
        last_written_page: int,
    ) -> bool:
        """
        Atualiza o checkpoint.

        A atualização deve ocorrer SOMENTE depois que a página
        tiver sido completamente processada e o batch tiver
        realizado COMMIT com sucesso.

        A página é considerada processada mesmo quando:
            - não possui registros de 2026;
            - possui somente duplicados;
            - possui registros inválidos.

        Parameters
        ----------
        last_written_page:
            Número da última página processada com sucesso.

        Returns
        -------
        bool
            True quando o checkpoint foi salvo.
        """

        if last_written_page < 0:

            logger.error(
                "Checkpoint inválido: página=%d",
                last_written_page,
            )

            return False

        if not cls._create_checkpoint_table():
            return False

        sql = f"""
            UPDATE [{cls.CHECKPOINT_TABLE}]
            SET
                [last_written_page] = ?,
                [updated_at] = GETDATE()
            WHERE [id] = (
                SELECT MAX([id])
                FROM [{cls.CHECKPOINT_TABLE}]
            )
        """

        try:

            execute_query(
                sql,
                (last_written_page,),
                database_name=cls.DB_NAME,
            )

            logger.debug(
                "Checkpoint atualizado para página %d.",
                last_written_page,
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao atualizar checkpoint para página %d: %s",
                last_written_page,
                exc,
            )

            return False

    @classmethod
    def reset_checkpoint(cls) -> bool:
        """
        Reinicia o checkpoint para zero.

        A tabela LY_TURMA NÃO é apagada.

        Returns
        -------
        bool
            True quando o reset foi concluído.
        """

        if not cls._create_checkpoint_table():
            return False

        try:

            execute_query(
                f"""
                UPDATE [{cls.CHECKPOINT_TABLE}]
                SET
                    [last_written_page] = 0,
                    [updated_at] = GETDATE()
                """,
                database_name=cls.DB_NAME,
            )

            logger.warning(
                "Checkpoint da LY_TURMA reiniciado para 0. "
                "Tabela LY_TURMA não foi limpa."
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao reiniciar checkpoint: %s",
                exc,
            )

            return False

    # ========================================================================
    # INSERT INDIVIDUAL
    # ========================================================================

    @classmethod
    def insert(
        cls,
        data: Dict,
    ) -> bool:
        """
        Insere uma turma individual.

        Este método não é utilizado pelo batch principal, mas permanece
        disponível para operações individuais.

        Parameters
        ----------
        data:
            Registro da API.

        Returns
        -------
        bool
            True quando inserido com sucesso.
        """

        try:

            ano = cls._normalize_value(
                data.get("ano")
            )

            semestre = cls._normalize_value(
                data.get("semestre")
            )

            turma = cls._normalize_value(
                data.get("turma")
            )

            disciplina = cls._normalize_value(
                data.get("disciplina")
            )

            if not all([
                ano,
                semestre,
                turma,
                disciplina,
            ]):

                return False

            columns = [
                "ano",
                "semestre",
                "turma",
                "disciplina",
            ]

            values = [
                ano,
                semestre,
                turma,
                disciplina,
            ]

            for field in cls.API_FIELDS:

                if field in (
                    "ano",
                    "semestre",
                    "turma",
                    "disciplina",
                ):
                    continue

                value = cls._normalize_value(
                    data.get(field)
                )

                if value is not None:

                    columns.append(field)
                    values.append(value)

            cols = ", ".join(
                f"[{column}]"
                for column in columns
            )

            placeholders = ", ".join(
                "?"
                for _ in values
            )

            sql = f"""
                INSERT INTO [{cls.TABLE_NAME}]
                (
                    {cols},
                    [data_atualizacao]
                )
                VALUES
                (
                    {placeholders},
                    GETDATE()
                )
            """

            execute_query(
                sql,
                tuple(values),
                database_name=cls.DB_NAME,
            )

            return True

        except Exception as exc:

            logger.error(
                "Erro ao inserir turma %s/%s/%s/%s: %s",
                data.get("ano"),
                data.get("semestre"),
                data.get("disciplina"),
                data.get("turma"),
                exc,
            )

            return False

    # ========================================================================
    # BATCH INSERT
    # ========================================================================

    @classmethod
    def batch_insert(
        cls,
        data_list: List[Dict],
    ) -> Dict[str, int]:
        """
        Processa uma página/lote em uma única transação.

        IMPORTANTE:
            get_db_connection() é um context manager.
            Portanto, a conexão REAL deve ser obtida através de:

                with get_db_connection(...) as conn:

            e não através de:

                conn = get_db_connection(...)

        Regras:
            - todos os INSERTs usam a mesma conexão;
            - todos os registros da página fazem parte da mesma transação;
            - COMMIT somente depois do processamento completo;
            - qualquer erro de banco provoca ROLLBACK;
            - após o COMMIT, o sincronizador pode avançar o checkpoint;
            - página vazia é tratada pelo sincronizador sem chamar este método.

        Parameters
        ----------
        data_list:
            Registros válidos da página.

        Returns
        -------
        Dict[str, int]
            Quantidades de:
                inseridos
                duplicados
                invalidos
        """

        result = {
            "inseridos": 0,
            "duplicados": 0,
            "invalidos": 0,
        }

        # --------------------------------------------------------------------
        # Nenhum registro para processar.
        #
        # Isso NÃO representa erro.
        # O sincronizador poderá avançar o checkpoint da página.
        # --------------------------------------------------------------------

        if not data_list:

            logger.info(
                "Batch LY_TURMA vazio. "
                "Nenhum registro de %d para inserir.",
                2026,
            )

            return result

        # --------------------------------------------------------------------
        # CORREÇÃO PRINCIPAL:
        #
        # get_db_connection() retorna um context manager.
        # A conexão real está disponível dentro do "with".
        # --------------------------------------------------------------------

        with get_db_connection(
            database_name=cls.DB_NAME
        ) as conn:

            cursor = conn.cursor()

            try:

                for data in data_list:

                    # ========================================================
                    # CHAVE LÓGICA
                    # ========================================================

                    ano = cls._normalize_value(
                        data.get("ano")
                    )

                    semestre = cls._normalize_value(
                        data.get("semestre")
                    )

                    turma = cls._normalize_value(
                        data.get("turma")
                    )

                    disciplina = cls._normalize_value(
                        data.get("disciplina")
                    )

                    # ========================================================
                    # VALIDAÇÃO
                    # ========================================================

                    if not all([
                        ano,
                        semestre,
                        turma,
                        disciplina,
                    ]):

                        result["invalidos"] += 1

                        continue

                    # ========================================================
                    # DUPLICIDADE
                    # ========================================================

                    cursor.execute(
                        f"""
                        SELECT TOP 1 1
                        FROM [{cls.TABLE_NAME}]
                        WHERE [ano] = ?
                          AND [semestre] = ?
                          AND [turma] = ?
                          AND [disciplina] = ?
                        """,
                        (
                            ano,
                            semestre,
                            turma,
                            disciplina,
                        ),
                    )

                    if cursor.fetchone():

                        result["duplicados"] += 1

                        continue

                    # ========================================================
                    # CAMPOS OBRIGATÓRIOS
                    # ========================================================

                    columns = [
                        "ano",
                        "semestre",
                        "turma",
                        "disciplina",
                    ]

                    values = [
                        ano,
                        semestre,
                        turma,
                        disciplina,
                    ]

                    # ========================================================
                    # DEMAIS CAMPOS
                    # ========================================================

                    for field in cls.API_FIELDS:

                        if field in (
                            "ano",
                            "semestre",
                            "turma",
                            "disciplina",
                        ):
                            continue

                        value = cls._normalize_value(
                            data.get(field)
                        )

                        if value is not None:

                            columns.append(field)
                            values.append(value)

                    # ========================================================
                    # SQL
                    # ========================================================

                    cols = ", ".join(
                        f"[{column}]"
                        for column in columns
                    )

                    placeholders = ", ".join(
                        "?"
                        for _ in values
                    )

                    # ========================================================
                    # INSERT
                    # ========================================================

                    cursor.execute(
                        f"""
                        INSERT INTO [{cls.TABLE_NAME}]
                        (
                            {cols},
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

                # ============================================================
                # COMMIT
                #
                # Somente aqui a página é considerada persistida.
                # ============================================================

                conn.commit()

            except Exception:

                # ============================================================
                # ROLLBACK
                # ============================================================

                try:

                    conn.rollback()

                    logger.error(
                        "ROLLBACK executado para o batch LY_TURMA."
                    )

                except Exception as rollback_exc:

                    logger.error(
                        "Falha no ROLLBACK LY_TURMA: %s",
                        rollback_exc,
                    )

                raise

        logger.info(
            "Batch LY_TURMA | "
            "Inseridos=%d | "
            "Duplicados=%d | "
            "Inválidos=%d",
            result["inseridos"],
            result["duplicados"],
            result["invalidos"],
        )

        return result

    # ========================================================================
    # RESUMO
    # ========================================================================

    @classmethod
    def get_summary(cls) -> Dict:
        """
        Retorna estatísticas da LY_TURMA.

        Returns
        -------
        Dict
            Estatísticas gerais da tabela.
        """

        queries = {

            "total_turmas":
                f"""
                SELECT COUNT(*)
                FROM [{cls.TABLE_NAME}]
                """,

            "anos_distintos":
                f"""
                SELECT COUNT(DISTINCT [ano])
                FROM [{cls.TABLE_NAME}]
                """,

            "semestres_distintos":
                f"""
                SELECT COUNT(DISTINCT [semestre])
                FROM [{cls.TABLE_NAME}]
                """,

            "disciplinas_distintas":
                f"""
                SELECT COUNT(DISTINCT [disciplina])
                FROM [{cls.TABLE_NAME}]
                """,

            "turmas_distintas":
                f"""
                SELECT COUNT(DISTINCT [turma])
                FROM [{cls.TABLE_NAME}]
                """,

            "turmas_ativas":
                f"""
                SELECT COUNT(*)
                FROM [{cls.TABLE_NAME}]
                WHERE [sit_turma] = 'A'
                """,

            "ultima_atualizacao":
                f"""
                SELECT MAX([data_atualizacao])
                FROM [{cls.TABLE_NAME}]
                """,
        }

        results = {}

        for key, query in queries.items():

            row = fetch_one(
                query,
                database_name=cls.DB_NAME,
            )

            results[key] = (
                row[0]
                if row
                else 0
            )

        return results

    # ========================================================================
    # CONSULTAS
    # ========================================================================

    @classmethod
    def get_all_turmas(cls) -> List[Dict]:
        """
        Retorna todas as turmas.

        Returns
        -------
        List[Dict]
            Lista de turmas.
        """

        sql = f"""
            SELECT *
            FROM [{cls.TABLE_NAME}]
            ORDER BY
                [ano] DESC,
                [semestre] DESC,
                [disciplina],
                [turma]
        """

        rows = fetch_all(
            sql,
            database_name=cls.DB_NAME,
        )

        if not rows:
            return []

        columns_rows = fetch_all(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            (cls.TABLE_NAME,),
            database_name=cls.DB_NAME,
        )

        columns = [
            row[0]
            for row in columns_rows
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    @classmethod
    def get_by_ano_semestre(
        cls,
        ano: int,
        semestre: int,
    ) -> List[Dict]:
        """
        Retorna turmas de determinado ano e semestre.

        Parameters
        ----------
        ano:
            Ano letivo.

        semestre:
            Semestre letivo.

        Returns
        -------
        List[Dict]
            Turmas encontradas.
        """

        rows = fetch_all(
            f"""
            SELECT *
            FROM [{cls.TABLE_NAME}]
            WHERE [ano] = ?
              AND [semestre] = ?
            ORDER BY [disciplina], [turma]
            """,
            (
                ano,
                semestre,
            ),
            database_name=cls.DB_NAME,
        )

        if not rows:
            return []

        columns_rows = fetch_all(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            (cls.TABLE_NAME,),
            database_name=cls.DB_NAME,
        )

        columns = [
            row[0]
            for row in columns_rows
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    @classmethod
    def get_by_disciplina(
        cls,
        disciplina_code: str,
    ) -> List[Dict]:
        """
        Retorna todas as turmas de uma disciplina.

        Parameters
        ----------
        disciplina_code:
            Código da disciplina.

        Returns
        -------
        List[Dict]
            Turmas encontradas.
        """

        rows = fetch_all(
            f"""
            SELECT *
            FROM [{cls.TABLE_NAME}]
            WHERE [disciplina] = ?
            ORDER BY
                [ano] DESC,
                [semestre] DESC,
                [turma]
            """,
            (disciplina_code,),
            database_name=cls.DB_NAME,
        )

        if not rows:
            return []

        columns_rows = fetch_all(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
            ORDER BY ORDINAL_POSITION
            """,
            (cls.TABLE_NAME,),
            database_name=cls.DB_NAME,
        )

        columns = [
            row[0]
            for row in columns_rows
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]
