"""
qstione/importadores/imp_006_usuarios.py
Importador para tabela imp_006_usuarios
Adaptado para SQL Server usando core.database
"""

from core.database import get_db_connection
from qstione.core.transformacoes import (
    extrair_usuario_email,
    converter_minusculas,
    truncar_texto
)
from qstione.core.validacoes import validar_email, validar_matricula, validar_nome


class ImportadorUsuarios:

    def __init__(self):
        pass

    def _tabela_existe(self, nome_tabela: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️  Erro ao verificar existência da tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️  Erro ao verificar índice: {e}")
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_006_usuarios'):
            try:
                with get_db_connection(database_name='qstione') as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_NAME = 'imp_006_usuarios'
                          AND COLUMN_NAME IN ('data_criacao', 'data_atualizacao')
                    """)
                    colunas = [row[0] for row in cursor.fetchall()]
                    if 'data_criacao' in colunas and 'data_atualizacao' in colunas:
                        print("✅ Tabela imp_006_usuarios já existe com estrutura correta.")
                        return
                    else:
                        print("⚠️  Colunas ausentes. Recriando tabela...")
                        cursor.execute("DROP TABLE imp_006_usuarios")
                        conn.commit()
            except Exception as e:
                print(f"⚠️  Erro ao verificar colunas: {e}. Recriando tabela...")
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute("DROP TABLE IF EXISTS imp_006_usuarios")
                    conn.commit()

        print("🆕 Criando tabela imp_006_usuarios...")
        create_sql = """
            CREATE TABLE imp_006_usuarios (
                matriculaUsuario NVARCHAR(20) NOT NULL,
                codigoUsuario NVARCHAR(24) NULL,
                emailUsuario NVARCHAR(100) NOT NULL,
                nomeUsuario NVARCHAR(64) NOT NULL,
                data_criacao DATETIME2 DEFAULT GETDATE(),
                data_atualizacao DATETIME2 DEFAULT GETDATE(),
                PRIMARY KEY (matriculaUsuario)
            )
        """
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute(create_sql)
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
                print("✅ Índice idx_usuarios_email criado.")
            except Exception as e:
                print(f"⚠️ Índice idx_usuarios_email não pôde ser criado: {e}")
        else:
            print("✅ Índice idx_usuarios_email já existe.")

    def obter_dados_lyceum(self):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    MAX(d.matricula) as matricula,
                    MAX(d.mailbox) as email,
                    MAX(COALESCE(d.nome_social, d.nome_compl)) as nome_completo,
                    d.cpf
                FROM LY_DOCENTE d
                WHERE d.ativo = 'S'
                GROUP BY d.cpf
                ORDER BY MAX(d.matricula)
            """
            cursor.execute(query)
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        dados_transformados = []

        for registro in dados_lyceum:
            matricula, email, nome, cpf = registro

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
            nome_final = truncar_texto(nome, 64)

            dados_transformados.append({
                'matriculaUsuario': str(matricula)[:20],
                'codigoUsuario': codigo_usuario[:24] if codigo_usuario else None,
                'emailUsuario': email_final[:100],
                'nomeUsuario': nome_final
            })

        return dados_transformados

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()

        merge_sql = """
            MERGE INTO imp_006_usuarios AS target
            USING (VALUES (?, ?, ?, ?)) AS source (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario)
            ON target.matriculaUsuario = source.matriculaUsuario
            WHEN MATCHED THEN
                UPDATE SET
                    codigoUsuario = source.codigoUsuario,
                    emailUsuario = source.emailUsuario,
                    nomeUsuario = source.nomeUsuario,
                    data_atualizacao = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario, data_criacao, data_atualizacao)
                VALUES (source.matriculaUsuario, source.codigoUsuario, source.emailUsuario, source.nomeUsuario, GETDATE(), GETDATE());
        """

        total_inseridos = 0
        total_atualizados = 0
        total_erros = 0

        with get_db_connection(database_name='qstione') as conn:
            cursor = conn.cursor()
            for reg in dados_transformados:
                try:
                    cursor.execute("SELECT 1 FROM imp_006_usuarios WHERE matriculaUsuario = ?", (reg['matriculaUsuario'],))
                    existe = cursor.fetchone()

                    cursor.execute(merge_sql, (
                        reg['matriculaUsuario'],
                        reg['codigoUsuario'],
                        reg['emailUsuario'],
                        reg['nomeUsuario']
                    ))

                    if existe:
                        total_atualizados += 1
                    else:
                        total_inseridos += 1
                except Exception as e:
                    total_erros += 1
                    print(f"  ✗  Erro ao importar {reg['matriculaUsuario']}: {e}")

            conn.commit()

        return {
            'total_inseridos': total_inseridos,
            'total_atualizados': total_atualizados,
            'total_erros': total_erros,
            'total_processados': len(dados_transformados)
        }

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_006_usuarios")
        print("=" * 70)

        dados_lyceum = self.obter_dados_lyceum()
        print(f"📊 Registros encontrados no Lyceum: {len(dados_lyceum)}")

        print("🔄 Transformando dados...")
        dados_transformados = self.transformar_dados(dados_lyceum)
        print(f"✅ Registros válidos para importação: {len(dados_transformados)}")

        print("💾 Importando para banco Qstione...")
        resultado = self.importar_para_qstione(dados_transformados)

        print(f"\n📈 RESULTADO DA IMPORTAÇÃO:")
        print(f"  ✓ Inseridos: {resultado['total_inseridos']}")
        print(f"  ↻ Atualizados: {resultado['total_atualizados']}")
        print(f"  ✗ Erros: {resultado['total_erros']}")
        print(f"  📋 Total processados: {resultado['total_processados']}")

        return dados_transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    importador = ImportadorUsuarios()
    importador.executar_importacao()
