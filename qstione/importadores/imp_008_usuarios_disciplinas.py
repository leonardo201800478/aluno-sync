"""
qstione/importadores/imp_008_usuarios_disciplinas.py
Importador independente de usuários das disciplinas.

A identificação da disciplina agora é calculada por disciplina + curso
usando exatamente MAPEAMENTO_CURSOS e gerar_codigo_disciplina_curso do
imp_002_disciplina.py. Isso evita o erro anterior de escolher um único
codigoDisciplina para uma disciplina que existe em vários cursos.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import converter_minusculas, truncar_texto, gerar_codigo_disciplina_curso
from qstione.core.validacoes import validar_email
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES, FACULDADES_INCLUIDAS
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorUsuariosDisciplinas:
    """Importa usuários para cada ID real de disciplina/curso do imp_002."""

    @staticmethod
    def _normalizar_curso(curso):
        curso = str(curso).strip() if curso is not None else ''
        if curso in MAPEAMENTO_CURSOS:
            return MAPEAMENTO_CURSOS[curso][0], MAPEAMENTO_CURSOS[curso][1]
        return curso, curso

    def _tabela_existe(self):
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = 'imp_008_usuarios_disciplinas' AND TABLE_TYPE = 'BASE TABLE'
                """).fetchone() is not None
        except Exception:
            return False

    def _criar_tabela(self):
        if not self._tabela_existe():
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_008_usuarios_disciplinas (
                        codigoDisciplina NVARCHAR(30) NOT NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        status CHAR(1) NOT NULL DEFAULT 'S',
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (codigoDisciplina, emailUsuario)
                    )
                """)
                conn.commit()
                print('🆕 Tabela imp_008_usuarios_disciplinas criada.')
            self._criar_indices()
            return

        with get_db_connection(database_name='qstione') as conn:
            cols = [r[0] for r in conn.execute("""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'imp_008_usuarios_disciplinas'
            """).fetchall()]
            if 'status' not in cols:
                conn.execute("ALTER TABLE imp_008_usuarios_disciplinas ADD status CHAR(1) NOT NULL DEFAULT 'S'")
            if 'data_criacao' not in cols:
                conn.execute("ALTER TABLE imp_008_usuarios_disciplinas ADD data_criacao DATETIME2 DEFAULT GETDATE()")
            if 'data_atualizacao' not in cols:
                conn.execute("ALTER TABLE imp_008_usuarios_disciplinas ADD data_atualizacao DATETIME2 DEFAULT GETDATE()")
            conn.commit()
        self._criar_indices()

    def _criar_indices(self):
        for nome, sql in [
            ('idx_usuarios_disciplinas_email', 'CREATE INDEX idx_usuarios_disciplinas_email ON imp_008_usuarios_disciplinas(emailUsuario)'),
            ('idx_usuarios_disciplinas_codigo', 'CREATE INDEX idx_usuarios_disciplinas_codigo ON imp_008_usuarios_disciplinas(codigoDisciplina)'),
        ]:
            try:
                with get_db_connection(database_name='qstione') as conn:
                    existe = conn.execute('SELECT 1 FROM sys.indexes WHERE name = ?', (nome,)).fetchone()
                    if not existe:
                        conn.execute(sql)
                        conn.commit()
            except Exception as e:
                print(f'⚠️ Índice {nome}: {e}')

    def _obter_emails_nde_por_curso(self):
        emails = {}
        try:
            with get_db_connection(database_name='qstione') as conn:
                for curso, email in conn.execute("""
                    SELECT codigoCurso, emailCoordenador FROM imp_nde_cursos
                    WHERE emailCoordenador IS NOT NULL AND emailCoordenador != '' AND status = 'S'
                """).fetchall():
                    emails.setdefault(str(curso), set()).add(email)
                for curso, email in conn.execute("""
                    SELECT codigoCurso, emailMembro FROM imp_nde_membros
                    WHERE emailMembro IS NOT NULL AND emailMembro != '' AND status = 'S'
                """).fetchall():
                    emails.setdefault(str(curso), set()).add(email)
        except Exception as e:
            print(f'⚠️ Erro ao buscar e-mails NDE: {e}')
        return emails

    def obter_dados_lyceum(self):
        periodos_sql = ','.join('?' for _ in PERIODOS_VIGENTES)
        faculdades_sql = ','.join('?' for _ in FACULDADES_INCLUIDAS)
        periodo_principal = PERIODOS_VIGENTES[0]

        # Docentes: cada combinação disciplina/curso/e-mail é preservada.
        with get_db_connection() as conn:
            tem_curso_turma = conn.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = 'LY_TURMA' AND COLUMN_NAME = 'curso'
            """).fetchone() is not None
            curso_expr = 't.curso' if tem_curso_turma else 'g.curso'
            grade_join = '' if tem_curso_turma else 'INNER JOIN LY_GRADE g ON g.disciplina = td.disciplina'
            docentes = conn.execute(f"""
                SELECT DISTINCT td.disciplina, {curso_expr} AS curso, d.email
                FROM LY_TURMA_DOCENTE td
                INNER JOIN LY_DISCIPLINA dsc ON dsc.disciplina = td.disciplina
                INNER JOIN LY_DOCENTE d ON d.num_func = td.num_func
                {('INNER JOIN LY_TURMA t ON t.disciplina = td.disciplina AND t.turma = td.turma AND t.ano = td.ano AND t.semestre = td.periodo' if tem_curso_turma else '')}
                {grade_join}
                WHERE td.ano = ? AND td.periodo = ?
                  AND dsc.faculdade IN ({faculdades_sql}) AND d.ativo = 'S'
                  AND d.email IS NOT NULL AND d.email != ''
            """, [ANO_VIGENTE, periodo_principal, *FACULDADES_INCLUIDAS]).fetchall()

            # NDE: disciplinas e todos os cursos nos quais elas aparecem.
            grade = conn.execute(f"""
                SELECT DISTINCT td.disciplina, g.curso
                FROM LY_TURMA_DOCENTE td
                INNER JOIN LY_DISCIPLINA dsc ON dsc.disciplina = td.disciplina
                INNER JOIN LY_GRADE g ON g.disciplina = td.disciplina
                WHERE td.ano = ? AND td.periodo = ?
                  AND dsc.faculdade IN ({faculdades_sql})
            """, [ANO_VIGENTE, periodo_principal, *FACULDADES_INCLUIDAS]).fetchall()

        nde = self._obter_emails_nde_por_curso()
        resultados = set()
        for disciplina, curso, email in docentes:
            if disciplina and curso and email:
                resultados.add((disciplina, curso, email))
        for disciplina, curso in grade:
            for email in nde.get(str(curso), set()):
                if email:
                    resultados.add((disciplina, curso, email))
        return list(resultados)

    def transformar_dados(self, dados_lyceum):
        dados = []
        for disciplina, curso, email in dados_lyceum:
            if not validar_email(email):
                continue
            curso_unificado, nome_curso_unificado = self._normalizar_curso(curso)
            if not disciplina or not curso_unificado:
                continue
            codigo_disciplina = truncar_texto(
                gerar_codigo_disciplina_curso(disciplina, nome_curso_unificado, curso_unificado), 30
            )
            dados.append({
                'codigoDisciplina': codigo_disciplina,
                'emailUsuario': truncar_texto(converter_minusculas(email), 100),
            })
        unicos = {(r['codigoDisciplina'], r['emailUsuario']): r for r in dados}
        return list(unicos.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute('DELETE FROM imp_008_usuarios_disciplinas')
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_008_usuarios_disciplinas
                            (codigoDisciplina, emailUsuario, status, data_criacao, data_atualizacao)
                            VALUES (?, ?, 'S', GETDATE(), GETDATE())
                        """, (reg['codigoDisciplina'], reg['emailUsuario']))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"✗ {reg['codigoDisciplina']} - {reg['emailUsuario']}: {e}")
                conn.commit()
        except Exception as e:
            print(f'❌ Erro durante reconstrução: {e}')
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print('=' * 70)
        print('IMPORTAÇÃO: imp_008_usuarios_disciplinas')
        print('=' * 70)
        dados = self.obter_dados_lyceum()
        print(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados)
        print(f'✅ Registros únicos: {len(transformados)}')
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorUsuariosDisciplinas().executar_importacao()
