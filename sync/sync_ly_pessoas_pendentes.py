#!/usr/bin/env python3
"""
sync/sync_ly_pessoas_pendentes.py

Sincronização de pessoas pendentes (IDs de alunos e docentes que não estão em LY_PESSOA)
usando o endpoint de listagem com filtro por PK:
/v2/tabela/pessoas?pk[pessoa]={id}

Características:
- Busca IDs de LY_ALUNO e LY_DOCENTE que não estão em LY_PESSOA
- Consulta a API para cada ID individualmente (get_pessoa_by_id)
- Acumula em lotes de 100 e faz UPSERT em lote (streaming) via batch_upsert
- Gera log de validação de CPF pós-carga (nulos, inválidos, duplicados)
- Arquivo de log: validacao_pessoas.log
"""

import os
import sys
import time
import logging
from typing import List, Dict, Any, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.api_client import get_pessoa_client
from core.database import fetch_all
from core.config import config
from models.ly_pessoa import LyPessoaModel

# ------------------------------------------------------------
# Configuração do LOG
# ------------------------------------------------------------
LOG_FILE = "validacao_pessoas.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

COLETAR_LOTE = 100
UPSERT_BATCH = 1000

# ------------------------------------------------------------
# Validação de CPF
# ------------------------------------------------------------
def is_cpf_valido(cpf: Optional[str]) -> bool:
    if not cpf:
        return False
    cpf_clean = ''.join(filter(str.isdigit, cpf))
    if len(cpf_clean) != 11:
        return False
    if cpf_clean == '0' * 11:
        return False
    return True

def validar_e_logar_cpfs(registros: List[Dict[str, Any]]) -> None:
    logger.info("=" * 60)
    logger.info("INICIANDO VALIDAÇÃO DE CPFs NA TABELA LY_PESSOA")
    logger.info("=" * 60)

    cpf_map: Dict[str, List[tuple]] = {}
    invalidos = []

    for reg in registros:
        pessoa = reg.get('pessoa')
        nome = reg.get('nome_compl')
        cpf = reg.get('cpf')

        if not is_cpf_valido(cpf):
            invalidos.append((pessoa, cpf, nome))
        else:
            cpf_clean = ''.join(filter(str.isdigit, cpf))
            cpf_map.setdefault(cpf_clean, []).append((pessoa, nome))

    if invalidos:
        logger.warning("--- CPFs INVÁLIDOS (nulos, <11 dígitos ou só zeros) ---")
        for pessoa, cpf, nome in invalidos:
            logger.warning(f"Pessoa: {pessoa} | CPF: {cpf} | Nome: {nome}")
    else:
        logger.info("Nenhum CPF inválido encontrado.")

    duplicados = {cpf: lista for cpf, lista in cpf_map.items() if len(lista) > 1}
    if duplicados:
        logger.error("--- CPFs DUPLICADOS (mesmo CPF para pessoas distintas) ---")
        for cpf, pessoas in duplicados.items():
            detalhes = ", ".join([f"ID {p} ({n})" for p, n in pessoas])
            logger.error(f"CPF: {cpf} -> {detalhes}")
    else:
        logger.info("Nenhum CPF duplicado encontrado.")

    logger.info("=" * 60)
    logger.info("VALIDAÇÃO CONCLUÍDA")
    logger.info("=" * 60)

# ------------------------------------------------------------
# IDs pendentes (ALUNO + DOCENTE)
# ------------------------------------------------------------
def obter_ids_pendentes() -> List[int]:
    """
    Retorna lista de IDs (pessoa) de LY_ALUNO ou LY_DOCENTE que NÃO estão em LY_PESSOA.
    """
    query = """
        SELECT DISTINCT pessoa FROM (
            SELECT a.pessoa FROM lyceum.dbo.LY_ALUNO a
            LEFT JOIN lyceum.dbo.LY_PESSOA p ON a.pessoa = p.pessoa
            WHERE p.pessoa IS NULL AND a.pessoa IS NOT NULL
            UNION
            SELECT d.pessoa FROM lyceum.dbo.LY_DOCENTE d
            LEFT JOIN lyceum.dbo.LY_PESSOA p ON d.pessoa = p.pessoa
            WHERE p.pessoa IS NULL AND d.pessoa IS NOT NULL
        ) AS pendentes
    """
    rows = fetch_all(query, database_name="lyceum")
    return [row[0] for row in rows] if rows else []

# ------------------------------------------------------------
# Sincronização principal
# ------------------------------------------------------------
def sincronizar_pessoas_pendentes() -> Dict[str, Any]:
    logger.info("=" * 80)
    logger.info("INICIANDO SINCRONIZAÇÃO DE PESSOAS PENDENTES (ALUNOS + DOCENTES)")
    logger.info(f"Coleta em lotes de: {COLETAR_LOTE}")
    logger.info(f"UPSERT em lotes de: {UPSERT_BATCH}")
    logger.info("=" * 80)

    inicio_execucao = time.time()

    try:
        LyPessoaModel.create_table()
        resumo_inicial = LyPessoaModel.get_summary()
        total_inicial = resumo_inicial.get("total_pessoas", 0)
        logger.info(f"Total atual na tabela: {total_inicial:,}")

        ids_pendentes = obter_ids_pendentes()

        if not ids_pendentes:
            logger.info("Nenhuma pessoa pendente para sincronizar.")
            # Valida CPFs existentes
            rows = fetch_all("SELECT pessoa, nome_compl, cpf FROM lyceum.dbo.LY_PESSOA", database_name="lyceum")
            registros = [{"pessoa": r[0], "nome_compl": r[1], "cpf": r[2]} for r in rows]
            validar_e_logar_cpfs(registros)
            return {
                "success": True,
                "total_ids": 0,
                "processados": 0,
                "tempo_total": time.time() - inicio_execucao,
            }

        total_ids = len(ids_pendentes)
        logger.info(f"Encontrados {total_ids:,} IDs pendentes (alunos + docentes).")

        client = get_pessoa_client()
        buffer_pessoas = []
        total_obtidos = 0
        total_validos = 0
        total_processados = 0
        erros_api = 0

        inicio_api_geral = time.time()

        for idx, pid in enumerate(ids_pendentes, 1):
            logger.info(f"Buscando pessoa {pid} ({idx}/{total_ids})...")
            pessoa = client.get_pessoa_by_id(pid)

            if pessoa:
                buffer_pessoas.append(pessoa)
                total_obtidos += 1
            else:
                erros_api += 1
                logger.warning(f"Falha ao obter dados para ID {pid} (possivelmente não existe na API)")

            time.sleep(config.API_DELAY_BETWEEN_REQUESTS)

            if len(buffer_pessoas) >= COLETAR_LOTE or idx == total_ids:
                if buffer_pessoas:
                    validos = []
                    invalidos = 0
                    for p in buffer_pessoas:
                        if isinstance(p, dict) and p.get("pessoa") is not None:
                            validos.append(p)
                        else:
                            invalidos += 1
                    total_validos += len(validos)
                    if invalidos:
                        logger.warning(f"Registros inválidos (sem ID) neste lote: {invalidos}")

                    if validos:
                        logger.info(f"Upsert de {len(validos)} pessoas (lote de coleta)...")
                        processados = LyPessoaModel.batch_upsert(validos, batch_size=UPSERT_BATCH)
                        total_processados += processados
                        logger.info(f"Lote processado: {processados} registros.")
                    else:
                        logger.warning("Nenhum registro válido neste lote para upsert.")

                    buffer_pessoas = []

        tempo_api_geral = time.time() - inicio_api_geral
        client.close()

        # Validação final de CPF
        rows = fetch_all("SELECT pessoa, nome_compl, cpf FROM lyceum.dbo.LY_PESSOA", database_name="lyceum")
        registros = [{"pessoa": r[0], "nome_compl": r[1], "cpf": r[2]} for r in rows]
        validar_e_logar_cpfs(registros)

        resumo_final = LyPessoaModel.get_summary()
        total_final = resumo_final.get("total_pessoas", 0)
        tempo_total = time.time() - inicio_execucao

        logger.info("=" * 80)
        logger.info("RESUMO DA SINCRONIZAÇÃO")
        logger.info("=" * 80)
        logger.info(f"Total de IDs pendentes (alunos+docentes): {total_ids:,}")
        logger.info(f"Registros obtidos da API: {total_obtidos:,}")
        logger.info(f"Erros na API: {erros_api:,}")
        logger.info(f"Registros válidos: {total_validos:,}")
        logger.info(f"Registros processados (UPSERT): {total_processados:,}")
        logger.info(f"Total antes: {total_inicial:,}")
        logger.info(f"Total depois: {total_final:,}")
        logger.info(f"Tempo de API: {tempo_api_geral:.2f}s")
        logger.info(f"Tempo total: {tempo_total:.2f}s")
        logger.info("=" * 80)

        return {
            "success": True,
            "total_ids": total_ids,
            "total_obtidos": total_obtidos,
            "validos": total_validos,
            "processados": total_processados,
            "erros_api": erros_api,
            "tempo_api": tempo_api_geral,
            "tempo_total": tempo_total,
        }

    except Exception as e:
        logger.exception(f"Erro durante sincronização: {e}")
        return {"success": False, "erro": str(e)}

# ------------------------------------------------------------
# Execução
# ------------------------------------------------------------
def run() -> Dict[str, Any]:
    return sincronizar_pessoas_pendentes()

if __name__ == "__main__":
    resultado = run()
    sys.exit(0 if resultado.get("success") else 1)