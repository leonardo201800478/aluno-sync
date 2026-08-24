"""
qstione/importadores/imp_011_alunos_ofertas.py

Importador independente para alunos vinculados às ofertas/turmas.

REGRAS PRINCIPAIS
-----------------

1. A fonte da matrícula é LY_MATRICULA.

2. A oferta é identificada por:

       disciplina
       turma
       ano
       semestre

3. O codigoOferta é gerado EXATAMENTE pela mesma função utilizada
   pelo imp_005_ofertas.py:

       gerar_codigo_oferta(
           disciplina,
           turma,
           ano,
           semestre
       )

4. O curso da oferta NÃO vem de LY_ALUNO.curso.

   O curso é obtido de:

       LY_TURMA.curso

   porque a matrícula está vinculada à turma/disciplina.

5. Se LY_TURMA.curso for NULL ou vazio:

       codigoCurso = 999

   representando:

       COMPARTILHADA

6. Quando houver curso definido, ele é normalizado utilizando
   exatamente o MAPEAMENTO_CURSOS do imp_002_disciplina.py.

7. A turma deve pertencer ao ano, período e faculdade configurados.

8. Turmas sem curso definido são aceitas independentemente da
   faculdade, pois são tratadas como compartilhadas.

9. A existência da matrícula não depende de docente.

10. A existência da matrícula não depende de outra tabela de alunos
    para determinar o curso da oferta.

11. A tabela destino é totalmente reconstruída em cada execução.

12. O arquivo pode ser executado diretamente pelo botão Play
    do VS Code.
"""

import os
import sys


# =============================================================================
# PATH
# =============================================================================

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# =============================================================================
# IMPORTS
# =============================================================================

from core.database import get_db_connection

from qstione.core.transformacoes import (
    gerar_codigo_oferta,
    truncar_texto,
)

from qstione.core.validacoes import (
    validar_matricula,
    validar_codigo_curso,
)

from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)

from qstione.importadores.imp_002_disciplina import (
    MAPEAMENTO_CURSOS,
)


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorAlunosOfertas:
    """
    Importa os alunos matriculados nas turmas/ofertas vigentes.

    A relação aluno → oferta é determinada por LY_MATRICULA.

    O curso da oferta é determinado pela LY_TURMA.
    """

    # =========================================================================
    # CURSO
    # =========================================================================

    @staticmethod
    def _curso_unificado(
        curso,
    ) -> str:
        """
        Normaliza o código de curso utilizando o mesmo
        MAPEAMENTO_CURSOS do imp_002_disciplina.py.

        Regras:

        NULL
            -> 999

        vazio
            -> 999

        curso mapeado
            -> código unificado

        curso não mapeado
            -> mantém código original
        """

        # ---------------------------------------------------------------------
        # NULL
        # ---------------------------------------------------------------------

        if curso is None:
            return "999"

        # ---------------------------------------------------------------------
        # NORMALIZA TEXTO
        # ---------------------------------------------------------------------

        curso = str(
            curso
        ).strip()

        # ---------------------------------------------------------------------
        # VAZIO
        # ---------------------------------------------------------------------

        if not curso:
            return "999"

        # ---------------------------------------------------------------------
        # MAPEAMENTO OFICIAL
        # ---------------------------------------------------------------------

        if curso in MAPEAMENTO_CURSOS:

            return str(
                MAPEAMENTO_CURSOS[curso][0]
            ).strip()

        # ---------------------------------------------------------------------
        # NÃO MAPEADO
        # ---------------------------------------------------------------------

        return curso

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela,
    ):
        """
        Verifica se a tabela destino existe.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                return (
                    conn.execute(
                        """
                        SELECT 1
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_NAME = ?
                          AND TABLE_TYPE = 'BASE TABLE'
                        """,
                        (nome_tabela,),
                    ).fetchone()
                    is not None
                )

        except Exception as e:

            print(
                f"⚠️ Erro ao verificar tabela: {e}"
            )

            return False

    # =========================================================================
    # ÍNDICE
    # =========================================================================

    def _indice_existe(
        self,
        nome_indice,
    ):
        """
        Verifica se um índice existe.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                return (
                    conn.execute(
                        """
                        SELECT 1
                        FROM sys.indexes
                        WHERE name = ?
                        """,
                        (nome_indice,),
                    ).fetchone()
                    is not None
                )

        except Exception:

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela imp_011_alunos_ofertas caso não exista.
        """

        if self._tabela_existe(
            "imp_011_alunos_ofertas"
        ):

            self._criar_indices()

            return True

        print(
            "🆕 Criando tabela imp_011_alunos_ofertas..."
        )

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_011_alunos_ofertas (

                        codigoOferta NVARCHAR(30) NOT NULL,

                        matriculaAluno NVARCHAR(20) NOT NULL,

                        codigoCurso NVARCHAR(30) NOT NULL,

                        data_criacao DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoOferta,
                            matriculaAluno
                        )
                    )
                    """
                )

                conn.commit()

            print(
                "✅ Tabela criada."
            )

            self._criar_indices()

            return True

        except Exception as e:

            print(
                f"❌ Erro ao criar tabela: {e}"
            )

            return False

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):
        """
        Cria os índices auxiliares da tabela.
        """

        indices = [

            (
                "idx_alunos_ofertas_matricula",
                """
                CREATE INDEX idx_alunos_ofertas_matricula
                ON imp_011_alunos_ofertas(matriculaAluno)
                """,
            ),

            (
                "idx_alunos_ofertas_curso",
                """
                CREATE INDEX idx_alunos_ofertas_curso
                ON imp_011_alunos_ofertas(codigoCurso)
                """,
            ),

            (
                "idx_alunos_ofertas_oferta",
                """
                CREATE INDEX idx_alunos_ofertas_oferta
                ON imp_011_alunos_ofertas(codigoOferta)
                """,
            ),

        ]

        for nome_indice, sql in indices:

            if self._indice_existe(
                nome_indice
            ):

                continue

            try:

                with get_db_connection(
                    database_name="qstione"
                ) as conn:

                    conn.execute(sql)
                    conn.commit()

            except Exception as e:

                print(
                    f"⚠️ Índice {nome_indice} "
                    f"não pôde ser criado: {e}"
                )

    # =========================================================================
    # CONSULTA LYCEUM
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém os alunos efetivamente matriculados nas turmas válidas.

        IMPORTANTE
        ----------

        O curso é obtido de LY_TURMA.curso.

        Não é utilizado LY_ALUNO.curso para determinar o curso
        da oferta.

        Isso é fundamental para turmas compartilhadas.
        """

        periodos = ",".join(
            "?"
            for _ in PERIODOS_VIGENTES
        )

        faculdades = ",".join(
            "?"
            for _ in FACULDADES_INCLUIDAS
        )

        query = f"""
            SELECT DISTINCT

                m.aluno,

                m.ano,

                m.semestre,

                m.turma,

                m.disciplina,

                t.curso

            FROM LY_MATRICULA m

            INNER JOIN LY_TURMA t
                ON t.ano = m.ano
               AND t.semestre = m.semestre
               AND t.turma = m.turma
               AND t.disciplina = m.disciplina

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            WHERE m.ano = ?

              AND m.semestre IN (
                  {periodos}
              )

              AND t.sit_turma = ?

              AND (
                    t.curso IS NULL

                    OR c.faculdade IN (
                        {faculdades}
                    )
                  )

            ORDER BY

                m.aluno,
                m.ano,
                m.semestre,
                m.turma,
                m.disciplina
        """

        params = [
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        ]

        with get_db_connection() as conn:

            return conn.execute(
                query,
                params,
            ).fetchall()

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum,
    ):
        """
        Converte os registros do Lyceum para o formato da tabela destino.

        O codigoOferta é baseado exclusivamente em:

            disciplina
            turma
            ano
            semestre

        O codigoCurso é baseado em:

            LY_TURMA.curso
                ↓
            MAPEAMENTO_CURSOS
        """

        unicos = {}

        total_999 = 0
        total_mapeados = 0

        for (
            aluno,
            ano,
            semestre,
            turma,
            disciplina,
            curso_turma,
        ) in dados_lyceum:

            # -----------------------------------------------------------------
            # MATRÍCULA
            # -----------------------------------------------------------------

            if not validar_matricula(
                aluno
            ):

                print(
                    f"⚠️ Matrícula inválida: "
                    f"{aluno}"
                )

                continue

            # -----------------------------------------------------------------
            # CURSO DA TURMA
            # -----------------------------------------------------------------

            curso_unificado = (
                self._curso_unificado(
                    curso_turma
                )
            )

            # -----------------------------------------------------------------
            # ESTATÍSTICAS
            # -----------------------------------------------------------------

            if curso_unificado == "999":

                total_999 += 1

            else:

                curso_original = (
                    str(curso_turma).strip()
                    if curso_turma is not None
                    else ""
                )

                if (
                    curso_original in
                    MAPEAMENTO_CURSOS
                ):

                    total_mapeados += 1

            # -----------------------------------------------------------------
            # VALIDAÇÃO DO CURSO
            # -----------------------------------------------------------------

            if not validar_codigo_curso(
                curso_unificado
            ):

                print(
                    f"⚠️ Código de curso inválido: "
                    f"{curso_turma} → "
                    f"{curso_unificado} | "
                    f"aluno={aluno} | "
                    f"turma={turma} | "
                    f"disciplina={disciplina}"
                )

                continue

            # -----------------------------------------------------------------
            # CÓDIGO DA OFERTA
            # -----------------------------------------------------------------

            codigo_oferta = truncar_texto(
                gerar_codigo_oferta(
                    disciplina,
                    turma,
                    ano,
                    semestre,
                ),
                30,
            )

            # -----------------------------------------------------------------
            # MATRÍCULA
            # -----------------------------------------------------------------

            matricula = truncar_texto(
                str(aluno),
                20,
            )

            # -----------------------------------------------------------------
            # CHAVE ÚNICA
            # -----------------------------------------------------------------

            chave = (
                codigo_oferta,
                matricula,
            )

            unicos[chave] = {

                "codigoOferta":
                    codigo_oferta,

                "matriculaAluno":
                    matricula,

                "codigoCurso":
                    truncar_texto(
                        curso_unificado,
                        30,
                    ),
            }

        print(
            f"🔗 Turmas compartilhadas / curso 999: "
            f"{total_999}"
        )

        print(
            f"🔄 Cursos normalizados pelo "
            f"MAPEAMENTO_CURSOS: "
            f"{total_mapeados}"
        )

        return list(
            unicos.values()
        )

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ):
        """
        Limpa e reconstrói integralmente a tabela.
        """

        if not self._criar_tabela():

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": len(
                    dados_transformados
                ),
                "total_processados": len(
                    dados_transformados
                ),
            }

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                # -------------------------------------------------------------
                # LIMPEZA TOTAL
                # -------------------------------------------------------------

                conn.execute(
                    """
                    DELETE FROM imp_011_alunos_ofertas
                    """
                )

                cursor = conn.cursor()

                # -------------------------------------------------------------
                # INSERT
                # -------------------------------------------------------------

                for reg in dados_transformados:

                    try:

                        cursor.execute(
                            """
                            INSERT INTO imp_011_alunos_ofertas
                            (
                                codigoOferta,
                                matriculaAluno,
                                codigoCurso,
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
                                    "codigoOferta"
                                ],

                                reg[
                                    "matriculaAluno"
                                ],

                                reg[
                                    "codigoCurso"
                                ],
                            ),
                        )

                        inseridos += 1

                    except Exception as e:

                        erros += 1

                        print(
                            f"✗ "
                            f"{reg['codigoOferta']} - "
                            f"{reg['matriculaAluno']}: "
                            f"{e}"
                        )

                conn.commit()

        except Exception as e:

            print(
                f"❌ Erro durante reconstrução: "
                f"{e}"
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": len(
                    dados_transformados
                ),
                "total_processados": len(
                    dados_transformados
                ),
            }

        return {
            "total_inseridos": inseridos,
            "total_atualizados": 0,
            "total_erros": erros,
            "total_processados": len(
                dados_transformados
            ),
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(self):
        """
        Executa a importação completa.
        """

        print(
            "=" * 70
        )

        print(
            "IMPORTAÇÃO: imp_011_alunos_ofertas"
        )

        print(
            "=" * 70
        )

        print(
            f"📅 Ano: {ANO_VIGENTE}"
        )

        print(
            f"📅 Períodos: {PERIODOS_VIGENTES}"
        )

        print(
            f"🏫 Faculdades: {FACULDADES_INCLUIDAS}"
        )

        print(
            f"📚 Situação turma: "
            f"{SITUACAO_TURMA_VALIDA}"
        )

        print(
            "🔗 Curso da oferta: LY_TURMA.curso"
        )

        print(
            "🔄 Cursos: "
            "MAPEAMENTO_CURSOS do imp_002"
        )

        print(
            "🎓 Alunos: LY_MATRICULA"
        )

        # ---------------------------------------------------------------------
        # CONSULTA
        # ---------------------------------------------------------------------

        dados = (
            self.obter_dados_lyceum()
        )

        print(
            f"📊 Registros encontrados: "
            f"{len(dados)}"
        )

        # ---------------------------------------------------------------------
        # TRANSFORMAÇÃO
        # ---------------------------------------------------------------------

        transformados = (
            self.transformar_dados(
                dados
            )
        )

        print(
            f"✅ Registros únicos: "
            f"{len(transformados)}"
        )

        # ---------------------------------------------------------------------
        # IMPORTAÇÃO
        # ---------------------------------------------------------------------

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']} "
            f"| Erros: "
            f"{resultado['total_erros']}"
        )

        return transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    ImportadorAlunosOfertas().executar_importacao()