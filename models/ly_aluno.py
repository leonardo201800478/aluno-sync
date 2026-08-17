# models/ly_aluno.py
"""
Modelo para a tabela LY_ALUNO no SQL Server.
Gerencia a sincronização de alunos com a API do Lyceum.
"""

import logging
from datetime import datetime
from typing import Optional, Set, List, Dict, Any, Union

from core.database import execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)


class AlunoModel:
    TABLE = "LY_ALUNO"

    # Campos que devem ser convertidos para inteiro
    INTEGER_FIELDS = {
        'ano_ingresso', 'anoconcl2g', 'creditos', 'num_chamada',
        'pessoa', 'sem_ingresso', 'serie', 'dist_aluno_unidade'
    }

    # Campos booleanos (armazenados como 'S'/'N')
    BOOLEAN_FIELDS = {'representante_turma'}

    # Campos de data/hora (timestamp ou string)
    DATETIME_FIELDS = {'dt_ingresso', 'stamp_atualizacao'}

    @staticmethod
    def _normalize_value(key: str, value: Any) -> Any:
        """
        Normaliza um valor para inserção no banco de dados.
        Trata tipos específicos e converte quando necessário.
        """
        if value is None:
            return None

        # Converte para inteiro se for um campo numérico
        if key in AlunoModel.INTEGER_FIELDS:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Converte booleano para 'S'/'N'
        if key in AlunoModel.BOOLEAN_FIELDS:
            if isinstance(value, str):
                return 'S' if value.upper() == 'S' else 'N'
            return 'S' if value else 'N'

        # Converte timestamp para string ISO
        if key in AlunoModel.DATETIME_FIELDS:
            if isinstance(value, (int, float)):
                try:
                    # Verifica se é milissegundos
                    if value > 1000000000000:
                        timestamp = value / 1000
                    else:
                        timestamp = value
                    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    return str(value)
            if isinstance(value, str):
                return value.strip()
            return None

        # Strings: remove espaços extras
        if isinstance(value, str):
            return value.strip()

        return value

    @staticmethod
    def create_table() -> None:
        """
        Cria a tabela LY_ALUNO se não existir.
        Adiciona coluna 'data_sincronizacao' se ausente.
        """
        # Verifica existência da tabela
        exists = fetch_one(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'",
            (AlunoModel.TABLE,)
        )

        if not exists:
            create_sql = f"""
                CREATE TABLE [{AlunoModel.TABLE}] (
                    [aluno] NVARCHAR(100) PRIMARY KEY,
                    [ano_ingresso] BIGINT,
                    [anoconcl2g] BIGINT,
                    [areacnpq] NVARCHAR(255),
                    [candidato] NVARCHAR(100),
                    [cidade2g] NVARCHAR(255),
                    [classif_aluno] NVARCHAR(100),
                    [cod_cartao] NVARCHAR(100),
                    [concurso] NVARCHAR(100),
                    [cred_educativo] NVARCHAR(50),
                    [creditos] BIGINT,
                    [curriculo] NVARCHAR(50),
                    [curso] NVARCHAR(100),
                    [curso_ant] NVARCHAR(255),
                    [discipoutraserie] NVARCHAR(20),
                    [dist_aluno_unidade] BIGINT,
                    [dt_ingresso] NVARCHAR(30),
                    [e_mail_interno] NVARCHAR(255),
                    [faculdade_conveniada] NVARCHAR(50),
                    [grupo] NVARCHAR(50),
                    [instituicao] NVARCHAR(200),
                    [nome_abrev] NVARCHAR(200),
                    [nome_compl] NVARCHAR(500),
                    [nome_conjuge] NVARCHAR(500),
                    [nome_social] NVARCHAR(500),
                    [num_chamada] BIGINT,
                    [obs_aluno_finan] NVARCHAR(MAX),
                    [obs_tel_com] NVARCHAR(MAX),
                    [obs_tel_res] NVARCHAR(MAX),
                    [outra_faculdade] NVARCHAR(100),
                    [pais2g] NVARCHAR(255),
                    [pessoa] BIGINT,
                    [ref_aluno_ant] NVARCHAR(100),
                    [representante_turma] CHAR(1),
                    [sem_ingresso] BIGINT,
                    [serie] BIGINT,
                    [sit_aluno] NVARCHAR(50),
                    [sit_aprov] NVARCHAR(50),
                    [stamp_atualizacao] NVARCHAR(30),
                    [tipo_aluno] NVARCHAR(50),
                    [tipo_escola] NVARCHAR(50),
                    [tipo_ingresso] NVARCHAR(50),
                    [turma_pref] NVARCHAR(50),
                    [turno] NVARCHAR(20),
                    [unidade_ensino] NVARCHAR(100),
                    [unidade_fisica] NVARCHAR(100),
                    [data_sincronizacao] DATETIME2 DEFAULT GETDATE()
                )
            """
            execute_query(create_sql)
            logger.info(f"Tabela {AlunoModel.TABLE} criada com sucesso.")
        else:
            # Garante que a coluna data_sincronizacao exista
            col_exists = fetch_one(
                "SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ? AND COLUMN_NAME = 'data_sincronizacao'",
                (AlunoModel.TABLE,)
            )
            if not col_exists:
                execute_query(f"ALTER TABLE [{AlunoModel.TABLE}] ADD [data_sincronizacao] DATETIME2 DEFAULT GETDATE()")
                logger.info(f"Coluna data_sincronizacao adicionada à tabela {AlunoModel.TABLE}")
            logger.info(f"Tabela {AlunoModel.TABLE} já existe e está atualizada.")

    @staticmethod
    def upsert(data: Dict[str, Any]) -> bool:
        """
        Insere ou atualiza um aluno usando MERGE.
        Retorna True se bem-sucedido, False caso contrário.
        """
        matricula = data.get("aluno")
        if not matricula:
            logger.warning("Tentativa de upsert sem matrícula. Dados ignorados.")
            return False

        # Normaliza todos os campos
        fields = [
            "aluno", "ano_ingresso", "anoconcl2g", "areacnpq", "candidato",
            "cidade2g", "classif_aluno", "cod_cartao", "concurso",
            "cred_educativo", "creditos", "curriculo", "curso", "curso_ant",
            "discipoutraserie", "dist_aluno_unidade", "dt_ingresso",
            "e_mail_interno", "faculdade_conveniada", "grupo", "instituicao",
            "nome_abrev", "nome_compl", "nome_conjuge", "nome_social",
            "num_chamada", "obs_aluno_finan", "obs_tel_com", "obs_tel_res",
            "outra_faculdade", "pais2g", "pessoa", "ref_aluno_ant",
            "representante_turma", "sem_ingresso", "serie", "sit_aluno",
            "sit_aprov", "stamp_atualizacao", "tipo_aluno", "tipo_escola",
            "tipo_ingresso", "turma_pref", "turno", "unidade_ensino",
            "unidade_fisica"
        ]

        params = {field: AlunoModel._normalize_value(field, data.get(field)) for field in fields}

        # Colunas e valores
        columns = list(params.keys())
        update_columns = [c for c in columns if c != "aluno"]

        # Constroi o MERGE
        update_set = ", ".join([f"target.[{col}] = source.[{col}]" for col in update_columns])
        insert_cols = [f"[{col}]" for col in columns] + ["[data_sincronizacao]"]
        insert_vals = ", ".join([f"source.[{col}]" for col in columns]) + ", GETDATE()"

        merge_sql = f"""
            MERGE INTO [{AlunoModel.TABLE}] AS target
            USING (VALUES ({','.join(['?' for _ in columns])})) AS source ({','.join([f"[{col}]" for col in columns])})
            ON target.[aluno] = source.[aluno]
            WHEN MATCHED THEN
                UPDATE SET {update_set}, target.[data_sincronizacao] = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT ({', '.join(insert_cols)}) VALUES ({insert_vals});
        """

        try:
            execute_query(merge_sql, [params[col] for col in columns])
            logger.debug(f"Aluno {matricula} upsert realizado com sucesso.")
            return True
        except Exception as e:
            logger.error(f"Erro no upsert do aluno {matricula}: {e}")
            return False

    @staticmethod
    def get_all_matriculas() -> Set[str]:
        """Retorna todas as matrículas existentes no banco como um set de strings."""
        rows = fetch_all(f"SELECT [aluno] FROM [{AlunoModel.TABLE}]")
        return {row[0] for row in rows} if rows else set()

    @staticmethod
    def get_total_count() -> int:
        """Retorna o número total de registros na tabela."""
        result = fetch_one(f"SELECT COUNT(*) FROM [{AlunoModel.TABLE}]")
        return result[0] if result else 0

    @staticmethod
    def delete_obsoletos(matriculas_ativas: Set[str]) -> int:
        """
        Remove alunos que não estão mais na API.
        Proteção contra deleção em massa: aborta se mais de 50% dos registros forem obsoletos.
        Retorna o número de registros deletados.
        """
        if not matriculas_ativas:
            logger.warning("Lista de matrículas ativas vazia. Nenhuma deleção será realizada.")
            return 0

        total_no_banco = AlunoModel.get_total_count()
        if total_no_banco == 0:
            logger.info("Tabela já está vazia. Nada a deletar.")
            return 0

        # Converte para lista de strings e ordena
        ativas_lista = sorted(str(m) for m in matriculas_ativas)

        # Estima quantos seriam deletados (apenas para proteção)
        placeholders_est = ','.join(['?' for _ in ativas_lista])
        count_sql = f"""
            SELECT COUNT(*) FROM [{AlunoModel.TABLE}]
            WHERE [aluno] NOT IN ({placeholders_est})
        """
        obsoletos_estimados = fetch_one(count_sql, tuple(ativas_lista))
        obsoletos_estimados = obsoletos_estimados[0] if obsoletos_estimados else 0

        # Proteção: se mais de 50% dos registros forem obsoletos, aborta
        if obsoletos_estimados > 0.5 * total_no_banco:
            logger.error(
                f"⚠️ Deleção em massa detectada: {obsoletos_estimados} registros seriam deletados "
                f"({obsoletos_estimados/total_no_banco:.1%} do total). Abortando para segurança."
            )
            return 0

        logger.info(f"Removendo {obsoletos_estimados} alunos obsoletos...")

        # Processa em lotes de 1000
        lote_tamanho = 1000
        total_removidos = 0

        for i in range(0, len(ativas_lista), lote_tamanho):
            lote = ativas_lista[i:i + lote_tamanho]
            placeholders = ','.join(['?' for _ in lote])
            params = tuple(lote)

            # Seleciona os obsoletos do lote
            select_sql = f"""
                SELECT [aluno] FROM [{AlunoModel.TABLE}]
                WHERE [aluno] NOT IN ({placeholders})
            """
            obsoletos_lote = fetch_all(select_sql, params)

            if obsoletos_lote:
                delete_sql = f"""
                    DELETE FROM [{AlunoModel.TABLE}]
                    WHERE [aluno] NOT IN ({placeholders})
                """
                execute_query(delete_sql, params)
                total_removidos += len(obsoletos_lote)
                logger.debug(f"Lote {i//lote_tamanho + 1}: removidos {len(obsoletos_lote)} alunos.")
                # Mostra alguns exemplos
                for aluno in obsoletos_lote[:3]:
                    logger.debug(f"  - Removido: {aluno[0]}")
                if len(obsoletos_lote) > 3:
                    logger.debug(f"  ... e mais {len(obsoletos_lote) - 3} alunos")

        if total_removidos:
            logger.info(f"Total de alunos obsoletos removidos: {total_removidos}")
        else:
            logger.info("Nenhum aluno obsoleto encontrado para remoção.")

        return total_removidos