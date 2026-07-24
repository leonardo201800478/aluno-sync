#!/usr/bin/env python3
"""
models/normaliza_turmas.py
Script para normalizar o campo 'curso' da tabela LY_TURMA com base em LY_GRADE,
respeitando a regra de não atualizar turmas que possuem mais de uma turma
para a mesma disciplina, ano e semestre (pois podem ter cursos distintos).
Execução direta: python -m models.normaliza_turmas
"""

import sys
import os
import logging
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db_connection, fetch_all, execute_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

DB_NAME = "lyceum"


def obter_cursos_por_disciplina():
    """Retorna dicionário {disciplina: set(cursos)} a partir de LY_GRADE."""
    sql = """
        SELECT DISTINCT disciplina, curso
        FROM LY_GRADE
        WHERE disciplina IS NOT NULL AND curso IS NOT NULL
    """
    rows = fetch_all(sql, database_name=DB_NAME)
    resultado = {}
    for disciplina, curso in rows:
        if disciplina not in resultado:
            resultado[disciplina] = set()
        resultado[disciplina].add(curso)
    return resultado


def obter_turmas_por_disciplina_ano_semestre():
    """
    Retorna dicionário:
        (disciplina, ano, semestre) -> lista de (turma, curso_atual)
    """
    sql = """
        SELECT disciplina, ano, semestre, turma, curso
        FROM LY_TURMA
        WHERE disciplina IS NOT NULL
          AND ano IS NOT NULL
          AND semestre IS NOT NULL
          AND turma IS NOT NULL
    """
    rows = fetch_all(sql, database_name=DB_NAME)
    agrupado = defaultdict(list)
    for disciplina, ano, semestre, turma, curso in rows:
        agrupado[(disciplina, ano, semestre)].append((turma, curso))
    return agrupado


def main():
    logger.info("=" * 60)
    logger.info("INICIANDO NORMALIZAÇÃO DO CAMPO 'curso' EM LY_TURMA")
    logger.info("Regra: não atualizar turmas quando houver mais de uma turma")
    logger.info("para a mesma disciplina, ano e semestre.")
    logger.info("=" * 60)

    # 1. Obter mapeamento disciplina → cursos (LY_GRADE)
    logger.info("Obtendo disciplinas e cursos da LY_GRADE...")
    disciplina_cursos = obter_cursos_por_disciplina()
    logger.info(f"Total de disciplinas distintas em LY_GRADE: {len(disciplina_cursos)}")

    # Definir curso final para cada disciplina (compartilhada ou única)
    disciplina_para_curso = {}
    for disciplina, cursos in disciplina_cursos.items():
        if len(cursos) > 1:
            disciplina_para_curso[disciplina] = "999"
        else:
            disciplina_para_curso[disciplina] = next(iter(cursos))

    # 2. Obter turmas agrupadas por (disciplina, ano, semestre)
    logger.info("Obtendo turmas da LY_TURMA...")
    turmas_agrupadas = obter_turmas_por_disciplina_ano_semestre()
    logger.info(f"Total de grupos (disciplina, ano, semestre): {len(turmas_agrupadas)}")

    # 3. Preparar atualizações
    updates = []  # lista de (curso_novo, disciplina, ano, semestre, turma)
    ignorados = 0
    processados = 0

    for (disciplina, ano, semestre), turmas in turmas_agrupadas.items():
        # Verifica se há mais de uma turma nesse grupo
        if len(turmas) > 1:
            # Ignorar todas as turmas desse grupo (não atualizar)
            ignorados += len(turmas)
            logger.debug(f"Ignorando grupo: disciplina='{disciplina}', ano={ano}, semestre={semestre} "
                         f"com {len(turmas)} turmas (cursos podem ser distintos).")
            continue

        # Grupo com uma única turma
        turma, curso_atual = turmas[0]
        processados += 1

        # Se a disciplina não está em LY_GRADE, mantém o curso atual (não atualiza)
        if disciplina not in disciplina_para_curso:
            logger.debug(f"Disciplina '{disciplina}' não encontrada em LY_GRADE. Mantendo curso atual.")
            continue

        curso_novo = disciplina_para_curso[disciplina]
        # Se o curso já é o mesmo, não precisa atualizar
        if curso_atual == curso_novo:
            continue

        updates.append((curso_novo, disciplina, ano, semestre, turma))

    logger.info(f"Grupos com múltiplas turmas (ignorados): {ignorados} turmas")
    logger.info(f"Grupos com uma única turma: {processados} turmas")
    logger.info(f"Turmas a serem atualizadas: {len(updates)}")

    # 4. Executar atualizações
    if updates:
        logger.info("Aplicando atualizações...")
        total_atualizados = 0
        erros = 0

        with get_db_connection(database_name=DB_NAME) as conn:
            cursor = conn.cursor()
            for curso_novo, disciplina, ano, semestre, turma in updates:
                try:
                    update_sql = """
                        UPDATE LY_TURMA
                        SET curso = ?
                        WHERE disciplina = ?
                          AND ano = ?
                          AND semestre = ?
                          AND turma = ?
                    """
                    cursor.execute(update_sql, (curso_novo, disciplina, ano, semestre, turma))
                    total_atualizados += cursor.rowcount
                except Exception as e:
                    logger.error(f"Erro ao atualizar turma {turma} da disciplina {disciplina}: {e}")
                    erros += 1
            conn.commit()

        logger.info(f"Total de turmas atualizadas: {total_atualizados}")
        logger.info(f"Erros: {erros}")
    else:
        logger.info("Nenhuma atualização necessária.")

    logger.info("=" * 60)
    logger.info("NORMALIZAÇÃO CONCLUÍDA")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()