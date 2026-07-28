#!/usr/bin/env python3
"""
models/ly_turma_docente.py
Modelo para tabela LY_TURMA_DOCENTE usando core.database (SQL Server)
Inclui suporte a checkpoint de sincronização incremental.
"""
import logging
from typing import List, Dict, Any, Optional
from core.database import get_db_connection, execute_query, fetch_one

logger = logging.getLogger(__name__)


class LyTurmaDocenteModel:
    TABLE_NAME = "LY_TURMA_DOCENTE"
    DB_NAME = "lyceum"
    CHECKPOINT_TABLE = "SYNC_CHECKPOINT_TURMA_DOCENTE"

    API_FIELDS = [
        'chave', 'ano', 'periodo', 'turma', 'disciplina', 'num_func',
        'funcao', 'carga_hor', 'dt_inicio', 'dt_fim', 'dt_ultalt',
        'observacao', 'usuario',
        'fl_field01', 'fl_field02', 'fl_field03', 'fl_field04', 'fl_field05',
        'fl_field06', 'fl_field07', 'fl_field08', 'fl_field09', 'fl_field10',
        'fl_field11', 'fl_field12', 'fl_field13', 'fl_field14', 'fl_field15',
        'fl_field16', 'fl_field17', 'fl_field18', 'fl_field19', 'fl_field20'
    ]

    # ---------- Métodos auxiliares ----------
    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, bool):
            return 'S' if value else 'N'
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in ['null', 'none', '']:
                return None
            return value
        return str(value)

    @classmethod
    def _table_exists(cls, table_name: str) -> bool:
        query = """
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
        """
        result = fetch_one(query, (table_name,), database_name=cls.DB_NAME)
        return result is not None

    # ---------- Criação da tabela de dados ----------
    @classmethod
    def create_table(cls):
        if cls._table_exists(cls.TABLE_NAME):
            logger.info(f"Tabela {cls.TABLE_NAME} já existe.")
            return True

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
            [data_importacao] DATETIME2 DEFAULT GETDATE(),
            [data_atualizacao] DATETIME2 DEFAULT GETDATE()
        )
        """
        try:
            execute_query(sql, database_name=cls.DB_NAME)
            indexes = [
                f"CREATE INDEX idx_turma_docente_chave ON [{cls.TABLE_NAME}]([chave])",
                f"CREATE INDEX idx_turma_docente_ano_periodo ON [{cls.TABLE_NAME}]([ano], [periodo])",
                f"CREATE INDEX idx_turma_docente_turma ON [{cls.TABLE_NAME}]([turma])",
                f"CREATE INDEX idx_turma_docente_disciplina ON [{cls.TABLE_NAME}]([disciplina])",
                f"CREATE INDEX idx_turma_docente_num_func ON [{cls.TABLE_NAME}]([num_func])",
            ]
            for idx in indexes:
                try:
                    execute_query(idx, database_name=cls.DB_NAME)
                except Exception as e:
                    logger.warning(f"Erro ao criar índice: {e}")
            logger.info(f"Tabela {cls.TABLE_NAME} criada com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar tabela {cls.TABLE_NAME}: {e}")
            return False

    # ---------- Tabela de checkpoint ----------
    @classmethod
    def _create_checkpoint_table(cls):
        if cls._table_exists(cls.CHECKPOINT_TABLE):
            return True
        sql = f"""
        CREATE TABLE [{cls.CHECKPOINT_TABLE}] (
            [id] INT IDENTITY(1,1) PRIMARY KEY,
            [last_page] INT NOT NULL,
            [last_chave] BIGINT NOT NULL,
            [updated_at] DATETIME2 DEFAULT GETDATE()
        )
        """
        try:
            execute_query(sql, database_name=cls.DB_NAME)
            # Insere registro inicial
            execute_query(
                f"INSERT INTO [{cls.CHECKPOINT_TABLE}] ([last_page], [last_chave]) VALUES (0, 0)",
                database_name=cls.DB_NAME
            )
            logger.info(f"Tabela {cls.CHECKPOINT_TABLE} criada.")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar checkpoint: {e}")
            return False

    @classmethod
    def get_checkpoint(cls) -> Dict[str, int]:
        """Retorna o último checkpoint salvo: { 'last_page': int, 'last_chave': int }"""
        cls._create_checkpoint_table()
        sql = f"SELECT TOP 1 [last_page], [last_chave] FROM [{cls.CHECKPOINT_TABLE}] ORDER BY [id] DESC"
        row = fetch_one(sql, database_name=cls.DB_NAME)
        if row:
            return {'last_page': row[0], 'last_chave': row[1]}
        return {'last_page': 0, 'last_chave': 0}

    @classmethod
    def update_checkpoint(cls, last_page: int, last_chave: int):
        """Atualiza o checkpoint com a última página e última chave processadas."""
        cls._create_checkpoint_table()
        sql = f"""
            UPDATE [{cls.CHECKPOINT_TABLE}]
            SET [last_page] = ?, [last_chave] = ?, [updated_at] = GETDATE()
            WHERE [id] = (SELECT MAX([id]) FROM [{cls.CHECKPOINT_TABLE}])
        """
        try:
            execute_query(sql, (last_page, last_chave), database_name=cls.DB_NAME)
        except Exception as e:
            logger.error(f"Erro ao atualizar checkpoint: {e}")

    # ---------- Operações de dados ----------
    @classmethod
    def get_max_chave(cls) -> int:
        sql = f"SELECT MAX([chave]) FROM [{cls.TABLE_NAME}]"
        row = fetch_one(sql, database_name=cls.DB_NAME)
        return row[0] if row and row[0] is not None else 0

    @classmethod
    def clear_table(cls):
        try:
            execute_query(f"DELETE FROM [{cls.TABLE_NAME}]", database_name=cls.DB_NAME)
            logger.info(f"Tabela {cls.TABLE_NAME} limpa.")
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar tabela: {e}")
            return False

    @classmethod
    def batch_insert(cls, data_list: List[Dict]) -> int:
        if not data_list:
            return 0
        success = 0
        errors = 0
        with get_db_connection(database_name=cls.DB_NAME) as conn:
            cursor = conn.cursor()
            for data in data_list:
                try:
                    chave = cls._normalize_value(data.get('chave'))
                    if not chave:
                        errors += 1
                        continue
                    columns = ['chave']
                    values = [chave]
                    for field in cls.API_FIELDS:
                        if field != 'chave':
                            val = cls._normalize_value(data.get(field))
                            if val is not None:
                                columns.append(field)
                                values.append(val)
                    cols_str = ', '.join([f"[{c}]" for c in columns])
                    placeholders = ', '.join(['?' for _ in values])
                    sql = f"""
                        INSERT INTO [{cls.TABLE_NAME}] ({cols_str}, [data_atualizacao])
                        VALUES ({placeholders}, GETDATE())
                    """
                    cursor.execute(sql, tuple(values))
                    success += 1
                except Exception as e:
                    logger.error(f"Erro ao inserir chave={data.get('chave')}: {e}")
                    errors += 1
            conn.commit()
        logger.info(f"Batch insert: {success} sucessos, {errors} erros, total {len(data_list)}")
        return success

    @classmethod
    def get_summary(cls) -> Dict:
        queries = {
            'total_registros': f"SELECT COUNT(*) FROM [{cls.TABLE_NAME}]",
            'turmas_distintas': f"SELECT COUNT(DISTINCT [turma]) FROM [{cls.TABLE_NAME}]",
            'disciplinas_distintas': f"SELECT COUNT(DISTINCT [disciplina]) FROM [{cls.TABLE_NAME}]",
            'docentes_distintos': f"SELECT COUNT(DISTINCT [num_func]) FROM [{cls.TABLE_NAME}]",
            'anos_distintos': f"SELECT COUNT(DISTINCT [ano]) FROM [{cls.TABLE_NAME}]",
            'periodos_distintos': f"SELECT COUNT(DISTINCT [periodo]) FROM [{cls.TABLE_NAME}]",
            'ultima_atualizacao': f"SELECT MAX([data_atualizacao]) FROM [{cls.TABLE_NAME}]"
        }
        results = {}
        for key, q in queries.items():
            row = fetch_one(q, database_name=cls.DB_NAME)
            results[key] = row[0] if row else 0
        return results