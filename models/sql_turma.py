#!/usr/bin/env python3
"""
models/sql_turma.py
Modelo para consulta direta à tabela LY_TURMA no SQL Server (sem API)
"""

import logging
from typing import List, Dict, Any, Optional
from core.database import fetch_all

logger = logging.getLogger(__name__)


class SQLTurmaModel:
    TABLE_NAME = "LY_TURMA"
    DB_NAME = "lyceum"

    @classmethod
    def get_turmas_abertas(cls, unidades: List[str] = None) -> List[Dict[str, Any]]:
        """
        Retorna turmas com situação 'Aberta' diretamente da tabela LY_TURMA.
        Opcionalmente, filtra por unidades responsáveis.
        Retorna dicionários com: ano, disciplina, semestre, turma, curso, unidade_responsavel.
        """
        sql = f"""
            SELECT 
                [ano],
                [disciplina],
                [semestre],
                [turma],
                [curso],
                [unidade_responsavel]
            FROM [{cls.TABLE_NAME}]
            WHERE sit_turma = 'Aberta'
            AND unidade_responsavel = '001'
            AND ano = 2026
            AND semestre = 2
        """
        params = []
        if unidades:
            placeholders = ','.join(['?' for _ in unidades])
            sql += f" AND unidade_responsavel IN ({placeholders})"
            params.extend(unidades)

        sql += " ORDER BY ano, semestre, turma, disciplina"

        try:
            rows = fetch_all(sql, tuple(params), database_name=cls.DB_NAME)
            result = []
            for row in rows:
                result.append({
                    'ano': row[0],
                    'disciplina': row[1],
                    'semestre': row[2],
                    'turma': row[3],
                    'curso': row[4],
                    'unidade_responsavel': row[5],
                })
            logger.info(f"Encontradas {len(result)} turmas abertas.")
            return result
        except Exception as e:
            logger.error(f"Erro ao buscar turmas abertas: {e}")
            return []