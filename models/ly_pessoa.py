#!/usr/bin/env python3
"""
models/ly_pessoa.py
Modelo para tabela LY_PESSOA usando core.database (SQL Server)
Chave primária: pessoa (código numérico)
"""

import logging
from typing import List, Dict, Any, Optional
from core.database import get_db_connection, execute_query, fetch_all, fetch_one

logger = logging.getLogger(__name__)


class LyPessoaModel:
    TABLE_NAME = "LY_PESSOA"
    DB_NAME = "lyceum"

    # Lista de campos conforme API (excluindo metadados internos e campos derivados)
    # ATUALIZADO para incluir campos do novo endpoint /v2/pessoas/idPessoa/...
    API_FIELDS = [
        # Campos originais (mantidos)
        "alist_csm", "alist_dtexp", "alist_num", "alist_rm", "alist_serie",
        "area_prof", "autoriza_envio_mail", "bairro", "cargo", "celular", "cep",
        "cert_nasc_cartorio_exped", "cert_nasc_cartorio_uf", "cert_nasc_emissao",
        "cert_nasc_folha", "cert_nasc_livro", "cert_nasc_matricula", "cert_nasc_num",
        "conselho_regional", "contribui_renda", "cor_raca", "cpf",
        "cprof_dtexp", "cprof_num", "cprof_serie", "cprof_uf",
        "cr_cat", "cr_csm", "cr_dtexp", "cr_num", "cr_rm", "cr_serie",
        "credo", "ddd_fax_res", "ddd_fone", "ddd_fone_celular", "ddd_fone_comercial",
        "ddd_fone_recado", "ddd_resp_fone", "depto_com", "divida_biblio",
        "dt_falecimento", "dt_nasc", "e_mail", "e_mail_com", "e_mail_interno",
        "end_compl", "end_correto", "end_municipio", "end_num", "end_pais",
        "endcom", "endcom_bairro", "endcom_cep", "endcom_compl", "endcom_municipio",
        "endcom_num", "endcom_pais", "endereco", "especializacao", "est_civil",
        "etnia", "fax", "fax_res", "fone", "fone_com", "fone_recados",
        "formacao_mae", "formacao_pai", "hab_tac", "hab_tac_data", "id_censo",
        "latitude", "longitude", "mailbox", "municipio_nasc", "nacionalidade",
        "necessidade_especial", "nome_abrev", "nome_compl", "nome_conjuge",
        "nome_empresa", "nome_mae", "nome_pai", "nome_social", "nr_regua",
        "num_func", "obs", "obs_cel", "obs_fax", "obs_fax_res", "obs_tel_com",
        "obs_tel_rec", "obs_tel_res", "orgao_militar", "pais_nasc", "passaporte",
        "permite_usar_imagem", "permiteacescadsemsenha", "pessoa", "pre_nome_social",
        "profissao", "qt_filhos", "renda_familiar", "renda_mensal",
        "resp_bairro", "resp_cep", "resp_cpf", "resp_email", "resp_end_compl",
        "resp_end_municipio", "resp_end_num", "resp_end_pais", "resp_endereco",
        "resp_est_civil", "resp_fone", "resp_fone_obs", "resp_municipio_nasc",
        "resp_nacionalidade", "resp_nome_compl", "resp_rg_dtexp", "resp_rg_emissor",
        "resp_rg_num", "resp_rg_tipo", "resp_rg_uf", "resp_senha", "resp_sexo",
        "rg_dtexp", "rg_emissor", "rg_num", "rg_tipo", "rg_uf",
        "senha_alterada", "senha_tac", "sexo", "stamp_atualizacao",
        "teleitor_dtexp", "teleitor_mun", "teleitor_num", "teleitor_secao",
        "teleitor_zona", "tipo_docmilitar", "tipo_sanguineo", "winusuario",

        # NOVOS CAMPOS do endpoint específico (não presentes na listagem geral)
        "ddi_fone",
        "ddi_fone_celular",
        "ddi_fone_comercial",
        "dt_criacao",          # timestamp de criação
        "loc_dif_residenc",
        "loc_zona_residenc",
        "povo_indigena",
        "resp_e_mail",         # alternativa a resp_email (ambos podem vir)
    ]

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        """Normaliza valores para inserção no banco."""
        if value is None:
            return None

        if isinstance(value, bool):
            return "S" if value else "N"

        if isinstance(value, (int, float)):
            return value

        if isinstance(value, str):
            value = value.strip()
            if value.lower() in ["null", "none", ""]:
                return None
            return value

        # Se for dict (ex: flex fields), ignoramos
        if isinstance(value, dict):
            return None

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
        """Cria a tabela LY_PESSOA no SQL Server com todos os campos atualizados."""
        if cls._table_exists():
            logger.info(f"Tabela {cls.TABLE_NAME} já existe.")
            return True

        # Definição dos campos com tipos adequados (mantendo compatibilidade)
        sql = f"""
        CREATE TABLE [{cls.TABLE_NAME}] (
            [alist_csm] NVARCHAR(50),
            [alist_dtexp] NVARCHAR(30),
            [alist_num] NVARCHAR(50),
            [alist_rm] NVARCHAR(50),
            [alist_serie] NVARCHAR(50),
            [area_prof] NVARCHAR(255),
            [autoriza_envio_mail] NVARCHAR(10),
            [bairro] NVARCHAR(100),
            [cargo] NVARCHAR(255),
            [celular] NVARCHAR(50),
            [cep] NVARCHAR(10),
            [cert_nasc_cartorio_exped] NVARCHAR(255),
            [cert_nasc_cartorio_uf] NVARCHAR(2),
            [cert_nasc_emissao] NVARCHAR(30),
            [cert_nasc_folha] NVARCHAR(20),
            [cert_nasc_livro] NVARCHAR(20),
            [cert_nasc_matricula] NVARCHAR(50),
            [cert_nasc_num] NVARCHAR(50),
            [conselho_regional] NVARCHAR(255),
            [contribui_renda] NVARCHAR(10),
            [cor_raca] NVARCHAR(50),
            [cpf] NVARCHAR(20),
            [cprof_dtexp] NVARCHAR(30),
            [cprof_num] NVARCHAR(50),
            [cprof_serie] NVARCHAR(50),
            [cprof_uf] NVARCHAR(2),
            [cr_cat] NVARCHAR(50),
            [cr_csm] NVARCHAR(50),
            [cr_dtexp] NVARCHAR(30),
            [cr_num] NVARCHAR(50),
            [cr_rm] NVARCHAR(50),
            [cr_serie] NVARCHAR(50),
            [credo] NVARCHAR(50),
            [ddd_fax_res] NVARCHAR(10),
            [ddd_fone] NVARCHAR(10),
            [ddd_fone_celular] NVARCHAR(10),
            [ddd_fone_comercial] NVARCHAR(10),
            [ddd_fone_recado] NVARCHAR(10),
            [ddd_resp_fone] NVARCHAR(10),
            [depto_com] NVARCHAR(50),
            [divida_biblio] NVARCHAR(10),
            [dt_falecimento] NVARCHAR(30),
            [dt_nasc] NVARCHAR(30),
            [e_mail] NVARCHAR(255),
            [e_mail_com] NVARCHAR(255),
            [e_mail_interno] NVARCHAR(255),
            [end_compl] NVARCHAR(255),
            [end_correto] NVARCHAR(10),
            [end_municipio] NVARCHAR(100),
            [end_num] NVARCHAR(20),
            [end_pais] NVARCHAR(50),
            [endcom] NVARCHAR(255),
            [endcom_bairro] NVARCHAR(100),
            [endcom_cep] NVARCHAR(10),
            [endcom_compl] NVARCHAR(255),
            [endcom_municipio] NVARCHAR(100),
            [endcom_num] NVARCHAR(20),
            [endcom_pais] NVARCHAR(50),
            [endereco] NVARCHAR(255),
            [especializacao] NVARCHAR(255),
            [est_civil] NVARCHAR(50),
            [etnia] NVARCHAR(50),
            [fax] NVARCHAR(50),
            [fax_res] NVARCHAR(50),
            [fone] NVARCHAR(50),
            [fone_com] NVARCHAR(50),
            [fone_recados] NVARCHAR(50),
            [formacao_mae] NVARCHAR(255),
            [formacao_pai] NVARCHAR(255),
            [hab_tac] NVARCHAR(10),
            [hab_tac_data] NVARCHAR(30),
            [id_censo] NVARCHAR(50),
            [latitude] NVARCHAR(50),
            [longitude] NVARCHAR(50),
            [mailbox] NVARCHAR(50),
            [municipio_nasc] NVARCHAR(100),
            [nacionalidade] NVARCHAR(100),
            [necessidade_especial] NVARCHAR(255),
            [nome_abrev] NVARCHAR(255),
            [nome_compl] NVARCHAR(500),
            [nome_conjuge] NVARCHAR(500),
            [nome_empresa] NVARCHAR(255),
            [nome_mae] NVARCHAR(500),
            [nome_pai] NVARCHAR(500),
            [nome_social] NVARCHAR(500),
            [nr_regua] NVARCHAR(50),
            [num_func] BIGINT,
            [obs] NVARCHAR(MAX),
            [obs_cel] NVARCHAR(MAX),
            [obs_fax] NVARCHAR(MAX),
            [obs_fax_res] NVARCHAR(MAX),
            [obs_tel_com] NVARCHAR(MAX),
            [obs_tel_rec] NVARCHAR(MAX),
            [obs_tel_res] NVARCHAR(MAX),
            [orgao_militar] NVARCHAR(255),
            [pais_nasc] NVARCHAR(100),
            [passaporte] NVARCHAR(50),
            [permite_usar_imagem] NVARCHAR(10),
            [permiteacescadsemsenha] NVARCHAR(10),
            [pessoa] BIGINT PRIMARY KEY,
            [pre_nome_social] NVARCHAR(500),
            [profissao] NVARCHAR(255),
            [qt_filhos] INT,
            [renda_familiar] DECIMAL(18,2),
            [renda_mensal] DECIMAL(18,2),
            [resp_bairro] NVARCHAR(100),
            [resp_cep] NVARCHAR(10),
            [resp_cpf] NVARCHAR(20),
            [resp_email] NVARCHAR(255),
            [resp_end_compl] NVARCHAR(255),
            [resp_end_municipio] NVARCHAR(100),
            [resp_end_num] NVARCHAR(20),
            [resp_end_pais] NVARCHAR(50),
            [resp_endereco] NVARCHAR(255),
            [resp_est_civil] NVARCHAR(50),
            [resp_fone] NVARCHAR(50),
            [resp_fone_obs] NVARCHAR(255),
            [resp_municipio_nasc] NVARCHAR(100),
            [resp_nacionalidade] NVARCHAR(100),
            [resp_nome_compl] NVARCHAR(500),
            [resp_rg_dtexp] NVARCHAR(30),
            [resp_rg_emissor] NVARCHAR(100),
            [resp_rg_num] NVARCHAR(50),
            [resp_rg_tipo] NVARCHAR(50),
            [resp_rg_uf] NVARCHAR(2),
            [resp_senha] NVARCHAR(255),
            [resp_sexo] CHAR(1),
            [rg_dtexp] NVARCHAR(30),
            [rg_emissor] NVARCHAR(100),
            [rg_num] NVARCHAR(50),
            [rg_tipo] NVARCHAR(50),
            [rg_uf] NVARCHAR(2),
            [senha_alterada] NVARCHAR(10),
            [senha_tac] NVARCHAR(255),
            [sexo] CHAR(1),
            [stamp_atualizacao] NVARCHAR(30),
            [teleitor_dtexp] NVARCHAR(30),
            [teleitor_mun] NVARCHAR(100),
            [teleitor_num] NVARCHAR(50),
            [teleitor_secao] NVARCHAR(50),
            [teleitor_zona] NVARCHAR(50),
            [tipo_docmilitar] NVARCHAR(50),
            [tipo_sanguineo] NVARCHAR(10),
            [winusuario] NVARCHAR(50),
            -- NOVOS CAMPOS
            [ddi_fone] NVARCHAR(10),
            [ddi_fone_celular] NVARCHAR(10),
            [ddi_fone_comercial] NVARCHAR(10),
            [dt_criacao] NVARCHAR(30),
            [loc_dif_residenc] NVARCHAR(50),
            [loc_zona_residenc] NVARCHAR(50),
            [povo_indigena] NVARCHAR(100),
            [resp_e_mail] NVARCHAR(255),
            -- Metadados
            [data_importacao] DATETIME2 DEFAULT GETDATE(),
            [data_atualizacao] DATETIME2 DEFAULT GETDATE()
        )
        """
        try:
            execute_query(sql, database_name=cls.DB_NAME)

            # Índices
            indexes = [
                f"CREATE INDEX idx_pessoa_cpf ON [{cls.TABLE_NAME}]([cpf])",
                f"CREATE INDEX idx_pessoa_nome ON [{cls.TABLE_NAME}]([nome_compl])",
                f"CREATE INDEX idx_pessoa_num_func ON [{cls.TABLE_NAME}]([num_func])",
                f"CREATE INDEX idx_pessoa_stamp ON [{cls.TABLE_NAME}]([stamp_atualizacao])",
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

    @classmethod
    def upsert(cls, data: Dict) -> bool:
        """Insere ou atualiza uma pessoa usando MERGE."""
        pessoa_id = cls._normalize_value(data.get("pessoa"))
        if pessoa_id is None:
            logger.warning("Registro sem campo 'pessoa' (chave primária).")
            return False

        # Mapeia campos que podem vir com nomes alternativos
        if "resp_e_mail" in data and "resp_email" not in data:
            data["resp_email"] = data["resp_e_mail"]
        # Se vier ambos, prioriza resp_email (já está na lista)

        # Lista de colunas (todos os campos da API)
        columns = cls.API_FIELDS
        values = [cls._normalize_value(data.get(col)) for col in columns]

        # Montar MERGE dinâmico
        col_list = ", ".join([f"[{col}]" for col in columns])
        param_placeholders = ", ".join(["?" for _ in columns])
        source_cols = ", ".join([f"source.[{col}]" for col in columns])

        # Update set: todos exceto a chave
        update_set = ", ".join(
            [f"target.[{col}] = source.[{col}]" for col in columns if col != "pessoa"]
        )
        if update_set:
            update_set += ", "
        update_set += "target.[data_atualizacao] = GETDATE()"

        insert_cols = f"{col_list}, [data_importacao], [data_atualizacao]"
        insert_vals = f"{source_cols}, GETDATE(), GETDATE()"

        merge_sql = f"""
            MERGE INTO [{cls.TABLE_NAME}] AS target
            USING (VALUES ({param_placeholders})) AS source ({col_list})
            ON target.[pessoa] = source.[pessoa]
            WHEN MATCHED THEN
                UPDATE SET {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals});
        """

        try:
            execute_query(merge_sql, tuple(values), database_name=cls.DB_NAME)
            logger.debug(f"Pessoa {pessoa_id} upsert realizada.")
            return True
        except Exception as e:
            logger.error(f"Erro no upsert da pessoa {pessoa_id}: {e}")
            return False

    @classmethod
    def batch_upsert(cls, data_list: List[Dict], batch_size: int = 1000) -> int:
        """
        Insere ou atualiza múltiplas pessoas em lotes.
        """
        if not data_list:
            logger.warning("Nenhum registro recebido para batch_upsert.")
            return 0

        total = len(data_list)
        total_success = 0
        total_error = 0

        columns = cls.API_FIELDS

        col_list = ", ".join([f"[{col}]" for col in columns])
        param_placeholders = ", ".join(["?" for _ in columns])
        source_cols = ", ".join([f"source.[{col}]" for col in columns])

        update_set = ", ".join(
            [f"target.[{col}] = source.[{col}]" for col in columns if col != "pessoa"]
        )
        update_set += ", target.[data_atualizacao] = GETDATE()"

        insert_cols = f"{col_list}, [data_importacao], [data_atualizacao]"
        insert_vals = f"{source_cols}, GETDATE(), GETDATE()"

        merge_sql = f"""
            MERGE INTO [{cls.TABLE_NAME}] AS target
            USING (VALUES ({param_placeholders})) AS source ({col_list})
            ON target.[pessoa] = source.[pessoa]
            WHEN MATCHED THEN
                UPDATE SET {update_set}
            WHEN NOT MATCHED THEN
                INSERT ({insert_cols})
                VALUES ({insert_vals});
        """

        logger.info(f"Iniciando batch_upsert de {total:,} registros (lotes de {batch_size})")

        with get_db_connection(database_name=cls.DB_NAME) as conn:
            cursor = conn.cursor()
            try:
                cursor.fast_executemany = True
            except Exception:
                pass

            for lote_num, inicio in enumerate(range(0, total, batch_size), start=1):
                fim = min(inicio + batch_size, total)
                lote = data_list[inicio:fim]

                sucesso_lote = 0
                erro_lote = 0

                logger.info(f"Lote {lote_num}: registros {inicio + 1:,} até {fim:,}")

                for data in lote:
                    pessoa_id = cls._normalize_value(data.get("pessoa"))
                    if pessoa_id is None:
                        erro_lote += 1
                        total_error += 1
                        continue

                    # Mapeamento de campos alternativos
                    if "resp_e_mail" in data and "resp_email" not in data:
                        data["resp_email"] = data["resp_e_mail"]

                    values = [cls._normalize_value(data.get(col)) for col in columns]

                    try:
                        cursor.execute(merge_sql, tuple(values))
                        sucesso_lote += 1
                        total_success += 1
                    except Exception as e:
                        logger.error(f"Pessoa {pessoa_id}: {e}")
                        erro_lote += 1
                        total_error += 1

                try:
                    conn.commit()
                    logger.info(f"Lote {lote_num} concluído. Sucesso={sucesso_lote:,} Erro={erro_lote:,}")
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Erro ao confirmar lote {lote_num}: {e}")

            logger.info(f"Batch finalizado | Sucesso={total_success:,} Erro={total_error:,} Total={total:,}")
            return total_success

    @classmethod
    def get_summary(cls) -> Dict:
        """Retorna estatísticas da tabela."""
        try:
            queries = {
                "total_pessoas": f"SELECT COUNT(*) FROM [{cls.TABLE_NAME}]",
                "ultima_atualizacao": f"SELECT MAX([data_atualizacao]) FROM [{cls.TABLE_NAME}]",
            }
            results = {}
            for key, query in queries.items():
                row = fetch_one(query, database_name=cls.DB_NAME)
                results[key] = row[0] if row else 0
            return results
        except Exception as e:
            logger.error(f"Erro no resumo: {e}")
            return {}