"""
qstione/importadores/imp_006_usuarios.py
Importador para tabela imp_006_usuarios.

Somente docentes presentes na mesma população do imp_007_usuarios_cursos
(ano/período vigente) são importados. O e-mail vem exclusivamente de
LY_DOCENTE.mailbox.
"""

import os
import sys

# Permite executar diretamente pelo botão Play do VS Code, independentemente do cwd.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import extrair_usuario_email, converter_minusculas, truncar_texto
from qstione.core.validacoes import validar_email, validar_matricula, validar_nome
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES


class ImportadorUsuarios:
    def __init__(self):
        pass

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
        if self._tabela_existe('imp_006_usuarios'):
            return
        print("🆕 Criando tabela imp_006_usuarios...")
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_006_usuarios (
                        matriculaUsuario NVARCHAR(20) NOT NULL,
                        codigoUsuario NVARCHAR(24) NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        nomeUsuario NVARCHAR(64) NOT NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (matriculaUsuario)
                    )
                """)
                conn.commit()
            print("✅ Tabela criada.")
        except Exception as e:
            print(f"❌ Erro ao criar tabela: {e}")
            return

        if not self._indice_existe('idx_usuarios_email'):
            try:
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute("CREATE INDEX idx_usuarios_email ON imp_006_usuarios(emailUsuario)")
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Índice idx_usuarios_email não pôde ser criado: {e}")

    def obter_dados_lyceum(self):
        """Usa a mesma população docente do imp_007_usuarios_cursos."""
        periodo_principal = PERIODOS_VIGENTES[0]
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    MAX(d.matricula) AS matricula,
                    MAX(d.mailbox) AS email,
                    MAX(COALESCE(d.nome_social, d.nome_compl)) AS nome_completo,
                    d.cpf
                FROM LY_DOCENTE d
                INNER JOIN (
                    SELECT DISTINCT td.num_func
                    FROM LY_TURMA_DOCENTE td
                    INNER JOIN LY_GRADE g ON g.disciplina = td.disciplina
                    WHERE td.ano = ? AND td.periodo = ?
                ) elegivel ON elegivel.num_func = d.num_func
                WHERE d.ativo = 'S'
                  AND d.mailbox IS NOT NULL
                  AND LTRIM(RTRIM(d.mailbox)) <> ''
                GROUP BY d.cpf
                ORDER BY MAX(d.matricula)
            """, (ANO_VIGENTE, periodo_principal))
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        dados_transformados = []
        for matricula, email, nome, cpf in dados_lyceum:
            if not validar_matricula(matricula):
                print(f"  ⚠️  Matrícula inválida: {matricula}")
                continue
            if not validar_email(email):
                print(f"  ⚠️  Email inválido: {email}")
                continue
            if not validar_nome(nome):
                print(f"  ⚠️  Nome inválido: {nome}")
                continue
            email_final = converter_minusculas(email)
            codigo_usuario = extrair_usuario_email(email)
            dados_transformados.append({
                'matriculaUsuario': str(matricula)[:20],
                'codigoUsuario': codigo_usuario[:24] if codigo_usuario else None,
                'emailUsuario': email_final[:100],
                'nomeUsuario': truncar_texto(nome, 64)
            })
        return dados_transformados

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        merge_sql = """
            MERGE INTO imp_006_usuarios AS target
            USING (VALUES (?, ?, ?, ?)) AS source (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario)
            ON target.matriculaUsuario = source.matriculaUsuario
            WHEN MATCHED THEN UPDATE SET
                codigoUsuario = source.codigoUsuario,
                emailUsuario = source.emailUsuario,
                nomeUsuario = source.nomeUsuario,
                data_atualizacao = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario, data_criacao, data_atualizacao)
                VALUES (source.matriculaUsuario, source.codigoUsuario, source.emailUsuario, source.nomeUsuario, GETDATE(), GETDATE());
        """
        inseridos = atualizados = erros = 0
        with get_db_connection(database_name='qstione') as conn:
            cursor = conn.cursor()
            for reg in dados_transformados:
                try:
                    cursor.execute("SELECT 1 FROM imp_006_usuarios WHERE matriculaUsuario = ?", (reg['matriculaUsuario'],))
                    existe = cursor.fetchone()
                    cursor.execute(merge_sql, (reg['matriculaUsuario'], reg['codigoUsuario'], reg['emailUsuario'], reg['nomeUsuario']))
                    atualizados += 1 if existe else 0
                    inseridos += 0 if existe else 1
                except Exception as e:
                    erros += 1
                    print(f"  ✗  Erro ao importar {reg['matriculaUsuario']}: {e}")
            conn.commit()
        return {'total_inseridos': inseridos, 'total_atualizados': atualizados, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_006_usuarios")
        print("=" * 70)
        print(f"🎓 Docentes habilitados: ano={ANO_VIGENTE}, período={PERIODOS_VIGENTES[0]}")
        dados = self.obter_dados_lyceum()
        print(f"📊 Registros encontrados: {len(dados)}")
        transformados = self.transformar_dados(dados)
        print(f"✅ Registros válidos: {len(transformados)}")
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Atualizados: {resultado['total_atualizados']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    ImportadorUsuarios().executar_importacao()
