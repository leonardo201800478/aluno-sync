"""
qstione/importadores/imp_011_alunos_ofertas.py
Importador independente para alunos das ofertas.

O codigoCurso segue exatamente MAPEAMENTO_CURSOS do imp_002_disciplina.py.
O codigoOferta continua sendo gerado com a mesma função usada no imp_005,
garantindo que as tabelas de ofertas permaneçam relacionadas.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import gerar_codigo_oferta, truncar_texto
from qstione.core.validacoes import validar_matricula, validar_codigo_curso
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorAlunosOfertas:
    """Importa alunos das ofertas e reconstrói a tabela a cada execução."""

    @staticmethod
    def _curso_unificado(curso):
        curso = str(curso).strip() if curso is not None else ''
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))[0]

    def _tabela_existe(self, nome_tabela):
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,)).fetchone() is not None
        except Exception:
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_011_alunos_ofertas'):
            return True
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_011_alunos_ofertas (
                        codigoOferta NVARCHAR(30) NOT NULL,
                        matriculaAluno NVARCHAR(20) NOT NULL,
                        codigoCurso NVARCHAR(30) NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (codigoOferta, matriculaAluno)
                    )
                """)
                conn.execute("CREATE INDEX idx_alunos_ofertas_matricula ON imp_011_alunos_ofertas(matriculaAluno)")
                conn.execute("CREATE INDEX idx_alunos_ofertas_curso ON imp_011_alunos_ofertas(codigoCurso) WHERE codigoCurso IS NOT NULL")
                conn.commit()
            print('🆕 Tabela imp_011_alunos_ofertas criada.')
            return True
        except Exception as e:
            print(f'❌ Erro ao criar tabela: {e}')
            return False

    def obter_dados_lyceum(self):
        periodos = ','.join('?' for _ in PERIODOS_VIGENTES)
        with get_db_connection() as conn:
            return conn.execute(f"""
                SELECT DISTINCT
                    m.aluno, m.ano, m.semestre, m.turma, m.disciplina, a.curso
                FROM LY_MATRICULA m
                INNER JOIN LY_TURMA t
                    ON m.ano = t.ano AND m.semestre = t.semestre
                   AND m.turma = t.turma AND m.disciplina = t.disciplina
                INNER JOIN LY_ALUNO a ON m.aluno = a.aluno
                WHERE m.ano = ?
                  AND m.semestre IN ({periodos})
                  AND t.sit_turma = ?
                ORDER BY m.aluno, m.ano, m.semestre, m.turma, m.disciplina
            """, [ANO_VIGENTE, *PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA]).fetchall()

    def transformar_dados(self, dados_lyceum):
        unicos = {}
        for aluno, ano, semestre, turma, disciplina, curso in dados_lyceum:
            if not validar_matricula(aluno):
                continue
            curso_unificado = self._curso_unificado(curso)
            if curso_unificado and not validar_codigo_curso(curso_unificado):
                print(f'⚠️ Código de curso inválido: {curso} -> {curso_unificado}')
                continue
            codigo_oferta = truncar_texto(gerar_codigo_oferta(disciplina, turma, ano, semestre), 30)
            matricula = truncar_texto(aluno, 20)
            unicos[(codigo_oferta, matricula)] = {
                'codigoOferta': codigo_oferta,
                'matriculaAluno': matricula,
                'codigoCurso': truncar_texto(curso_unificado, 30) if curso_unificado else None,
            }
        return list(unicos.values())

    def importar_para_qstione(self, dados_transformados):
        if not self._criar_tabela():
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute('DELETE FROM imp_011_alunos_ofertas')
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_011_alunos_ofertas
                            (codigoOferta, matriculaAluno, codigoCurso, data_criacao, data_atualizacao)
                            VALUES (?, ?, ?, GETDATE(), GETDATE())
                        """, (reg['codigoOferta'], reg['matriculaAluno'], reg['codigoCurso']))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"✗ {reg['codigoOferta']} - {reg['matriculaAluno']}: {e}")
                conn.commit()
        except Exception as e:
            print(f'❌ Erro durante reconstrução: {e}')
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print('=' * 70)
        print('IMPORTAÇÃO: imp_011_alunos_ofertas')
        print('=' * 70)
        dados = self.obter_dados_lyceum()
        print(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados)
        print(f'✅ Registros únicos: {len(transformados)}')
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorAlunosOfertas().executar_importacao()
