"""
qstione/importadores/imp_007_usuarios_cursos.py
Importador independente para imp_007_usuarios_cursos.

O código de curso segue exatamente o mapeamento utilizado por
imp_002_disciplina.py. A tabela destino é limpa antes de cada carga.
"""

import os
import sys

# Permite executar diretamente pelo Play do VS Code, independentemente do cwd.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import converter_minusculas, determinar_papel_usuario
from qstione.core.validacoes import validar_codigo_curso, validar_email, validar_papel_usuario
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorUsuariosCursos:
    """Importa professores/coordenadores por curso usando o código de curso unificado."""

    def _tabela_existe(self, nome_tabela: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,)).fetchone() is not None
        except Exception as e:
            print(f"⚠️ Erro ao verificar tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,)).fetchone() is not None
        except Exception:
            return False

    def _criar_tabela(self):
        if not self._tabela_existe('imp_007_usuarios_cursos'):
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_007_usuarios_cursos (
                        codigoCurso NVARCHAR(30) NOT NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        papelUsuario NVARCHAR(1) NOT NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (codigoCurso, emailUsuario)
                    )
                """)
                conn.commit()
                print("🆕 Tabela imp_007_usuarios_cursos criada.")

        indices = [
            ('idx_usuarios_cursos_email', "CREATE INDEX idx_usuarios_cursos_email ON imp_007_usuarios_cursos(emailUsuario)"),
            ('idx_usuarios_cursos_curso', "CREATE INDEX idx_usuarios_cursos_curso ON imp_007_usuarios_cursos(codigoCurso)"),
            ('idx_usuarios_cursos_papel', "CREATE INDEX idx_usuarios_cursos_papel ON imp_007_usuarios_cursos(papelUsuario)"),
        ]
        for nome, sql in indices:
            if not self._indice_existe(nome):
                try:
                    with get_db_connection(database_name='qstione') as conn:
                        conn.execute(sql)
                        conn.commit()
                except Exception as e:
                    print(f"⚠️ Índice {nome}: {e}")

    @staticmethod
    def _curso_unificado(curso):
        """Aplica exatamente MAPEAMENTO_CURSOS do imp_002_disciplina.py."""
        curso = str(curso).strip() if curso is not None else ''
        if curso in MAPEAMENTO_CURSOS:
            return MAPEAMENTO_CURSOS[curso][0]
        return curso

    def obter_coordenadores(self):
        with get_db_connection() as conn:
            rows = conn.execute("SELECT DISTINCT num_func, curso FROM LY_COORDENACAO").fetchall()
        coordenadores = {}
        for num_func, curso in rows:
            curso = self._curso_unificado(curso)
            coordenadores[(str(num_func), str(curso))] = True
        print(f"📋 Coordenadores encontrados: {len(coordenadores)}")
        return coordenadores

    def obter_dados_lyceum(self):
        coordenadores = self.obter_coordenadores()
        periodo_principal = PERIODOS_VIGENTES[0]
        with get_db_connection() as conn:
            rows = conn.execute("""
                SELECT DISTINCT td.num_func, d.email, g.curso
                FROM LY_TURMA_DOCENTE td
                INNER JOIN LY_GRADE g ON g.disciplina = td.disciplina
                INNER JOIN LY_DOCENTE d ON d.num_func = td.num_func
                WHERE td.ano = ? AND td.periodo = ? AND d.ativo = 'S'
                ORDER BY td.num_func, g.curso
            """, (ANO_VIGENTE, periodo_principal)).fetchall()
        return rows, coordenadores

    def transformar_dados(self, dados_lyceum, coordenadores):
        registros_unicos = {}
        for num_func, email, curso in dados_lyceum:
            curso = self._curso_unificado(curso)
            if not validar_codigo_curso(curso):
                print(f"⚠️ Código de curso inválido: {curso} para docente {num_func}")
                continue
            if not validar_email(email):
                print(f"⚠️ Email inválido: {email} para docente {num_func}")
                continue

            email_final = converter_minusculas(email)[:100]
            chave = (curso[:30], email_final)
            papel = determinar_papel_usuario(num_func, curso, coordenadores)
            if not validar_papel_usuario(papel):
                continue

            if chave not in registros_unicos or (papel == 'C' and registros_unicos[chave]['papelUsuario'] == 'P'):
                registros_unicos[chave] = {
                    'codigoCurso': curso[:30],
                    'emailUsuario': email_final,
                    'papelUsuario': papel,
                }
        return list(registros_unicos.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                # Reconstrução completa: só limpa depois que a nova carga foi preparada.
                conn.execute("DELETE FROM imp_007_usuarios_cursos")
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_007_usuarios_cursos
                            (codigoCurso, emailUsuario, papelUsuario, data_criacao, data_atualizacao)
                            VALUES (?, ?, ?, GETDATE(), GETDATE())
                        """, (reg['codigoCurso'], reg['emailUsuario'], reg['papelUsuario']))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"✗ {reg['codigoCurso']} - {reg['emailUsuario']}: {e}")
                conn.commit()
        except Exception as e:
            print(f"❌ Erro durante reconstrução: {e}")
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print('=' * 70)
        print('IMPORTAÇÃO: imp_007_usuarios_cursos')
        print('=' * 70)
        dados, coordenadores = self.obter_dados_lyceum()
        print(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados, coordenadores)
        print(f'✅ Registros únicos: {len(transformados)}')
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorUsuariosCursos().executar_importacao()
