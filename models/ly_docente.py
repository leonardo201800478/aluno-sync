#!/usr/bin/env python3
"""
models/ly_docente.py
Modelo para tabela LY_DOCENTE usando core.database (SQL Server)
SEM chave primária natural - usa IDENTITY.
"""

import logging
from typing import List, Dict, Any, Optional
from core.database import get_db_connection, execute_query, fetch_all, fetch_one
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


class LyDocenteModel:
    """Modelo para tabela LY_DOCENTE (SQL Server) sem chave primária natural."""

    TABLE_NAME = "LY_DOCENTE"
    DB_NAME = "lyceum"  # nome do banco no SQL Server

    API_FIELDS = [
        'cpf', 'num_func', 'agencia', 'ano_ingresso', 'ativo', 'atuacao_profis',
        'bairro', 'banco', 'candidato', 'categoria', 'celular', 'cep', 'cgc_emp',
        'cod_lattes', 'concurso', 'conta_banco', 'contrato_trabalho',
        'cprof_dataexp', 'cprof_num', 'cprof_serie', 'cprof_uf', 'curso_contrato',
        'depto', 'dt_admissao', 'dt_demissao', 'dt_habilit_dol', 'dt_nasc',
        'dt_ult_titulo', 'e_mail_com', 'e_mail_emp', 'email', 'end_com_bairro',
        'end_com_cep', 'end_com_compl', 'end_com_municipio', 'end_com_num',
        'end_com_pais', 'end_compl', 'end_num', 'endcom', 'endemp', 'endemp_bairro',
        'endemp_cep', 'endemp_compl', 'endemp_municipio', 'endemp_num', 'endereco',
        'est_civil', 'faculdade', 'fax_com', 'fax_emp', 'fax_res', 'fechar_turma_internet',
        'fl_field01', 'fl_field02', 'fl_field03', 'fl_field04', 'fl_field05',
        'fl_field06', 'fl_field07', 'fl_field08', 'fl_field09', 'fl_field10',
        'fone', 'fone_com', 'fone_emp', 'hab_tac', 'mailbox', 'matricula',
        'municipio', 'nome_abrev', 'nome_compl', 'nome_empresa', 'nome_meio',
        'nome_social', 'obs', 'obs_tel_com', 'obs_tel_res', 'outra_faculdade',
        'pais_res', 'perc_dedic_mens', 'pessoa', 'pispasep', 'primeiro_nome',
        'razao_social', 're', 'regime_trabalho', 'rg_dtexp', 'rg_emissor',
        'rg_num', 'rg_tipo', 'rg_uf', 'senha_alterada', 'senha_dol', 'sexo',
        'sobrenome', 'stamp_atualizacao', 'tempo_exp_ead', 'tempo_exp_edu_basica',
        'tempo_exp_gestao', 'tempo_exp_magisterio', 'tempo_exp_profissional',
        'tipo_ingresso', 'tipo_pessoa', 'titulacao', 'url_particular',
        'url_professional', 'winusuario'
    ]

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
    def _table_exists(cls) -> bool:
        query = """
            SELECT 1 FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
        """
        result = fetch_one(query, (cls.TABLE_NAME,), database_name=cls.DB_NAME)
        return result is not None

    @classmethod
    def create_table(cls):
        if cls._table_exists():
            logger.info(f"Tabela {cls.TABLE_NAME} já existe.")
            return True

        sql = f"""
        CREATE TABLE [{cls.TABLE_NAME}] (
            [id] INT IDENTITY(1,1) PRIMARY KEY,
            [cpf] NVARCHAR(11),
            [num_func] INT,
            [agencia] NVARCHAR(50),
            [ano_ingresso] BIGINT,
            [ativo] CHAR(1),
            [atuacao_profis] NVARCHAR(255),
            [bairro] NVARCHAR(100),
            [banco] BIGINT,
            [candidato] NVARCHAR(50),
            [categoria] NVARCHAR(50),
            [celular] NVARCHAR(20),
            [cep] NVARCHAR(10),
            [cgc_emp] NVARCHAR(20),
            [cod_lattes] NVARCHAR(50),
            [concurso] NVARCHAR(50),
            [conta_banco] NVARCHAR(20),
            [contrato_trabalho] NVARCHAR(50),
            [cprof_dataexp] NVARCHAR(20),
            [cprof_num] NVARCHAR(50),
            [cprof_serie] NVARCHAR(10),
            [cprof_uf] CHAR(2),
            [curso_contrato] NVARCHAR(100),
            [depto] NVARCHAR(50),
            [dt_admissao] NVARCHAR(20),
            [dt_demissao] NVARCHAR(20),
            [dt_habilit_dol] NVARCHAR(20),
            [dt_nasc] NVARCHAR(20),
            [dt_ult_titulo] NVARCHAR(20),
            [e_mail_com] NVARCHAR(255),
            [e_mail_emp] NVARCHAR(255),
            [email] NVARCHAR(255),
            [end_com_bairro] NVARCHAR(100),
            [end_com_cep] NVARCHAR(10),
            [end_com_compl] NVARCHAR(100),
            [end_com_municipio] NVARCHAR(100),
            [end_com_num] NVARCHAR(10),
            [end_com_pais] NVARCHAR(50),
            [end_compl] NVARCHAR(100),
            [end_num] NVARCHAR(10),
            [endcom] NVARCHAR(255),
            [endemp] NVARCHAR(255),
            [endemp_bairro] NVARCHAR(100),
            [endemp_cep] NVARCHAR(10),
            [endemp_compl] NVARCHAR(100),
            [endemp_municipio] NVARCHAR(100),
            [endemp_num] NVARCHAR(10),
            [endereco] NVARCHAR(255),
            [est_civil] CHAR(30),
            [faculdade] NVARCHAR(50),
            [fax_com] NVARCHAR(20),
            [fax_emp] NVARCHAR(20),
            [fax_res] NVARCHAR(20),
            [fechar_turma_internet] CHAR(1),
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
            [fone] NVARCHAR(20),
            [fone_com] NVARCHAR(20),
            [fone_emp] NVARCHAR(20),
            [hab_tac] CHAR(1),
            [mailbox] NVARCHAR(50),
            [matricula] NVARCHAR(20),
            [municipio] NVARCHAR(100),
            [nome_abrev] NVARCHAR(100),
            [nome_compl] NVARCHAR(500),
            [nome_empresa] NVARCHAR(255),
            [nome_meio] NVARCHAR(100),
            [nome_social] NVARCHAR(500),
            [obs] NVARCHAR(MAX),
            [obs_tel_com] NVARCHAR(MAX),
            [obs_tel_res] NVARCHAR(MAX),
            [outra_faculdade] NVARCHAR(50),
            [pais_res] NVARCHAR(50),
            [perc_dedic_mens] FLOAT,
            [pessoa] BIGINT,
            [pispasep] NVARCHAR(20),
            [primeiro_nome] NVARCHAR(100),
            [razao_social] NVARCHAR(255),
            [re] NVARCHAR(20),
            [regime_trabalho] NVARCHAR(50),
            [rg_dtexp] NVARCHAR(20),
            [rg_emissor] NVARCHAR(50),
            [rg_num] NVARCHAR(20),
            [rg_tipo] NVARCHAR(20),
            [rg_uf] CHAR(2),
            [senha_alterada] CHAR(1),
            [senha_dol] NVARCHAR(50),
            [sexo] CHAR(1),
            [sobrenome] NVARCHAR(100),
            [stamp_atualizacao] NVARCHAR(50),
            [tempo_exp_ead] BIGINT,
            [tempo_exp_edu_basica] BIGINT,
            [tempo_exp_gestao] BIGINT,
            [tempo_exp_magisterio] BIGINT,
            [tempo_exp_profissional] BIGINT,
            [tipo_ingresso] NVARCHAR(50),
            [tipo_pessoa] NVARCHAR(20),
            [titulacao] NVARCHAR(100),
            [url_particular] NVARCHAR(255),
            [url_professional] NVARCHAR(255),
            [winusuario] NVARCHAR(50),
            [data_importacao] DATETIME2 DEFAULT GETDATE(),
            [data_atualizacao] DATETIME2 DEFAULT GETDATE()
        )
        """
        try:
            execute_query(sql, database_name=cls.DB_NAME)

            # Índices
            indexes = [
                f"CREATE INDEX idx_docente_cpf ON [{cls.TABLE_NAME}]([cpf])",
                f"CREATE INDEX idx_docente_num_func ON [{cls.TABLE_NAME}]([num_func])",
                f"CREATE INDEX idx_docente_nome ON [{cls.TABLE_NAME}]([nome_compl])",
                f"CREATE INDEX idx_docente_email ON [{cls.TABLE_NAME}]([email])",
                f"CREATE INDEX idx_docente_depto ON [{cls.TABLE_NAME}]([depto])",
                f"CREATE INDEX idx_docente_ativo ON [{cls.TABLE_NAME}]([ativo])",
                f"CREATE INDEX idx_docente_cpf_num_func ON [{cls.TABLE_NAME}]([cpf], [num_func])",
            ]
            for idx_sql in indexes:
                try:
                    execute_query(idx_sql, database_name=cls.DB_NAME)
                except Exception as e:
                    logger.warning(f"Erro ao criar índice: {e}")

            logger.info(f"Tabela {cls.TABLE_NAME} criada com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro ao criar tabela {cls.TABLE_NAME}: {e}")
            return False

    @classmethod
    def clear_table(cls):
        try:
            sql = f"DELETE FROM [{cls.TABLE_NAME}]"
            execute_query(sql, database_name=cls.DB_NAME)
            logger.info(f"Tabela {cls.TABLE_NAME} limpa.")
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar tabela {cls.TABLE_NAME}: {e}")
            return False

    @classmethod
    def insert(cls, data: Dict) -> bool:
        try:
            cpf = cls._normalize_value(data.get('cpf'))
            num_func = cls._normalize_value(data.get('num_func'))
            if not all([cpf, num_func]):
                logger.warning(f"Docente sem campos obrigatórios: {data}")
                return False

            columns = ['cpf', 'num_func']
            values = [cpf, num_func]

            for field in cls.API_FIELDS:
                if field not in ['cpf', 'num_func']:
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
            execute_query(sql, tuple(values), database_name=cls.DB_NAME)
            return True
        except Exception as e:
            logger.error(f"Erro ao inserir docente {data.get('cpf')}/{data.get('num_func')}: {e}")
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
                    cpf = cls._normalize_value(data.get('cpf'))
                    num_func = cls._normalize_value(data.get('num_func'))
                    if not all([cpf, num_func]):
                        logger.warning(f"Docente sem campos obrigatórios: {data}")
                        errors += 1
                        continue

                    columns = ['cpf', 'num_func']
                    values = [cpf, num_func]

                    for field in cls.API_FIELDS:
                        if field not in ['cpf', 'num_func']:
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
                    logger.error(f"Erro ao inserir docente {data.get('cpf')}/{data.get('num_func')}: {e}")
                    errors += 1
            conn.commit()

        logger.info(f"Batch insert: {success} sucessos, {errors} erros, total {len(data_list)}")
        return success

    @classmethod
    def get_summary(cls) -> Dict:
        queries = {
            'total_docentes': f"SELECT COUNT(*) FROM [{cls.TABLE_NAME}]",
            'ativos': f"SELECT COUNT(*) FROM [{cls.TABLE_NAME}] WHERE [ativo] = 'S'",
            'inativos': f"SELECT COUNT(*) FROM [{cls.TABLE_NAME}] WHERE [ativo] = 'N'",
            'deptos_distintos': f"SELECT COUNT(DISTINCT [depto]) FROM [{cls.TABLE_NAME}]",
            'cpfs_distintos': f"SELECT COUNT(DISTINCT [cpf]) FROM [{cls.TABLE_NAME}]",
            'num_func_distintos': f"SELECT COUNT(DISTINCT [num_func]) FROM [{cls.TABLE_NAME}]",
            'ultima_atualizacao': f"SELECT MAX([data_atualizacao]) FROM [{cls.TABLE_NAME}]"
        }
        results = {}
        for key, q in queries.items():
            row = fetch_one(q, database_name=cls.DB_NAME)
            results[key] = row[0] if row else 0
        return results

    @classmethod
    def get_all_docentes(cls) -> List[Dict]:
        sql = f"SELECT * FROM [{cls.TABLE_NAME}] ORDER BY [nome_compl]"
        rows = fetch_all(sql, database_name=cls.DB_NAME)
        if not rows:
            return []
        col_query = """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION
        """
        col_rows = fetch_all(col_query, (cls.TABLE_NAME,), database_name=cls.DB_NAME)
        columns = [r[0] for r in col_rows]
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def get_by_cpf(cls, cpf: str) -> List[Dict]:
        sql = f"SELECT * FROM [{cls.TABLE_NAME}] WHERE [cpf] = ? ORDER BY [num_func]"
        rows = fetch_all(sql, (cpf,), database_name=cls.DB_NAME)
        if not rows:
            return []
        col_query = """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION
        """
        col_rows = fetch_all(col_query, (cls.TABLE_NAME,), database_name=cls.DB_NAME)
        columns = [r[0] for r in col_rows]
        return [dict(zip(columns, row)) for row in rows]

    @classmethod
    def get_by_depto(cls, depto: str) -> List[Dict]:
        sql = f"SELECT * FROM [{cls.TABLE_NAME}] WHERE [depto] = ? ORDER BY [nome_compl]"
        rows = fetch_all(sql, (depto,), database_name=cls.DB_NAME)
        if not rows:
            return []
        col_query = """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION
        """
        col_rows = fetch_all(col_query, (cls.TABLE_NAME,), database_name=cls.DB_NAME)
        columns = [r[0] for r in col_rows]
        return [dict(zip(columns, row)) for row in rows]