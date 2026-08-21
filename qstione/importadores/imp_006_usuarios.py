"""
qstione/importadores/imp_006_usuarios.py
Importador para tabela imp_006_usuarios.

Somente docentes presentes na população de turmas/docentes do período vigente
são importados. A elegibilidade segue a mesma origem de turma utilizada pelo
imp_002_disciplina.py:

- ano/período vigente;
- LY_TURMA_DOCENTE relacionado à LY_TURMA pela chave completa
  (ano, semestre, turma, disciplina);
- o curso considerado é SEMPRE LY_TURMA.curso;
- cursos duplicados são unificados pelo mesmo MAPEAMENTO_CURSOS do imp_002;
- turma sem curso definido é tratada como curso 999 (COMPARTILHADA);
- o docente precisa estar ativo e possuir LY_DOCENTE.mailbox válido.

O e-mail vem exclusivamente de LY_DOCENTE.mailbox.
A tabela destino é reconstruída integralmente a cada execução.
"""

import os
import sys

# Permite executar diretamente pelo botão Play do VS Code, independentemente do cwd.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import (
    extrair_usuario_email,
    converter_minusculas,
    truncar_texto,
)
from qstione.core.validacoes import validar_email, validar_matricula, validar_nome
from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorUsuarios:
    """Importa docentes habilitados nas turmas vigentes."""

    def __init__(self):
        self.periodos_placeholders = ','.join(['?'] * len(PERIODOS_VIGENTES))
        self.faculdades_placeholders = ','.join(['?'] * len(FACULDADES_INCLUIDAS))

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
                return conn.execute(
                    "SELECT 1 FROM sys.indexes WHERE name = ?",
                    (nome_indice,),
                ).fetchone() is not None
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
                    conn.execute(
                        "CREATE INDEX idx_usuarios_email ON imp_006_usuarios(emailUsuario)"
                    )
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Índice idx_usuarios_email não pôde ser criado: {e}")

    @staticmethod
    def _curso_unificado(curso):
        """Aplica exatamente o MAPEAMENTO_CURSOS definido pelo imp_002."""
        curso = str(curso).strip() if curso is not None else ''
        if not curso:
            return '999'
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))[0]

    def obter_dados_lyceum(self):
        """
        Obtém docentes ligados às turmas vigentes.

        A relação LY_TURMA_DOCENTE -> LY_TURMA utiliza a chave completa
        (ano, semestre, turma, disciplina), exatamente como o imp_002.
        O curso vem exclusivamente de LY_TURMA.curso.
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT DISTINCT
                    td.num_func,
                    d.matricula,
                    d.mailbox,
                    COALESCE(d.nome_social, d.nome_compl) AS nome_completo,
                    d.cpf,
                    t.curso
                FROM LY_TURMA_DOCENTE td
                INNER JOIN LY_TURMA t
                    ON t.ano = td.ano
                   AND t.semestre = td.periodo
                   AND t.turma = td.turma
                   AND t.disciplina = td.disciplina
                INNER JOIN LY_DOCENTE d
                    ON d.num_func = td.num_func
                LEFT JOIN LY_CURSO c
                    ON c.curso = t.curso
                WHERE td.ano = ?
                  AND td.periodo IN ({self.periodos_placeholders})
                  AND t.sit_turma = ?
                  AND (
                        t.curso IS NULL
                        OR c.faculdade IN ({self.faculdades_placeholders})
                      )
                  AND d.ativo = 'S'
                  AND d.mailbox IS NOT NULL
                  AND LTRIM(RTRIM(d.mailbox)) <> ''
                ORDER BY d.matricula, td.num_func, t.curso
            """, (
                ANO_VIGENTE,
                *PERIODOS_VIGENTES,
                SITUACAO_TURMA_VALIDA,
                *FACULDADES_INCLUIDAS,
            ))
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        """
        Valida docentes e elimina duplicidades por matrícula.

        O curso/turma é utilizado para determinar a população elegível, mas
        não faz parte da tabela imp_006_usuarios. Assim, um docente que lecione
        várias turmas/cursos continua gerando apenas um usuário.
        """
        registros = {}

        for matricula, matricula_docente, email, nome, cpf, curso in dados_lyceum:
            curso_unificado = self._curso_unificado(curso)

            if not validar_matricula(matricula_docente):
                print(f"  ⚠️  Matrícula inválida: {matricula_docente} (curso {curso_unificado})")
                continue
            if not validar_email(email):
                print(f"  ⚠️  Email inválido: {email}")
                continue
            if not validar_nome(nome):
                print(f"  ⚠️  Nome inválido: {nome}")
                continue

            matricula_final = str(matricula_docente)[:20]
            email_final = converter_minusculas(email)[:100]
            codigo_usuario = extrair_usuario_email(email)

            # A matrícula é a chave primária. Caso o mesmo docente apareça em
            # várias turmas/cursos, preservamos somente um registro.
            if matricula_final not in registros:
                registros[matricula_final] = {
                    'matriculaUsuario': matricula_final,
                    'codigoUsuario': codigo_usuario[:24] if codigo_usuario else None,
                    'emailUsuario': email_final,
                    'nomeUsuario': truncar_texto(nome, 64),
                }

        return list(registros.values())

    def importar_para_qstione(self, dados_transformados):
        """Reconstrói integralmente imp_006_usuarios."""
        self._criar_tabela()

        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()

                # Regra dos importadores Qstione: carga sempre limpa.
                cursor.execute("DELETE FROM imp_006_usuarios")

                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_006_usuarios
                            (
                                matriculaUsuario,
                                codigoUsuario,
                                emailUsuario,
                                nomeUsuario,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
                        """, (
                            reg['matriculaUsuario'],
                            reg['codigoUsuario'],
                            reg['emailUsuario'],
                            reg['nomeUsuario'],
                        ))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"  ✗  Erro ao importar {reg['matriculaUsuario']}: {e}")

                conn.commit()
        except Exception as e:
            print(f"❌ Erro durante reconstrução da tabela: {e}")
            return {
                'total_inseridos': 0,
                'total_atualizados': 0,
                'total_erros': len(dados_transformados),
                'total_processados': len(dados_transformados),
            }

        return {
            'total_inseridos': inseridos,
            'total_atualizados': 0,
            'total_erros': erros,
            'total_processados': len(dados_transformados),
        }

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_006_usuarios")
        print("=" * 70)
        print(
            f"🎓 Docentes habilitados: ano={ANO_VIGENTE}, "
            f"períodos={PERIODOS_VIGENTES}"
        )
        print("🔗 Cursos/turmas: mesma regra de origem do imp_002_disciplina")

        dados = self.obter_dados_lyceum()
        print(f"📊 Vínculos docente/turma encontrados: {len(dados)}")

        transformados = self.transformar_dados(dados)
        print(f"✅ Usuários únicos: {len(transformados)}")

        resultado = self.importar_para_qstione(transformados)
        print(
            f"📈 Inseridos: {resultado['total_inseridos']} | "
            f"Erros: {resultado['total_erros']}"
        )
        return transformados


if __name__ == "__main__":
    ImportadorUsuarios().executar_importacao()
