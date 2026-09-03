
"""
qstione/importadores/imp_013_unidades_avaliacao.py

Importador independente de unidades de avaliação.

REGRAS
------

1. A unidade de avaliação nasce de LY_PROVA.

2. A prova somente é considerada quando estiver vinculada a uma
   LY_TURMA válida.

3. A turma deve respeitar:

       - ANO_VIGENTE
       - PERIODOS_VIGENTES
       - SITUACAO_TURMA_VALIDA
       - FACULDADES_INCLUIDAS

4. A faculdade da turma é determinada por:

       LY_TURMA.curso
            ↓
       LY_CURSO.faculdade

5. LY_DISCIPLINA.faculdade não é utilizada para determinar
   a faculdade.

6. O curso original é preservado durante a consulta.

7. A unificação do curso acontece somente durante a transformação.

8. O codigoDisciplina utiliza exatamente a mesma função
   utilizada pelo imp_002_disciplina.py.

9. Cursos alternativos são unificados pelo MAPEAMENTO_CURSOS.

10. A tabela é reconstruída a cada execução.
"""

import os
import sys
import logging


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
    truncar_texto,
    converter_inteiro,
    gerar_codigo_disciplina_curso,
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


# ============================================================================
# LOG
# ============================================================================

logger = logging.getLogger(
    "imp_013_unidades_avaliacao"
)

if not logger.handlers:

    handler = logging.StreamHandler()

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )

    logger.addHandler(
        handler
    )

logger.setLevel(
    logging.INFO
)


# ============================================================================
# CONSTANTES
# ============================================================================

CURSO_COMPARTILHADO = "999"


# ============================================================================
# IMPORTADOR
# ============================================================================

class ImportadorUnidadesAvaliacao:

    MAPEAMENTO_PROVA = {

        "AVF":
            "Avaliação Formativa",

        "AVS":
            "Avaliação Somativa",

        "AVSB":
            "Avaliação Substitutiva",

        "AVD1":
            "Avaliação 1",

        "AVD2":
            "Avaliação 2",

        "SUBST":
            "Avaliação Substitutiva",

        "AV":
            "Avaliação",
    }

    def __init__(self):

        self.periodos_placeholders = ",".join(
            "?"
            for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?"
            for _ in FACULDADES_INCLUIDAS
        )

    # ========================================================================
    # CURSO
    # ========================================================================

    @staticmethod
    def _curso_unificado(curso):

        if curso is None:
            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA",
            )

        curso = str(curso).strip()

        if not curso:
            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA",
            )

        if curso == CURSO_COMPARTILHADO:
            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA",
            )

        if curso in MAPEAMENTO_CURSOS:

            codigo, nome = (
                MAPEAMENTO_CURSOS[curso]
            )

            return (
                str(codigo).strip(),
                str(nome).strip(),
            )

        return (
            curso,
            curso,
        )

    # ========================================================================
    # TABELA
    # ========================================================================

    def _tabela_existe(self):

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
                        "imp_013_unidades_avaliacao",
                    )
                ).fetchone() is not None

        except Exception as exc:

            logger.error(
                "Erro ao verificar tabela: %s",
                exc
            )

            return False

    # ========================================================================
    # ÍNDICES
    # ========================================================================

    def _indice_existe(self, nome):

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
                    (nome,)
                ).fetchone() is not None

        except Exception:

            return False

    def _criar_indices(self):

        indices = [

            (
                "idx_imp013_codigoCurso",

                """
                CREATE INDEX idx_imp013_codigoCurso
                ON imp_013_unidades_avaliacao(
                    codigoCurso
                )
                """
            ),

            (
                "idx_imp013_codigoDisciplina",

                """
                CREATE INDEX idx_imp013_codigoDisciplina
                ON imp_013_unidades_avaliacao(
                    codigoDisciplina
                )
                """
            ),
        ]

        for nome, sql in indices:

            if self._indice_existe(nome):
                continue

            try:

                with get_db_connection(
                    database_name="qstione"
                ) as conn:

                    conn.execute(sql)
                    conn.commit()

            except Exception as exc:

                logger.warning(
                    "Índice %s: %s",
                    nome,
                    exc
                )

    # ========================================================================
    # CRIAÇÃO
    # ========================================================================

    def _criar_tabela(self):

        if not self._tabela_existe():

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_013_unidades_avaliacao (

                        codigoUnidade
                            NVARCHAR(200) NOT NULL,

                        nomeUnidade
                            NVARCHAR(64) NOT NULL,

                        codigoCurso
                            NVARCHAR(30) NULL,

                        codigoDisciplina
                            NVARCHAR(30) NULL,

                        ordemExibicao
                            INT NOT NULL,

                        codigoAgrupamento
                            NVARCHAR(200) NOT NULL,

                        data_criacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoUnidade
                        )
                    )
                    """
                )

                conn.commit()

                logger.info(
                    "🆕 Tabela criada."
                )

        self._criar_indices()

    # ========================================================================
    # CONSULTA LYCEUM
    # ========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém provas somente de turmas válidas.

        A faculdade é determinada pela cadeia:

            LY_PROVA
                 ↓
            LY_TURMA
                 ↓
            LY_CURSO.faculdade
        """

        if not PERIODOS_VIGENTES:

            logger.warning(
                "PERIODOS_VIGENTES está vazio."
            )

            return []

        if not FACULDADES_INCLUIDAS:

            logger.warning(
                "FACULDADES_INCLUIDAS está vazio."
            )

            return []

        sql = f"""
            SELECT DISTINCT

                p.ano,

                p.disciplina,

                p.prova,

                p.semestre,

                p.turma,

                p.nome,

                p.ordem,

                p.classificacao,

                t.curso,

                c.nome AS nome_curso

            FROM LY_PROVA p

            INNER JOIN LY_TURMA t

                ON t.ano = p.ano

               AND t.semestre = p.semestre

               AND t.turma = p.turma

               AND t.disciplina = p.disciplina

            LEFT JOIN LY_CURSO c

                ON c.curso = t.curso

            WHERE p.ano = ?

              AND p.semestre IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND p.prova IS NOT NULL

              AND LTRIM(RTRIM(
                  CAST(p.prova AS NVARCHAR(100))
              )) <> ''

              AND p.nome IS NOT NULL

              AND LTRIM(RTRIM(p.nome)) <> ''

              AND (
                    t.curso IS NULL

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(100))
                    )) = ''

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(100))
                    )) = '999'

                    OR c.faculdade IN (
                        {self.faculdades_placeholders}
                    )
              )

            ORDER BY
                p.ano,
                p.semestre,
                p.turma,
                p.disciplina,
                p.prova
        """

        params = [
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        ]

        try:

            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                rows = conn.execute(
                    sql,
                    tuple(params)
                ).fetchall()

        except Exception as exc:

            logger.exception(
                "❌ Erro ao consultar LY_PROVA: %s",
                exc
            )

            return []

        colunas = [
            "ano",
            "disciplina",
            "prova",
            "semestre",
            "turma",
            "nome",
            "ordem",
            "classificacao",
            "curso",
            "nome_curso",
        ]

        resultado = [
            dict(
                zip(
                    colunas,
                    row
                )
            )
            for row in rows
        ]

        logger.info(
            "📊 Provas encontradas: %d",
            len(resultado)
        )

        return resultado

    # ========================================================================
    # TRANSFORMAÇÃO
    # ========================================================================

    def transformar_dados(
        self,
        dados_lyceum
    ):

        dados = []

        for item in dados_lyceum:

            disciplina = str(
                item.get("disciplina") or ""
            ).strip()

            curso_original = str(
                item.get("curso") or ""
            ).strip()

            prova = str(
                item.get("prova") or ""
            ).strip()

            if not disciplina:
                continue

            if not prova:
                continue

            # ----------------------------------------------------------------
            # CURSO
            # ----------------------------------------------------------------

            curso_unificado, nome_curso_unificado = (
                self._curso_unificado(
                    curso_original
                )
            )

            if not nome_curso_unificado:

                nome_curso_unificado = str(
                    item.get(
                        "nome_curso"
                    )
                    or curso_unificado
                )

            # ----------------------------------------------------------------
            # DISCIPLINA
            # ----------------------------------------------------------------

            codigo_disciplina = (
                gerar_codigo_disciplina_curso(
                    disciplina,
                    nome_curso_unificado,
                    curso_unificado,
                )
            )

            codigo_disciplina = truncar_texto(
                codigo_disciplina,
                30
            )

            # ----------------------------------------------------------------
            # UNIDADE
            # ----------------------------------------------------------------

            codigo_unidade = (
                f"{codigo_disciplina}-{prova}"
            )

            codigo_unidade = truncar_texto(
                codigo_unidade,
                200
            )

            nome_unidade = (
                self.MAPEAMENTO_PROVA.get(
                    prova.upper(),
                    str(
                        item.get("nome")
                        or prova
                    ).strip()
                )
            )

            nome_unidade = truncar_texto(
                nome_unidade,
                64
            )

            # ----------------------------------------------------------------
            # ORDEM
            # ----------------------------------------------------------------

            ordem = item.get(
                "ordem"
            )

            if ordem is None:

                ordem_exibicao = 0

            else:

                ordem_exibicao = (
                    converter_inteiro(
                        ordem
                    )
                )

                if ordem_exibicao is None:
                    ordem_exibicao = 0

            dados.append(
                {
                    "codigoUnidade":
                        codigo_unidade,

                    "nomeUnidade":
                        nome_unidade,

                    "codigoCurso":
                        truncar_texto(
                            curso_unificado,
                            30
                        ),

                    "codigoDisciplina":
                        codigo_disciplina,

                    "ordemExibicao":
                        ordem_exibicao,

                    "codigoAgrupamento":
                        codigo_unidade,
                }
            )

        # --------------------------------------------------------------------
        # DEDUPLICAÇÃO
        # --------------------------------------------------------------------

        unicos = {}

        for registro in dados:

            unicos[
                registro["codigoUnidade"]
            ] = registro

        resultado = list(
            unicos.values()
        )

        resultado.sort(
            key=lambda x: (
                x["codigoDisciplina"],
                x["ordemExibicao"],
                x["codigoUnidade"],
            )
        )

        logger.info(
            "✅ Registros transformados: %d",
            len(resultado)
        )

        return resultado

    # ========================================================================
    # IMPORTAÇÃO
    # ========================================================================

    def importar_para_qstione(
        self,
        dados_transformados
    ):

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    DELETE
                    FROM imp_013_unidades_avaliacao
                    """
                )

                cursor = conn.cursor()

                for registro in (
                    dados_transformados
                ):

                    try:

                        cursor.execute(
                            """
                            INSERT INTO
                                imp_013_unidades_avaliacao
                            (
                                codigoUnidade,
                                nomeUnidade,
                                codigoCurso,
                                codigoDisciplina,
                                ordemExibicao,
                                codigoAgrupamento,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES
                            (
                                ?,
                                ?,
                                ?,
                                ?,
                                ?,
                                ?,
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                registro[
                                    "codigoUnidade"
                                ],

                                registro[
                                    "nomeUnidade"
                                ],

                                registro[
                                    "codigoCurso"
                                ],

                                registro[
                                    "codigoDisciplina"
                                ],

                                registro[
                                    "ordemExibicao"
                                ],

                                registro[
                                    "codigoAgrupamento"
                                ],
                            )
                        )

                        inseridos += 1

                    except Exception as exc:

                        erros += 1

                        logger.error(
                            "Erro em %s: %s",
                            registro[
                                "codigoUnidade"
                            ],
                            exc
                        )

                conn.commit()

        except Exception as exc:

            logger.exception(
                "❌ Erro durante reconstrução: %s",
                exc
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

    # ========================================================================
    # EXECUÇÃO
    # ========================================================================

    def executar_importacao(self):

        logger.info("=" * 80)

        logger.info(
            "IMPORTAÇÃO: imp_013_unidades_avaliacao"
        )

        logger.info(
            "ANO=%s | PERIODOS=%s | FACULDADES=%s",
            ANO_VIGENTE,
            PERIODOS_VIGENTES,
            FACULDADES_INCLUIDAS,
        )

        logger.info("=" * 80)

        dados = (
            self.obter_dados_lyceum()
        )

        transformados = (
            self.transformar_dados(
                dados
            )
        )

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        logger.info(
            "📈 Inseridos=%d | Erros=%d",
            resultado["total_inseridos"],
            resultado["total_erros"],
        )

        logger.info("=" * 80)

        return transformados


# ============================================================================
# EXECUÇÃO DIRETA
# ============================================================================

if __name__ == "__main__":

    ImportadorUnidadesAvaliacao().executar_importacao()
