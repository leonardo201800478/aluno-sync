"""
qstione/importadores/imp_010_alunos.py
Importador para tabela imp_010_alunos.

Somente alunos que possuem matrícula em imp_011_alunos_ofertas são
importados. Assim, a população de alunos fica limitada aos matriculados
nas ofertas vigentes de 2026.2.
"""

import argparse
import os
import sys

# Permite executar diretamente pelo botão Play do VS Code, independentemente do cwd.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import truncar_texto, converter_minusculas, mapear_turno
from qstione.core.validacoes import validar_matricula, validar_nome, validar_codigo_curso


class ImportadorAlunos:
    def __init__(self, ano=None, semestre=None, unidade=None):
        self.ano = ano
        self.semestre = semestre
        self.unidade = unidade

    def _tabela_existe(self, nome_tabela: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,)).fetchone() is not None
        except Exception as e:
            print(f"  ⚠️  Erro ao verificar existência da tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,)).fetchone() is not None
        except Exception as e:
            print(f"  ⚠️  Erro ao verificar índice: {e}")
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_010_alunos'):
            return
        print("🆕 Criando tabela imp_010_alunos...")
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_010_alunos (
                        matriculaAluno NVARCHAR(20) NOT NULL,
                        nomeAluno NVARCHAR(140) NOT NULL,
                        emailAluno NVARCHAR(100) NULL,
                        codigoCurso NVARCHAR(30) NOT NULL,
                        turno NVARCHAR(1) NULL,
                        codigoIdentificacaoAVA NVARCHAR(100) NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (matriculaAluno)
                    )
                """)
                conn.commit()
            print("✅ Tabela criada.")
        except Exception as e:
            print(f"❌ Erro ao criar tabela: {e}")
            return

        if not self._indice_existe('idx_alunos_curso'):
            try:
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute("CREATE INDEX idx_alunos_curso ON imp_010_alunos(codigoCurso)")
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Índice idx_alunos_curso não pôde ser criado: {e}")

    def _limpar_tabela(self):
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("TRUNCATE TABLE imp_010_alunos")
                conn.commit()
                print("🧹 Tabela imp_010_alunos esvaziada com sucesso.")
        except Exception as e:
            print(f"⚠️ TRUNCATE falhou ({e}), tentando DELETE...")
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("DELETE FROM imp_010_alunos")
                conn.commit()
                print("🧹 Tabela imp_010_alunos esvaziada via DELETE.")

    def obter_dados_lyceum(self):
        """Obtém somente alunos ativos presentes em imp_011_alunos_ofertas."""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT DISTINCT
                    a.aluno,
                    a.nome_compl,
                    a.unidade_ensino,
                    a.curso,
                    a.turno
                FROM LY_ALUNO a
                INNER JOIN qstione.dbo.imp_011_alunos_ofertas ao
                    ON ao.matriculaAluno = a.aluno
                WHERE a.sit_aluno = 'Ativo'
            """
            params = []
            if self.ano is not None:
                query += " AND a.ano_ingresso = ?"
                params.append(self.ano)
            if self.semestre is not None:
                query += " AND a.sem_ingresso = ?"
                params.append(self.semestre)
            if self.unidade is not None:
                query += " AND a.unidade_ensino = ?"
                params.append(self.unidade)
            query += " ORDER BY a.aluno"
            cursor.execute(query, params)
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        dados_transformados = []
        for aluno, nome_compl, unidade_ensino, curso, turno in dados_lyceum:
            if not validar_matricula(aluno):
                print(f"  ⚠️ Matrícula inválida: {aluno}")
                continue
            if not validar_nome(nome_compl):
                print(f"  ⚠️ Nome inválido para aluno {aluno}: {nome_compl}")
                continue
            if not validar_codigo_curso(curso):
                print(f"  ⚠️ Código de curso inválido: {curso} para aluno {aluno}")
                continue

            dominio = '@etecfoa.com.br' if unidade_ensino == '007' else '@unifoa.edu.br'
            email_aluno = truncar_texto(converter_minusculas(f"{aluno}{dominio}"), 100)

            dados_transformados.append({
                'matriculaAluno': str(aluno)[:20],
                'nomeAluno': truncar_texto(nome_compl, 140),
                'emailAluno': email_aluno,
                'codigoCurso': str(curso)[:30],
                'turno': mapear_turno(turno),
                'codigoIdentificacaoAVA': ''
            })
        return dados_transformados

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        self._limpar_tabela()
        if not dados_transformados:
            print("ℹ️ Nenhum aluno elegível para importar.")
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': 0, 'total_processados': 0}

        insert_sql = """
            INSERT INTO imp_010_alunos (
                matriculaAluno, nomeAluno, emailAluno, codigoCurso, turno,
                codigoIdentificacaoAVA, data_criacao, data_atualizacao
            ) VALUES (?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
        """
        inseridos = erros = 0
        with get_db_connection(database_name='qstione') as conn:
            cursor = conn.cursor()
            for reg in dados_transformados:
                try:
                    cursor.execute(insert_sql, (
                        reg['matriculaAluno'], reg['nomeAluno'], reg['emailAluno'],
                        reg['codigoCurso'], reg['turno'], reg['codigoIdentificacaoAVA']
                    ))
                    inseridos += 1
                except Exception as e:
                    erros += 1
                    print(f"  ✗ Erro ao inserir {reg['matriculaAluno']}: {e}")
            conn.commit()
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_010_alunos")
        print("=" * 70)
        print("🎓 População: somente alunos presentes em imp_011_alunos_ofertas")

        filtros_aplicados = []
        if self.ano is not None:
            filtros_aplicados.append(f"ano_ingresso={self.ano}")
        if self.semestre is not None:
            filtros_aplicados.append(f"sem_ingresso={self.semestre}")
        if self.unidade is not None:
            filtros_aplicados.append(f"unidade_ensino='{self.unidade}'")
        if filtros_aplicados:
            print(f"🔍 Filtros adicionais: {', '.join(filtros_aplicados)}")

        dados_lyceum = self.obter_dados_lyceum()
        print(f"📊 Alunos elegíveis encontrados: {len(dados_lyceum)}")
        dados_transformados = self.transformar_dados(dados_lyceum)
        print(f"✅ Registros válidos: {len(dados_transformados)}")
        resultado = self.importar_para_qstione(dados_transformados)
        print("\n📈 RESULTADO DA IMPORTAÇÃO:")
        print(f"  ✓ Inseridos: {resultado['total_inseridos']}")
        print(f"  ✗ Erros: {resultado['total_erros']}")
        print(f"  📋 Total processados: {resultado['total_processados']}")
        return dados_transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Importação de alunos presentes nas ofertas vigentes")
    parser.add_argument('--ano', type=int, help="Filtro opcional de ano de ingresso")
    parser.add_argument('--semestre', type=int, help="Filtro opcional de semestre de ingresso")
    parser.add_argument('--unidade', type=str, help="Filtro opcional de unidade de ensino")
    args = parser.parse_args()
    ImportadorAlunos(ano=args.ano, semestre=args.semestre, unidade=args.unidade).executar_importacao()
