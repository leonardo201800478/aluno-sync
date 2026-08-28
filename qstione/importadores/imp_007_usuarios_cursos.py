"""
qstione/importadores/imp_007_usuarios_cursos.py

Importador independente para imp_007_usuarios_cursos.

REGRAS
------

1. O código de curso segue exatamente o mapeamento utilizado por
   imp_002_disciplina.py.

2. Somente cursos pertencentes às faculdades configuradas em
   FACULDADES_INCLUIDAS são considerados para os vínculos vindos
   do Lyceum.

3. O período utilizado é PERIODOS_VIGENTES[0].

4. Somente docentes ativos são considerados.

5. O e-mail do docente é obtido de LY_DOCENTE.mailbox.

6. Coordenadores recebem papel "C".
   Demais docentes recebem papel "P".

7. Todo professor encontrado nas turmas também recebe acesso
   ao curso 999, preservando seu papel:
       P -> P
       C -> C

8. Todos os membros ativos da tabela imp_nde_membros recebem
   papel "A" no seu respectivo curso.

9. O código de curso dos registros do NDE também passa pelo
   MAPEAMENTO_CURSOS.

   Exemplo:
       056 -> 056
       141 -> 056

10. Caso a mesma pessoa possua mais de um papel no mesmo curso,
    a prioridade é:

        C > P > A

    Portanto:

        coordenador + NDE -> C
        professor + NDE   -> P
        somente NDE       -> A

11. Membros NDE não são adicionados automaticamente ao curso 999
    por esta regra.

12. A tabela é reconstruída a cada execução.

13. A chave da tabela é:

        (codigoCurso, emailUsuario)
"""

import os
import sys


# ============================================================================
# PATH
# ============================================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ============================================================================
# IMPORTS
# ============================================================================

from core.database import get_db_connection

from qstione.core.transformacoes import (
    converter_minusculas,
    determinar_papel_usuario,
)

from qstione.core.validacoes import (
    validar_codigo_curso,
    validar_email,
    validar_papel_usuario,
)

from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
)

from qstione.importadores.imp_002_disciplina import (
    MAPEAMENTO_CURSOS,
)


# ============================================================================
# CONSTANTES
# ============================================================================

CURSO_COMPARTILHADO = "999"

PAPEL_PROFESSOR = "P"

PAPEL_COORDENADOR = "C"

PAPEL_NDE = "A"


# ============================================================================
# PRIORIDADE DOS PAPÉIS
# ============================================================================

PRIORIDADE_PAPEIS = {
    PAPEL_COORDENADOR: 1,
    PAPEL_NDE: 2,
    PAPEL_PROFESSOR: 3,
}


# ============================================================================
# IMPORTADOR
# ============================================================================

class ImportadorUsuariosCursos:
    """
    Importa professores, coordenadores e membros do NDE por curso.

    Papéis:

        C = Coordenador
        P = Professor
        A = Membro NDE

    A prioridade dos papéis é:

        C > P > A
    """

    def __init__(self):
        """
        Inicializa o importador.
        """

        self.faculdades_placeholders = ",".join(
            ["?"] * len(FACULDADES_INCLUIDAS)
        )

    # ========================================================================
    # TABELA
    # ========================================================================

    def _tabela_existe(
        self,
        nome_tabela: str
    ) -> bool:
        """
        Verifica se a tabela existe.

        Parameters
        ----------
        nome_tabela:
            Nome da tabela.

        Returns
        -------
        bool
            True quando a tabela existe.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                return conn.execute(
                    """
                    SELECT 1
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ?
                      AND TABLE_TYPE = 'BASE TABLE'
                    """,
                    (
                        nome_tabela,
                    )
                ).fetchone() is not None

        except Exception as e:

            print(
                f"⚠️ Erro ao verificar tabela: {e}"
            )

            return False

    # ========================================================================
    # ÍNDICE
    # ========================================================================

    def _indice_existe(
        self,
        nome_indice: str
    ) -> bool:
        """
        Verifica se um índice existe.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                return conn.execute(
                    """
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = ?
                    """,
                    (
                        nome_indice,
                    )
                ).fetchone() is not None

        except Exception:

            return False

    # ========================================================================
    # CRIAÇÃO DA TABELA
    # ========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela destino caso ela não exista.

        Também cria os índices auxiliares.
        """

        if not self._tabela_existe(
            "imp_007_usuarios_cursos"
        ):

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_007_usuarios_cursos (
                        codigoCurso NVARCHAR(30) NOT NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        papelUsuario NVARCHAR(1) NOT NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoCurso,
                            emailUsuario
                        )
                    )
                    """
                )

                conn.commit()

                print(
                    "🆕 Tabela imp_007_usuarios_cursos criada."
                )

        indices = [

            (
                "idx_usuarios_cursos_email",

                """
                CREATE INDEX idx_usuarios_cursos_email
                ON imp_007_usuarios_cursos(emailUsuario)
                """
            ),

            (
                "idx_usuarios_cursos_curso",

                """
                CREATE INDEX idx_usuarios_cursos_curso
                ON imp_007_usuarios_cursos(codigoCurso)
                """
            ),

            (
                "idx_usuarios_cursos_papel",

                """
                CREATE INDEX idx_usuarios_cursos_papel
                ON imp_007_usuarios_cursos(papelUsuario)
                """
            ),
        ]

        for nome, sql in indices:

            if not self._indice_existe(nome):

                try:

                    with get_db_connection(
                        database_name="qstione"
                    ) as conn:

                        conn.execute(sql)
                        conn.commit()

                except Exception as e:

                    print(
                        f"⚠️ Índice {nome}: {e}"
                    )

    # ========================================================================
    # CURSO UNIFICADO
    # ========================================================================

    @staticmethod
    def _curso_unificado(curso):
        """
        Retorna o código unificado do curso.

        Exemplos:

            056 -> 056
            141 -> 056
            036 -> 065
            037 -> 065
        """

        curso = (
            str(curso).strip()
            if curso is not None
            else ""
        )

        if curso in MAPEAMENTO_CURSOS:

            return MAPEAMENTO_CURSOS[
                curso
            ][0]

        return curso

    # ========================================================================
    # COORDENADORES
    # ========================================================================

    def obter_coordenadores(self):
        """
        Obtém os coordenadores dos cursos pertencentes às faculdades
        filtradas.
        """

        with get_db_connection() as conn:

            rows = conn.execute(
                """
                SELECT DISTINCT
                    co.num_func,
                    co.curso

                FROM LY_COORDENACAO co

                INNER JOIN LY_CURSO c
                    ON c.curso = co.curso

                WHERE c.faculdade IN ({})
                """.format(
                    self.faculdades_placeholders
                ),
                FACULDADES_INCLUIDAS
            ).fetchall()

        coordenadores = {}

        for num_func, curso in rows:

            curso = self._curso_unificado(
                curso
            )

            coordenadores[
                (
                    str(num_func),
                    str(curso)
                )
            ] = True

        print(
            "📋 Coordenadores encontrados nas "
            f"faculdades filtradas: {len(coordenadores)}"
        )

        return coordenadores

    # ========================================================================
    # DADOS LYCEUM
    # ========================================================================

    def obter_dados_lyceum(self):
        """
        Retorna os vínculos docente/curso.

        A origem do curso é LY_TURMA.curso.
        """

        coordenadores = (
            self.obter_coordenadores()
        )

        periodo_principal = (
            PERIODOS_VIGENTES[0]
        )

        with get_db_connection() as conn:

            rows = conn.execute(
                """
                SELECT DISTINCT

                    td.num_func,

                    d.mailbox,

                    t.curso

                FROM LY_TURMA_DOCENTE td

                INNER JOIN LY_TURMA t
                    ON t.ano = td.ano
                   AND t.semestre = td.periodo
                   AND t.turma = td.turma
                   AND t.disciplina = td.disciplina

                INNER JOIN LY_CURSO c
                    ON c.curso = t.curso

                INNER JOIN LY_DOCENTE d
                    ON d.num_func = td.num_func

                WHERE td.ano = ?

                  AND td.periodo = ?

                  AND c.faculdade IN ({})

                  AND d.ativo = 'S'

                ORDER BY
                    td.num_func,
                    t.curso
                """.format(
                    self.faculdades_placeholders
                ),
                (
                    ANO_VIGENTE,
                    periodo_principal,
                    *FACULDADES_INCLUIDAS,
                )
            ).fetchall()

        return rows, coordenadores

    # ========================================================================
    # MEMBROS NDE
    # ========================================================================

    def obter_membros_nde(self):
        """
        Obtém todos os membros ativos do NDE.

        Origem:

            qstione.imp_nde_membros

        Campos:

            codigoCurso
            emailMembro
            status

        O papel será definido como "A".
        """

        print(
            "👥 Consultando membros do NDE..."
        )

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                rows = conn.execute(
                    """
                    SELECT DISTINCT
                        codigoCurso,
                        emailMembro
                    FROM imp_nde_membros
                    WHERE codigoCurso IS NOT NULL
                      AND emailMembro IS NOT NULL
                      AND LTRIM(RTRIM(emailMembro)) <> ''
                      AND status = 'S'
                    """
                ).fetchall()

        except Exception as e:

            print(
                "❌ Erro ao consultar membros NDE: "
                f"{e}"
            )

            return []

        print(
            "👥 Membros NDE encontrados: "
            f"{len(rows)}"
        )

        return rows

    # ========================================================================
    # TRANSFORMAÇÃO
    # ========================================================================

    def transformar_dados(
        self,
        dados_lyceum,
        coordenadores,
        membros_nde
    ):
        """
        Transforma os vínculos do Lyceum e do NDE.

        Prioridade:

            C > P > A
        """

        registros_unicos = {}

        # ====================================================================
        # FUNÇÃO AUXILIAR
        # ====================================================================

        def adicionar_registro(
            codigo_curso,
            email,
            papel
        ):
            """
            Adiciona um registro respeitando a prioridade dos papéis.

            C > P > A
            """

            if not validar_codigo_curso(
                codigo_curso
            ):
                return

            if not validar_email(
                email
            ):
                return

            if not validar_papel_usuario(
                papel
            ):
                return

            codigo_curso = str(
                codigo_curso
            ).strip()[:30]

            email = converter_minusculas(
                str(email).strip()
            )[:100]

            chave = (
                codigo_curso,
                email
            )

            registro_existente = (
                registros_unicos.get(
                    chave
                )
            )

            # ---------------------------------------------------------------
            # NOVO REGISTRO
            # ---------------------------------------------------------------

            if registro_existente is None:

                registros_unicos[
                    chave
                ] = {
                    "codigoCurso": codigo_curso,
                    "emailUsuario": email,
                    "papelUsuario": papel,
                }

                return

            # ---------------------------------------------------------------
            # REGISTRO EXISTENTE
            # ---------------------------------------------------------------

            papel_existente = (
                registro_existente[
                    "papelUsuario"
                ]
            )

            prioridade_existente = (
                PRIORIDADE_PAPEIS.get(
                    papel_existente,
                    0
                )
            )

            prioridade_nova = (
                PRIORIDADE_PAPEIS.get(
                    papel,
                    0
                )
            )

            if prioridade_nova > prioridade_existente:

                registro_existente[
                    "papelUsuario"
                ] = papel

        # ====================================================================
        # 1. PROFESSORES / COORDENADORES
        # ====================================================================

        professores_compartilhados = {}

        registros_professores = 0

        for num_func, email, curso in dados_lyceum:

            curso = self._curso_unificado(
                curso
            )

            if not validar_codigo_curso(
                curso
            ):

                print(
                    "⚠️ Código de curso inválido: "
                    f"{curso} para docente {num_func}"
                )

                continue

            if not validar_email(
                email
            ):

                print(
                    "⚠️ Email inválido: "
                    f"{email} para docente {num_func}"
                )

                continue

            email_final = (
                converter_minusculas(
                    email
                )[:100]
            )

            papel = determinar_papel_usuario(
                num_func,
                curso,
                coordenadores
            )

            if not validar_papel_usuario(
                papel
            ):
                continue

            adicionar_registro(
                curso,
                email_final,
                papel
            )

            registros_professores += 1

            # ---------------------------------------------------------------
            # CONTROLE DO CURSO 999
            # ---------------------------------------------------------------

            papel_anterior = (
                professores_compartilhados.get(
                    email_final
                )
            )

            if (
                papel_anterior is None
                or (
                    papel == PAPEL_COORDENADOR
                    and papel_anterior == PAPEL_PROFESSOR
                )
            ):

                professores_compartilhados[
                    email_final
                ] = papel

        print(
            "👨‍🏫 Vínculos professor/coordenador "
            f"processados: {registros_professores}"
        )

        # ====================================================================
        # 2. PROFESSORES -> 999
        # ====================================================================

        professores_999 = 0

        for email, papel in (
            professores_compartilhados.items()
        ):

            adicionar_registro(
                CURSO_COMPARTILHADO,
                email,
                papel
            )

            professores_999 += 1

        print(
            "🌐 Professores adicionados ao curso "
            f"999: {professores_999}"
        )

        # ====================================================================
        # 3. MEMBROS DO NDE -> A
        # ====================================================================

        membros_nde_processados = 0

        membros_nde_com_papel_a = 0

        membros_nde_com_papel_existente = 0

        for curso, email in membros_nde:

            curso_unificado = (
                self._curso_unificado(
                    curso
                )
            )

            if not validar_codigo_curso(
                curso_unificado
            ):

                print(
                    "⚠️ Código de curso NDE inválido: "
                    f"{curso} -> {curso_unificado}"
                )

                continue

            if not validar_email(
                email
            ):

                print(
                    "⚠️ E-mail de membro NDE inválido: "
                    f"{email}"
                )

                continue

            email_final = (
                converter_minusculas(
                    str(email).strip()
                )[:100]
            )

            membros_nde_processados += 1

            chave = (
                curso_unificado[:30],
                email_final
            )

            registro_existente = (
                registros_unicos.get(
                    chave
                )
            )

            papel_anterior = None

            if registro_existente is not None:

                papel_anterior = (
                    registro_existente[
                        "papelUsuario"
                    ]
                )

            # ---------------------------------------------------------------
            # MEMBRO NDE = A
            # ---------------------------------------------------------------

            adicionar_registro(
                curso_unificado,
                email_final,
                PAPEL_NDE
            )

            # ---------------------------------------------------------------
            # ESTATÍSTICAS
            # ---------------------------------------------------------------

            registro_final = (
                registros_unicos.get(
                    chave
                )
            )

            if registro_final is not None:

                if (
                    registro_final[
                        "papelUsuario"
                    ] == PAPEL_NDE
                ):

                    membros_nde_com_papel_a += 1

                elif papel_anterior in (
                    PAPEL_PROFESSOR,
                    PAPEL_COORDENADOR
                ):

                    membros_nde_com_papel_existente += 1

                    print(
                        "ℹ️ Membro NDE já possui papel "
                        f"{papel_anterior} no curso "
                        f"{curso_unificado}: "
                        f"{email_final}. "
                        "Mantido papel acadêmico."
                    )

        print(
            "👥 Membros NDE processados: "
            f"{membros_nde_processados}"
        )

        print(
            "🅰️ Membros NDE efetivamente com papel A: "
            f"{membros_nde_com_papel_a}"
        )

        print(
            "ℹ️ Membros NDE que já possuíam P/C: "
            f"{membros_nde_com_papel_existente}"
        )

        # ====================================================================
        # RESULTADO FINAL
        # ====================================================================

        resultado = list(
            registros_unicos.values()
        )

        # ====================================================================
        # ESTATÍSTICAS
        # ====================================================================

        quantidade_c = sum(
            1
            for registro in resultado
            if registro["papelUsuario"]
            == PAPEL_COORDENADOR
        )

        quantidade_p = sum(
            1
            for registro in resultado
            if registro["papelUsuario"]
            == PAPEL_PROFESSOR
        )

        quantidade_a = sum(
            1
            for registro in resultado
            if registro["papelUsuario"]
            == PAPEL_NDE
        )

        print(
            "📊 Distribuição final:"
        )

        print(
            f"   C = {quantidade_c}"
        )

        print(
            f"   P = {quantidade_p}"
        )

        print(
            f"   A = {quantidade_a}"
        )

        print(
            f"   Total = {len(resultado)}"
        )

        return resultado

    # ========================================================================
    # IMPORTAÇÃO
    # ========================================================================

    def importar_para_qstione(
        self,
        dados_transformados
    ):
        """
        Reconstrói a tabela imp_007_usuarios_cursos.

        A tabela é limpa antes da carga.
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    DELETE FROM imp_007_usuarios_cursos
                    """
                )

                cursor = conn.cursor()

                for reg in dados_transformados:

                    try:

                        cursor.execute(
                            """
                            INSERT INTO imp_007_usuarios_cursos
                            (
                                codigoCurso,
                                emailUsuario,
                                papelUsuario,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES
                            (
                                ?,
                                ?,
                                ?,
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                reg[
                                    "codigoCurso"
                                ],

                                reg[
                                    "emailUsuario"
                                ],

                                reg[
                                    "papelUsuario"
                                ],
                            )
                        )

                        inseridos += 1

                    except Exception as e:

                        erros += 1

                        print(
                            "✗ "
                            f"{reg['codigoCurso']} - "
                            f"{reg['emailUsuario']} - "
                            f"{reg['papelUsuario']}: "
                            f"{e}"
                        )

                conn.commit()

        except Exception as e:

            print(
                f"❌ Erro durante reconstrução: {e}"
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": len(
                    dados_transformados
                ),
                "total_processados": len(
                    dados_transformados
                )
            }

        return {
            "total_inseridos": inseridos,
            "total_atualizados": 0,
            "total_erros": erros,
            "total_processados": len(
                dados_transformados
            )
        }

    # ========================================================================
    # EXECUÇÃO
    # ========================================================================

    def executar_importacao(self):
        """
        Executa toda a importação.

        Pode ser executado diretamente pelo botão Play do VS Code.
        """

        print(
            "=" * 70
        )

        print(
            "IMPORTAÇÃO: imp_007_usuarios_cursos"
        )

        print(
            "=" * 70
        )

        print(
            f"🎓 Ano: {ANO_VIGENTE} | "
            f"Período: {PERIODOS_VIGENTES[0]} | "
            f"Faculdades: {FACULDADES_INCLUIDAS}"
        )

        # ====================================================================
        # LYCEUM
        # ====================================================================

        dados, coordenadores = (
            self.obter_dados_lyceum()
        )

        print(
            f"📊 Registros encontrados no Lyceum: "
            f"{len(dados)}"
        )

        # ====================================================================
        # NDE
        # ====================================================================

        membros_nde = (
            self.obter_membros_nde()
        )

        print(
            f"👥 Registros NDE encontrados: "
            f"{len(membros_nde)}"
        )

        # ====================================================================
        # TRANSFORMAÇÃO
        # ====================================================================

        transformados = (
            self.transformar_dados(
                dados,
                coordenadores,
                membros_nde
            )
        )

        print(
            f"✅ Registros únicos finais: "
            f"{len(transformados)}"
        )

        # ====================================================================
        # IMPORTAÇÃO
        # ====================================================================

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']} | "
            f"Erros: "
            f"{resultado['total_erros']}"
        )

        print(
            "=" * 70
        )

        return transformados


# ============================================================================
# EXECUÇÃO DIRETA
# ============================================================================

if __name__ == "__main__":

    ImportadorUsuariosCursos().executar_importacao()