"""
qstione/importadores/imp_013_unidades_avaliacao.py
Importador independente de unidades de avaliação.

Curso e disciplina usam exatamente a mesma regra do imp_002_disciplina:
- curso original -> curso unificado via MAPEAMENTO_CURSOS;
- nome do curso unificado do próprio mapeamento;
- codigoDisciplina via gerar_codigo_disciplina_curso().
A tabela é reconstruída a cada execução.
"""

import os
import sys
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import truncar_texto, converter_inteiro, gerar_codigo_disciplina_curso
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
logger = logging.getLogger(__name__)


class ImportadorUnidadesAvaliacao:
    MAPEAMENTO_PROVA = {
        'AVF': 'Avaliação Formativa',
        'AVS': 'Avaliação Somativa',
        'AVSB': 'Avaliação Substitutiva',
        'AVD1': 'Avaliação 1',
        'AVD2': 'Avaliação 2',
        'SUBST': 'Avaliação Substitutiva',
        'AV': 'Avaliação',
    }

    @staticmethod
    def _curso_unificado(curso):
        curso = str(curso).strip() if curso is not None else ''
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))

    def _tabela_existe(self):
        with get_db_connection(database_name='qstione') as conn:
            return conn.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'imp_013_unidades_avaliacao'
            """).fetchone() is not None

    def _criar_tabela(self):
        if self._tabela_existe():
            return
        with get_db_connection(database_name='qstione') as conn:
            conn.execute("""
                CREATE TABLE imp_013_unidades_avaliacao (
                    codigoUnidade NVARCHAR(200) NOT NULL,
                    nomeUnidade NVARCHAR(64) NOT NULL,
                    codigoCurso NVARCHAR(30) NULL,
                    codigoDisciplina NVARCHAR(30) NULL,
                    ordemExibicao INT NOT NULL,
                    codigoAgrupamento NVARCHAR(200) NOT NULL,
                    data_criacao DATETIME2 DEFAULT GETDATE(),
                    data_atualizacao DATETIME2 DEFAULT GETDATE(),
                    PRIMARY KEY (codigoUnidade)
                )
            """)
            conn.commit()
        logger.info('🆕 Tabela imp_013_unidades_avaliacao criada.')

    def obter_dados_lyceum(self):
        sql = """
            SELECT p.ano, p.disciplina, p.prova, p.semestre, p.turma,
                   p.nome, p.ordem, p.classificacao, t.curso, c.nome AS nome_curso
            FROM LY_PROVA p
            INNER JOIN LY_TURMA t
                ON t.ano = p.ano AND t.semestre = p.semestre
               AND t.turma = p.turma AND t.disciplina = p.disciplina
            INNER JOIN LY_CURSO c ON c.curso = t.curso
            WHERE p.prova IS NOT NULL AND p.nome IS NOT NULL AND t.curso IS NOT NULL
            ORDER BY p.ano, p.semestre, p.turma, p.disciplina, p.prova
        """
        try:
            with get_db_connection(database_name='lyceum') as conn:
                rows = conn.execute(sql).fetchall()
            colunas = ['ano', 'disciplina', 'prova', 'semestre', 'turma', 'nome', 'ordem', 'classificacao', 'curso', 'nome_curso']
            return [dict(zip(colunas, row)) for row in rows]
        except Exception as e:
            logger.error(f'❌ Erro ao buscar LY_PROVA: {e}')
            return []

    def transformar_dados(self, dados_lyceum):
        dados = []
        for item in dados_lyceum:
            disciplina = str(item.get('disciplina') or '').strip()
            curso_original = str(item.get('curso') or '').strip()
            prova = str(item.get('prova') or '').strip()
            if not disciplina or not curso_original or not prova:
                continue

            curso_unificado, nome_curso_unificado = self._curso_unificado(curso_original)
            if not nome_curso_unificado:
                nome_curso_unificado = str(item.get('nome_curso') or curso_unificado)

            # Exatamente a mesma chamada e os mesmos dados usados no imp_002.
            codigo_disciplina = gerar_codigo_disciplina_curso(
                disciplina,
                nome_curso_unificado,
                curso_unificado
            )
            codigo_disciplina = truncar_texto(codigo_disciplina, 30)
            codigo_unidade = truncar_texto(f'{codigo_disciplina}-{prova}', 200)
            nome_unidade = truncar_texto(self.MAPEAMENTO_PROVA.get(prova, prova), 64)

            ordem = item.get('ordem')
            ordem_exibicao = converter_inteiro(ordem) if ordem is not None else 0
            if ordem_exibicao is None:
                ordem_exibicao = 0

            dados.append({
                'codigoUnidade': codigo_unidade,
                'nomeUnidade': nome_unidade,
                'codigoCurso': truncar_texto(curso_unificado, 30),
                'codigoDisciplina': codigo_disciplina,
                'ordemExibicao': ordem_exibicao,
                'codigoAgrupamento': codigo_unidade,
            })
        logger.info(f'✅ Transformados: {len(dados)} registros.')
        return dados

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute('DELETE FROM imp_013_unidades_avaliacao')
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_013_unidades_avaliacao
                            (codigoUnidade, nomeUnidade, codigoCurso, codigoDisciplina,
                             ordemExibicao, codigoAgrupamento, data_criacao, data_atualizacao)
                            VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                        """, (
                            reg['codigoUnidade'], reg['nomeUnidade'], reg['codigoCurso'],
                            reg['codigoDisciplina'], reg['ordemExibicao'], reg['codigoAgrupamento']
                        ))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        logger.error(f"Erro em {reg['codigoUnidade']}: {e}")
                conn.commit()
        except Exception as e:
            logger.error(f'❌ Erro durante reconstrução: {e}')
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        logger.info('=' * 70)
        logger.info('IMPORTAÇÃO: imp_013_unidades_avaliacao')
        logger.info('=' * 70)
        dados = self.obter_dados_lyceum()
        logger.info(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados)
        resultado = self.importar_para_qstione(transformados)
        logger.info(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorUnidadesAvaliacao().executar_importacao()
