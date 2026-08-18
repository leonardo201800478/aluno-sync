"""
qstione/importadores/imp_009_professores_ofertas.py
Importador independente para imp_009_professores_ofertas.

O codigoOferta permanece exatamente o mesmo usado pelo imp_005_ofertas.
O e-mail do professor é sempre obtido de LY_DOCENTE.mailbox.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import gerar_codigo_oferta, converter_minusculas, truncar_texto
from qstione.core.validacoes import validar_email, validar_codigo_disciplina
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES, FACULDADES_INCLUIDAS, AREAS_CONHECIMENTO_INCLUIDAS, SITUACAO_TURMA_VALIDA
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorProfessoresOfertas:
    """Importa professores das ofertas e reconstrói a tabela em cada execução."""

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
        if self._tabela_existe('imp_009_professores_ofertas'):
            return
        with get_db_connection(database_name='qstione') as conn:
            conn.execute("""
                CREATE TABLE imp_009_professores_ofertas (
                    codigoOferta NVARCHAR(30) NOT NULL,
                    emailProfessor NVARCHAR(100) NOT NULL,
                    data_criacao DATETIME2 DEFAULT GETDATE(),
                    data_atualizacao DATETIME2 DEFAULT GETDATE(),
                    PRIMARY KEY (codigoOferta, emailProfessor)
                )
            """)
            conn.execute("CREATE INDEX idx_professores_ofertas_email ON imp_009_professores_ofertas(emailProfessor)")
            conn.execute("CREATE INDEX idx_professores_ofertas_codigo ON imp_009_professores_ofertas(codigoOferta)")
            conn.commit()
            print('🆕 Tabela imp_009_professores_ofertas criada.')

    @staticmethod
    def _curso_unificado(curso):
        curso = str(curso).strip() if curso is not None else ''
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))[0]

    def obter_dados_lyceum(self):
        periodos = ','.join('?' for _ in PERIODOS_VIGENTES)
        faculdades = ','.join('?' for _ in FACULDADES_INCLUIDAS)
        areas = [a for a in AREAS_CONHECIMENTO_INCLUIDAS if a not in (None, '')]
        areas_sql = ','.join('?' for _ in areas)

        with get_db_connection() as conn:
            query = f"""
                SELECT DISTINCT
                    t.disciplina, t.turma, t.ano, t.semestre, d.mailbox, t.curso
                FROM LY_TURMA t
                INNER JOIN LY_DISCIPLINA dsc ON dsc.disciplina = t.disciplina
                INNER JOIN LY_TURMA_DOCENTE td
                    ON td.disciplina = t.disciplina AND td.turma = t.turma
                   AND td.ano = t.ano AND td.periodo = t.semestre
                INNER JOIN LY_DOCENTE d ON d.num_func = td.num_func
                WHERE t.ano = ?
                  AND t.semestre IN ({periodos})
                  AND t.sit_turma = ?
                  AND dsc.faculdade IN ({faculdades})
                  AND (dsc.area_conhecimento IN ({areas_sql}) OR dsc.area_conhecimento IS NULL OR dsc.area_conhecimento = '')
                  AND d.ativo = 'S'
                  AND d.mailbox IS NOT NULL AND d.mailbox != ''
                ORDER BY t.disciplina, t.turma, d.mailbox
            """
            params = [ANO_VIGENTE, *PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA, *FACULDADES_INCLUIDAS, *areas]
            return conn.execute(query, params).fetchall()

    def transformar_dados(self, dados_lyceum):
        resultado = []
        for disciplina, turma, ano, semestre, email, curso in dados_lyceum:
            if not validar_codigo_disciplina(disciplina) or not validar_email(email):
                continue
            curso_unificado = self._curso_unificado(curso)
            codigo_oferta = truncar_texto(gerar_codigo_oferta(disciplina, turma, ano, semestre), 30)
            resultado.append({
                'codigoOferta': codigo_oferta,
                'emailProfessor': truncar_texto(converter_minusculas(email), 100),
                'codigoCurso': truncar_texto(curso_unificado, 30),
            })
        unicos = {}
        for reg in resultado:
            unicos[(reg['codigoOferta'], reg['emailProfessor'])] = reg
        return list(unicos.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute('DELETE FROM imp_009_professores_ofertas')
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_009_professores_ofertas
                            (codigoOferta, emailProfessor, data_criacao, data_atualizacao)
                            VALUES (?, ?, GETDATE(), GETDATE())
                        """, (reg['codigoOferta'], reg['emailProfessor']))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"✗ {reg['codigoOferta']} - {reg['emailProfessor']}: {e}")
                conn.commit()
        except Exception as e:
            print(f'❌ Erro durante reconstrução: {e}')
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print('=' * 70)
        print('IMPORTAÇÃO: imp_009_professores_ofertas')
        print('=' * 70)
        dados = self.obter_dados_lyceum()
        print(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados)
        print(f'✅ Registros únicos: {len(transformados)}')
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorProfessoresOfertas().executar_importacao()
