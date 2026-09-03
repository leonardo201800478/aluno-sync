
"""
Modelo para a tabela LY_ALUNO no SQL Server.
Gerencia a sincronização de alunos com a API do Lyceum.
"""

import logging
from datetime import datetime
from typing import Set, Dict, Any

from core.database import execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)


class AlunoModel:
    """Modelo responsável pelas operações da tabela LY_ALUNO."""

    TABLE = "LY_ALUNO"

    # Campos que devem ser convertidos para inteiro
    INTEGER_FIELDS = {
        "ano_ingresso",
        "anoconcl2g",
        "creditos",
        "num_chamada",
        "pessoa",
        "sem_ingresso",
        "serie",
        "dist_aluno_unidade",
    }

    # Campos booleanos armazenados como S/N
    BOOLEAN_FIELDS = {
        "representante_turma",
    }

    # Campos de data/hora
    DATETIME_FIELDS = {
        "dt_ingresso",
        "stamp_atualizacao",
    }

    @staticmethod
    def _normalize_value(key: str, value: Any) -> Any:
        """
        Normaliza um valor recebido da API antes da gravação.

        Args:
            key: Nome do campo.
            value: Valor recebido da API.

        Returns:
            Valor convertido para o tipo esperado pelo banco.
        """
        if value is None:
            return None

        # Campos inteiros
        if key in AlunoModel.INTEGER_FIELDS:
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Campos booleanos
        if key in AlunoModel.BOOLEAN_FIELDS:
            if isinstance(value, str):
                return "S" if value.strip().upper() == "S" else "N"

            return "S" if value else "N"

        # Campos de data/hora
        if key in AlunoModel.DATETIME_FIELDS:
            if isinstance(value, (int, float)):
                try:
                    # Detecta timestamp em milissegundos
                    timestamp = value / 1000 if value > 1000000000000 else value

                    return datetime.fromtimestamp(timestamp).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                except Exception:
                    return str(value)

            if isinstance(value, str):
                return value.strip()

            return None

        # Strings
        if isinstance(value, str):
            return value.strip()

        return value

    @staticmethod
    def create_table() -> None:
        """
        Cria a tabela LY_ALUNO caso ela ainda não exista.

        Também garante a existência da coluna data_sincronizacao.
        """

        exists = fetch_one(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
              AND TABLE_TYPE = 'BASE TABLE'
            """,
            (AlunoModel.TABLE,),
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

            logger.info(
                "Tabela %s criada com sucesso.",
                AlunoModel.TABLE,
            )

            return

        # Garante a existência da coluna data_sincronizacao
        col_exists = fetch_one(
            """
            SELECT 1
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = ?
              AND COLUMN_NAME = 'data_sincronizacao'
            """,
            (AlunoModel.TABLE,),
        )

        if not col_exists:
            execute_query(
                f"""
                ALTER TABLE [{AlunoModel.TABLE}]
                ADD [data_sincronizacao] DATETIME2 DEFAULT GETDATE()
                """
            )

            logger.info(
                "Coluna data_sincronizacao adicionada à tabela %s.",
                AlunoModel.TABLE,
            )

        logger.info(
            "Tabela %s já existe e está atualizada.",
            AlunoModel.TABLE,
        )

    @staticmethod
    def upsert(data: Dict[str, Any]) -> bool:
        """
        Insere ou atualiza um aluno usando MERGE.

        Args:
            data: Dicionário contendo os dados do aluno.

        Returns:
            True quando o MERGE foi executado com sucesso.
            False quando a matrícula é inválida ou ocorre erro.
        """

        matricula = data.get("aluno")

        if matricula is None or str(matricula).strip() == "":
            logger.warning(
                "Tentativa de upsert sem matrícula. Dados ignorados."
            )
            return False

        fields = [
            "aluno",
            "ano_ingresso",
            "anoconcl2g",
            "areacnpq",
            "candidato",
            "cidade2g",
            "classif_aluno",
            "cod_cartao",
            "concurso",
            "cred_educativo",
            "creditos",
            "curriculo",
            "curso",
            "curso_ant",
            "discipoutraserie",
            "dist_aluno_unidade",
            "dt_ingresso",
            "e_mail_interno",
            "faculdade_conveniada",
            "grupo",
            "instituicao",
            "nome_abrev",
            "nome_compl",
            "nome_conjuge",
            "nome_social",
            "num_chamada",
            "obs_aluno_finan",
            "obs_tel_com",
            "obs_tel_res",
            "outra_faculdade",
            "pais2g",
            "pessoa",
            "ref_aluno_ant",
            "representante_turma",
            "sem_ingresso",
            "serie",
            "sit_aluno",
            "sit_aprov",
            "stamp_atualizacao",
            "tipo_aluno",
            "tipo_escola",
            "tipo_ingresso",
            "turma_pref",
            "turno",
            "unidade_ensino",
            "unidade_fisica",
        ]

        params = {
            field: AlunoModel._normalize_value(
                field,
                data.get(field),
            )
            for field in fields
        }

        columns = list(params.keys())

        update_columns = [
            column
            for column in columns
            if column != "aluno"
        ]

        update_set = ", ".join(
            f"target.[{column}] = source.[{column}]"
            for column in update_columns
        )

        insert_columns = (
            [f"[{column}]" for column in columns]
            + ["[data_sincronizacao]"]
        )

        insert_values = (
            ", ".join(
                f"source.[{column}]"
                for column in columns
            )
            + ", GETDATE()"
        )

        placeholders = ",".join("?" for _ in columns)

        source_columns = ",".join(
            f"[{column}]"
            for column in columns
        )

        merge_sql = f"""
            MERGE INTO [{AlunoModel.TABLE}] AS target
            USING (
                VALUES ({placeholders})
            ) AS source ({source_columns})

            ON target.[aluno] = source.[aluno]

            WHEN MATCHED THEN
                UPDATE SET
                    {update_set},
                    target.[data_sincronizacao] = GETDATE()

            WHEN NOT MATCHED THEN
                INSERT (
                    {", ".join(insert_columns)}
                )
                VALUES (
                    {insert_values}
                );
        """

        try:
            execute_query(
                merge_sql,
                [params[column] for column in columns],
            )

            logger.debug(
                "Aluno %s upsert realizado com sucesso.",
                matricula,
            )

            return True

        except Exception as exc:
            logger.error(
                "Erro no upsert do aluno %s: %s",
                matricula,
                exc,
            )

            return False

    @staticmethod
    def get_all_matriculas() -> Set[str]:
        """
        Retorna todas as matrículas existentes no banco.

        Returns:
            Conjunto de matrículas como strings.
        """

        rows = fetch_all(
            f"""
            SELECT [aluno]
            FROM [{AlunoModel.TABLE}]
            """
        )

        if not rows:
            return set()

        return {
            str(row[0]).strip()
            for row in rows
            if row[0] is not None
        }

    @staticmethod
    def get_total_count() -> int:
        """
        Retorna a quantidade total de registros da tabela.

        Returns:
            Número de registros existentes.
        """

        result = fetch_one(
            f"""
            SELECT COUNT(*)
            FROM [{AlunoModel.TABLE}]
            """
        )

        return int(result[0]) if result else 0

    @staticmethod
    def delete_obsoletos(
        matriculas_ativas: Set[str],
    ) -> int:
        """
        Remove alunos que não estão mais presentes na API.

        A implementação evita o uso de NOT IN com milhares de parâmetros,
        que ultrapassa o limite de 2.100 parâmetros do SQL Server.

        Processo:

        1. Obtém todas as matrículas existentes no banco.
        2. Calcula em memória a diferença entre banco e API.
        3. Aplica proteção contra deleção em massa.
        4. Remove os registros obsoletos em lotes de até 1.000 matrículas.

        Args:
            matriculas_ativas:
                Conjunto de matrículas que continuam ativas na API.

        Returns:
            Quantidade de registros removidos.
        """

        # --------------------------------------------------------------
        # Segurança: nunca executar limpeza com lista vazia.
        # --------------------------------------------------------------
        if not matriculas_ativas:
            logger.warning(
                "Lista de matrículas ativas vazia. "
                "Nenhuma deleção será realizada."
            )
            return 0

        # --------------------------------------------------------------
        # Normaliza as matrículas recebidas.
        # --------------------------------------------------------------
        ativas_set = {
            str(matricula).strip()
            for matricula in matriculas_ativas
            if matricula is not None
            and str(matricula).strip()
        }

        if not ativas_set:
            logger.warning(
                "Nenhuma matrícula ativa válida encontrada. "
                "Nenhuma deleção será realizada."
            )
            return 0

        # --------------------------------------------------------------
        # Busca todas as matrículas atualmente existentes.
        #
        # Essa consulta não possui parâmetros e, portanto, não sofre
        # do limite de 2.100 parâmetros do SQL Server.
        # --------------------------------------------------------------
        logger.info(
            "Consultando matrículas existentes para identificar obsoletos..."
        )

        rows = fetch_all(
            f"""
            SELECT [aluno]
            FROM [{AlunoModel.TABLE}]
            """
        )

        if not rows:
            logger.info(
                "Tabela %s está vazia. Nada a deletar.",
                AlunoModel.TABLE,
            )
            return 0

        existentes_set = {
            str(row[0]).strip()
            for row in rows
            if row[0] is not None
        }

        total_no_banco = len(existentes_set)

        # --------------------------------------------------------------
        # Calcula EXATAMENTE quais registros não vieram da API.
        #
        # banco - API = obsoletos
        # --------------------------------------------------------------
        obsoletos = existentes_set - ativas_set

        obsoletos_estimados = len(obsoletos)

        logger.info(
            "Registros atualmente no banco: %d",
            total_no_banco,
        )

        logger.info(
            "Matrículas ativas recebidas da API: %d",
            len(ativas_set),
        )

        logger.info(
            "Registros obsoletos identificados: %d",
            obsoletos_estimados,
        )

        # --------------------------------------------------------------
        # Nada para remover.
        # --------------------------------------------------------------
        if not obsoletos:
            logger.info(
                "Nenhum aluno obsoleto encontrado para remoção."
            )
            return 0

        # --------------------------------------------------------------
        # Proteção contra deleção em massa.
        #
        # Mantém a mesma regra original:
        # aborta quando mais de 50% da tabela seria removida.
        # --------------------------------------------------------------
        percentual_obsoleto = (
            obsoletos_estimados / total_no_banco
            if total_no_banco
            else 0
        )

        if percentual_obsoleto > 0.5:
            logger.error(
                "⚠️ Deleção em massa detectada: %d registros seriam "
                "deletados (%.1f%% do total). Abortando por segurança.",
                obsoletos_estimados,
                percentual_obsoleto * 100,
            )

            return 0

        logger.info(
            "Removendo %d alunos obsoletos (%.1f%% do total)...",
            obsoletos_estimados,
            percentual_obsoleto * 100,
        )

        # --------------------------------------------------------------
        # DELETE em lotes.
        #
        # 1.000 parâmetros fica confortavelmente abaixo do limite de
        # 2.100 parâmetros do SQL Server.
        #
        # Importante:
        # Diferentemente da implementação anterior, cada lote contém
        # SOMENTE os registros que realmente foram identificados como
        # obsoletos.
        # --------------------------------------------------------------
        lote_tamanho = 1000
        total_removidos = 0

        obsoletos_lista = sorted(obsoletos)

        total_lotes = (
            (len(obsoletos_lista) + lote_tamanho - 1)
            // lote_tamanho
        )

        for numero_lote, inicio in enumerate(
            range(0, len(obsoletos_lista), lote_tamanho),
            start=1,
        ):
            lote = obsoletos_lista[
                inicio:inicio + lote_tamanho
            ]

            if not lote:
                continue

            placeholders = ",".join("?" for _ in lote)

            delete_sql = f"""
                DELETE FROM [{AlunoModel.TABLE}]
                WHERE [aluno] IN ({placeholders})
            """

            try:
                execute_query(
                    delete_sql,
                    tuple(lote),
                )

                total_removidos += len(lote)

                logger.info(
                    "Limpeza: lote %d/%d | removidos: %d | total: %d/%d",
                    numero_lote,
                    total_lotes,
                    len(lote),
                    total_removidos,
                    obsoletos_estimados,
                )

            except Exception:
                logger.exception(
                    "Erro ao remover lote %d/%d de alunos obsoletos.",
                    numero_lote,
                    total_lotes,
                )

                # Interrompe a limpeza para não mascarar erro de banco.
                break

        # --------------------------------------------------------------
        # Resultado final.
        # --------------------------------------------------------------
        if total_removidos:
            logger.info(
                "Total de alunos obsoletos removidos: %d",
                total_removidos,
            )

        else:
            logger.info(
                "Nenhum aluno obsoleto foi removido."
            )

        return total_removidos
