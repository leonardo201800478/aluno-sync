"""
qstione/importadores/imp_006_usuarios.py
Importador para tabela imp_006_usuarios.

A população de docentes é determinada diretamente por LY_TURMA_DOCENTE:
- ano/período vigentes;
- curso da turma obtido de LY_TURMA.curso;
- faculdade do curso filtrada pelas mesmas regras do imp_002_disciplina;
- docente identificado exclusivamente por LY_TURMA_DOCENTE.num_func.

Depois de obter os NUM_FUNC elegíveis, o cadastro é completado em LY_DOCENTE.
O e-mail vem exclusivamente de LY_DOCENTE.mailbox.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import extrair_usuario_email, converter_minusculas, truncar_texto
from qstione.core.validacoes import validar_email, validar_matricula, validar_nome
from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorUsuarios:
    """Importa todos os docentes presentes nas turmas elegíveis do período vigente."""

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
            print(f"  ⚠️ Erro ao verificar existência da tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute(
                    "SELECT 1 FROM sys.indexes WHERE name = ?",
                    (nome_indice,)
                ).fetchone() is not None
        except Exception as e:
            print(f"  ⚠️ Erro ao verificar índice: {e}")
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
        """Aplica exatamente o mapeamento de cursos utilizado pelo imp_002."""
        if curso is None or str(curso).strip() == '':
            return '999'
        curso = str(curso).strip()
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))[0]

    def obter_dados_lyceum(self):
        """
        Obtém primeiro os NUM_FUNC diretamente de LY_TURMA_DOCENTE.

        A elegibilidade é determinada pela turma/disciplina e pelo curso da
        própria turma, seguindo a lógica do imp_002. Depois o cadastro é
        completado em LY_DOCENTE.
        """
        query = f"""
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
            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso
            INNER JOIN LY_DOCENTE d
                ON d.num_func = td.num_func
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
            ORDER BY td.num_func, d.matricula
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        )

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        """
        Cria o cadastro do usuário a partir do docente encontrado pelo NUM_FUNC.

        Um docente pode aparecer em várias turmas/cursos; a tabela de usuários
        deve possuir apenas um registro por matrícula.
        """
        registros = {}

        for num_func, matricula, email, nome, cpf, curso in dados_lyceum:
            if not validar_matricula(matricula):
                print(f"  ⚠️ Matrícula inválida para NUM_FUNC {num_func}: {matricula}")
                continue
            if not validar_email(email):
                print(f"  ⚠️ Email inválido para NUM_FUNC {num_func}: {email}")
                continue
            if not validar_nome(nome):
                print(f"  ⚠️ Nome inválido para NUM_FUNC {num_func}: {nome}")
                continue

            email_final = converter_minusculas(email)[:100]
            codigo_usuario = extrair_usuario_email(email)
            matricula_final = str(matricula)[:20]

            # A chave do usuário é a matrícula, independentemente da quantidade
            # de turmas/cursos em que o NUM_FUNC aparece.
            if matricula_final not in registros:
                registros[matricula_final] = {
                    'matriculaUsuario': matricula_final,
                    'codigoUsuario': codigo_usuario[:24] if codigo_usuario else None,
                    'emailUsuario': email_final,
                    'nomeUsuario': truncar_texto(nome, 64),
                }

        return list(registros.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()

        inseridos = erros = 0

        try:
            with get_db_connection(database_name='qstione') as conn:
                # Reconstrução completa da tabela a cada execução.
                conn.execute("DELETE FROM imp_006_usuarios")
                cursor = conn.cursor()

                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_006_usuarios
                            (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario,
                             data_criacao, data_atualizacao)
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
                        print(f"  ✗ Erro ao importar {reg['matriculaUsuario']}: {e}")

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
            f"🎓 Docentes por LY_TURMA_DOCENTE: ano={ANO_VIGENTE}, "
            f"períodos={PERIODOS_VIGENTES}, faculdades={FACULDADES_INCLUIDAS}"
        )

        dados = self.obter_dados_lyceum()
        num_funcs = {str(row[0]) for row in dados if row[0] is not None}
        print(f"📊 Registros de vínculos encontrados: {len(dados)}")
        print(f"👨‍🏫 NUM_FUNC únicos elegíveis: {len(num_funcs)}")

        transformados = self.transformar_dados(dados)
        print(f"✅ Usuários únicos válidos: {len(transformados)}")

        resultado = self.importar_para_qstione(transformados)
        print(
            f"📈 Inseridos: {resultado['total_inseridos']} | "
            f"Erros: {resultado['total_erros']}"
        )
        return transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    ImportadorUsuarios().executar_importacao()
