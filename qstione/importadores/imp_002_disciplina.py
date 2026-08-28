"""
qstione/importadores/imp_002_disciplina.py

Importador independente de disciplinas para o Qstione.

REGRAS PRINCIPAIS
-----------------

1. LY_TURMA é a fonte de verdade para determinar quais disciplinas
   devem ser importadas.

2. Somente são consideradas turmas:
       - do ANO_VIGENTE;
       - dos PERIODOS_VIGENTES;
       - com SITUACAO_TURMA_VALIDA;
       - pertencentes às FACULDADES_INCLUIDAS.

3. O curso ORIGINAL da LY_TURMA é preservado durante todo o
   processamento.

4. Cursos NULL, vazios ou 999 representam COMPARTILHADA.

5. Para cursos reais, a faculdade é validada através de LY_CURSO.

6. LY_GRADE é utilizada somente para descobrir o menor período/série
   aplicável à disciplina.

7. A consulta de LY_GRADE utiliza SEMPRE o código ORIGINAL do curso.

   Exemplo:

       LY_TURMA.curso = 141

       consulta:
           LY_GRADE.curso = 141

   Somente depois disso:

       141 -> 056

   através do MAPEAMENTO_CURSOS.

8. Caso existam vários registros de LY_GRADE para a mesma combinação
   curso original + disciplina, será utilizada a menor série.

9. A disciplina é identificada juntamente com o CONTEXTO DE CURSO.

   Portanto:

       DISC001 + 999
       DISC001 + 056

   são contextos diferentes e ambos podem existir.

10. Cursos que possuem códigos alternativos continuam sendo consultados
    individualmente na LY_GRADE antes da unificação.

    Exemplo:

       056 -> 056
       141 -> 056

    Uma turma 056 consulta a grade 056.
    Uma turma 141 consulta a grade 141.

11. O código da disciplina é gerado com:

       gerar_codigo_disciplina_curso(
           disciplina,
           nome_curso_unificado,
           curso_unificado
       )

12. A tabela destino é reconstruída a cada execução.

13. O arquivo pode ser executado diretamente pelo botão PLAY do VS Code.
"""

import os
import sys
import logging


# =============================================================================
# PATH DO PROJETO
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


# =============================================================================
# LOG
# =============================================================================

logger = logging.getLogger(
    "imp_002_disciplina"
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


# =============================================================================
# MAPEAMENTO DE CURSOS
# =============================================================================

MAPEAMENTO_CURSOS = {

    "034": (
        "034",
        "ADMINISTRAÇÃO"
    ),

    "064": (
        "064",
        "CIÊNCIAS BIOLÓGICAS"
    ),

    "062": (
        "064",
        "CIÊNCIAS BIOLÓGICAS"
    ),

    "057": (
        "064",
        "CIÊNCIAS BIOLÓGICAS"
    ),

    "009": (
        "009",
        "CIÊNCIAS CONTÁBEIS"
    ),

    "023": (
        "009",
        "CIÊNCIAS CONTÁBEIS"
    ),

    "055": (
        "055",
        "CURSO SUPERIOR DE TECNOLOGIA EM GESTÃO DE RECURSOS HUMANOS"
    ),

    "056": (
        "056",
        "DESIGN"
    ),

    "141": (
        "056",
        "DESIGN"
    ),

    "031": (
        "031",
        "DIREITO"
    ),

    "065": (
        "065",
        "EDUCAÇÃO FÍSICA"
    ),

    "036": (
        "065",
        "EDUCAÇÃO FÍSICA"
    ),

    "037": (
        "065",
        "EDUCAÇÃO FÍSICA"
    ),

    "013": (
        "013",
        "ENFERMAGEM"
    ),

    "079": (
        "079",
        "ENGENHARIA"
    ),

    "006": (
        "006",
        "ENGENHARIA CIVIL"
    ),

    "020": (
        "006",
        "ENGENHARIA CIVIL"
    ),

    "097": (
        "097",
        "ENGENHARIA DA COMPUTAÇÃO"
    ),

    "059": (
        "059",
        "ENGENHARIA DE PRODUÇÃO"
    ),

    "142": (
        "059",
        "ENGENHARIA DE PRODUÇÃO"
    ),

    "044": (
        "044",
        "ENGENHARIA ELÉTRICA"
    ),

    "139": (
        "044",
        "ENGENHARIA ELÉTRICA"
    ),

    "017": (
        "017",
        "ENGENHARIA MECÂNICA"
    ),

    "132": (
        "017",
        "ENGENHARIA MECÂNICA"
    ),

    "126": (
        "126",
        "FARMÁCIA"
    ),

    "060": (
        "060",
        "JORNALISMO"
    ),

    "014": (
        "014",
        "MEDICINA"
    ),

    "024": (
        "024",
        "NUTRIÇÃO"
    ),

    "007": (
        "007",
        "ODONTOLOGIA"
    ),

    "130": (
        "007",
        "ODONTOLOGIA"
    ),

    "128": (
        "128",
        "PEDAGOGIA"
    ),

    "145": (
        "145",
        "PSICOLOGIA"
    ),

    "061": (
        "061",
        "PUBLICIDADE E PROPAGANDA"
    ),

    "025": (
        "025",
        "SERVIÇO SOCIAL"
    ),

    "019": (
        "019",
        "SISTEMAS DE INFORMAÇÃO"
    ),

        "080": (
        "113",
        "TÉCNICO EM ENFERMAGEM"
    ),

        "113": (
        "113",
        "TÉCNICO EM ENFERMAGEM"
    ),

    "999": (
        "999",
        "COMPARTILHADA"
    ),
}


# =============================================================================
# CONSTANTES
# =============================================================================

CURSO_COMPARTILHADO = "999"


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorDisciplina:
    """
    Importador de disciplinas do Lyceum para o Qstione.

    A seleção parte de LY_TURMA. As tabelas complementares não podem
    eliminar uma turma já considerada válida.
    """

    def __init__(self):

        self.periodos_placeholders = ",".join(
            "?" for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?" for _ in FACULDADES_INCLUIDAS
        )

        logger.info(
            "=" * 90
        )

        logger.info(
            "INÍCIO imp_002_disciplina"
        )

        logger.info(
            "ANO=%s | PERIODOS=%s | FACULDADES=%s | SIT_TURMA=%s",
            ANO_VIGENTE,
            PERIODOS_VIGENTES,
            FACULDADES_INCLUIDAS,
            SITUACAO_TURMA_VALIDA,
        )

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela
    ):

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                row = conn.execute(
                    """
                    SELECT 1
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ?
                      AND TABLE_TYPE = 'BASE TABLE'
                    """,
                    (
                        nome_tabela,
                    )
                ).fetchone()

                return row is not None

        except Exception:

            logger.exception(
                "Erro verificando tabela %s",
                nome_tabela
            )

            return False

    # =========================================================================
    # ÍNDICE
    # =========================================================================

    def _indice_existe(
        self,
        nome_indice
    ):

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                row = conn.execute(
                    """
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = ?
                    """,
                    (
                        nome_indice,
                    )
                ).fetchone()

                return row is not None

        except Exception:

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):

        if not self._tabela_existe(
            "imp_002_disciplina"
        ):

            logger.info(
                "🆕 Criando tabela imp_002_disciplina..."
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_002_disciplina (

                        codigoDisciplina NVARCHAR(30) NOT NULL,

                        nomeDisciplina NVARCHAR(255) NOT NULL,

                        codigoCurso NVARCHAR(30) NULL,

                        periodo INT NULL,

                        serie_ideal INT NULL,

                        cargaHoraria INT NULL,

                        tipoDisciplina NVARCHAR(30) NULL,

                        data_criacao DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoDisciplina
                        )
                    )
                    """
                )

                conn.commit()

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):

        indices = [

            (
                "idx_imp002_codigoCurso",

                """
                CREATE INDEX idx_imp002_codigoCurso
                ON imp_002_disciplina(codigoCurso)
                """
            ),

            (
                "idx_imp002_periodo",

                """
                CREATE INDEX idx_imp002_periodo
                ON imp_002_disciplina(periodo)
                """
            ),
        ]

        for nome, sql in indices:

            if self._indice_existe(
                nome
            ):
                continue

            try:

                with get_db_connection(
                    database_name="qstione"
                ) as conn:

                    conn.execute(sql)
                    conn.commit()

            except Exception:

                logger.exception(
                    "Erro criando índice %s",
                    nome
                )

    # =========================================================================
    # NORMALIZAÇÃO DO CURSO
    # =========================================================================

    @staticmethod
    def _normalizar_curso(
        curso
    ):
        """
        Normaliza o curso somente APÓS a consulta da grade.

        NULL, vazio e 999 representam COMPARTILHADA.
        """

        if curso is None:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        curso = str(
            curso
        ).strip()

        if not curso:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        if curso == CURSO_COMPARTILHADO:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        if curso in MAPEAMENTO_CURSOS:

            codigo, nome = (
                MAPEAMENTO_CURSOS[
                    curso
                ]
            )

            return (
                str(codigo).strip(),
                str(nome).strip()
            )

        return (
            curso,
            curso
        )

    # =========================================================================
    # CONSULTA DA GRADE
    # =========================================================================

    def _obter_menor_serie_grade(
        self,
        curso_original,
        disciplina
    ):
        """
        Obtém a menor serie_ideal da LY_GRADE usando o código ORIGINAL
        do curso.

        IMPORTANTE:

        Não é feita nenhuma unificação do curso antes da consulta.

        Exemplo:

            curso_original = 141

        consulta:

            WHERE g.curso = 141

        Somente depois disso o 141 será convertido para 056.

        Retorna:
            menor serie_ideal encontrada
            ou None.
        """

        if curso_original is None:
            return None

        curso_original = str(
            curso_original
        ).strip()

        if not curso_original:
            return None

        if curso_original == CURSO_COMPARTILHADO:
            return None

        sql = """
            SELECT MIN(
                TRY_CONVERT(
                    INT,
                    NULLIF(
                        LTRIM(RTRIM(
                            CAST(g.serie_ideal AS NVARCHAR(30))
                        )),
                        ''
                    )
                )
            )
            FROM LY_GRADE g

            WHERE g.curso = ?
              AND g.disciplina = ?
        """

        try:

            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                row = conn.execute(
                    sql,
                    (
                        curso_original,
                        disciplina,
                    )
                ).fetchone()

            if not row:
                return None

            valor = row[0]

            if valor is None:
                return None

            valor = converter_inteiro(
                valor
            )

            if valor is None:
                return None

            return valor

        except Exception:

            logger.exception(
                "Erro consultando LY_GRADE | curso=%s | disciplina=%s",
                curso_original,
                disciplina
            )

            return None

    # =========================================================================
    # CONSULTA DAS TURMAS
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém TODAS as disciplinas que possuem pelo menos uma turma
        válida dentro dos filtros.

        LY_TURMA é a fonte de verdade.

        Nenhuma tabela complementar é utilizada para decidir se a
        turma existe.

        O curso original é preservado.
        """

        logger.info(
            "🔎 Consultando turmas válidas no Lyceum..."
        )

        sql = f"""
            SELECT DISTINCT

                t.ano,

                t.semestre,

                t.turma,

                t.disciplina,

                t.curso,

                d.nome AS nome_disciplina,

                c.faculdade

            FROM LY_TURMA t

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            LEFT JOIN LY_DISCIPLINA d
                ON d.disciplina = t.disciplina

            WHERE t.ano = ?

              AND t.semestre IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND t.disciplina IS NOT NULL

              AND LTRIM(RTRIM(
                  CAST(t.disciplina AS NVARCHAR(100))
              )) <> ''

              AND (

                    -- =====================================================
                    -- TURMA COMPARTILHADA
                    -- =====================================================

                    t.curso IS NULL

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(30))
                    )) = ''

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(30))
                    )) = '999'

                    -- =====================================================
                    -- TURMA DE CURSO REAL
                    -- =====================================================

                    OR c.faculdade IN (
                        {self.faculdades_placeholders}
                    )
              )

            ORDER BY

                t.ano,
                t.semestre,
                t.turma,
                t.disciplina,
                t.curso
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,

            SITUACAO_TURMA_VALIDA,

            *FACULDADES_INCLUIDAS,
        )

        try:

            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                rows = conn.execute(
                    sql,
                    params
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro consultando LY_TURMA."
            )

            return []

        colunas = [

            "ano",
            "semestre",
            "turma",
            "disciplina",
            "curso",
            "nome_disciplina",
            "faculdade",
        ]

        dados = [
            dict(
                zip(
                    colunas,
                    row
                )
            )
            for row in rows
        ]

        logger.info(
            "📊 Turmas válidas encontradas: %d",
            len(dados)
        )

        # ---------------------------------------------------------------------
        # Diagnóstico por contexto
        # ---------------------------------------------------------------------

        contextos = set()

        for item in dados:

            disciplina = str(
                item.get(
                    "disciplina"
                ) or ""
            ).strip()

            curso = item.get(
                "curso"
            )

            curso_str = (
                str(curso).strip()
                if curso is not None
                else ""
            )

            contextos.add(
                (
                    disciplina,
                    curso_str
                )
            )

        logger.info(
            "📚 Contextos disciplina/curso encontrados: %d",
            len(contextos)
        )

        return dados

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum
    ):
        """
        Transforma as turmas em disciplinas do Qstione.

        O curso original é utilizado para consultar LY_GRADE.

        Depois da consulta da grade, o curso é unificado.

        Quando houver várias grades para o mesmo curso original e
        disciplina, a menor série será utilizada.
        """

        registros = {}

        for item in dados_lyceum:

            disciplina = str(
                item.get(
                    "disciplina"
                ) or ""
            ).strip()

            if not disciplina:
                continue

            nome_disciplina = str(
                item.get(
                    "nome_disciplina"
                ) or disciplina
            ).strip()

            curso_original = item.get(
                "curso"
            )

            # ================================================================
            # CURSO ORIGINAL
            # ================================================================

            curso_original_str = (
                str(
                    curso_original
                ).strip()
                if curso_original is not None
                else ""
            )

            curso_eh_compartilhado = (
                curso_original is None
                or curso_original_str == ""
                or curso_original_str == CURSO_COMPARTILHADO
            )

            # ================================================================
            # GRADE
            # ================================================================

            serie_grade = None

            if not curso_eh_compartilhado:

                serie_grade = (
                    self._obter_menor_serie_grade(
                        curso_original_str,
                        disciplina
                    )
                )

            # ================================================================
            # CURSO UNIFICADO
            #
            # IMPORTANTE:
            #
            # A unificação acontece SOMENTE depois da consulta da grade.
            # ================================================================

            curso_unificado, nome_curso_unificado = (
                self._normalizar_curso(
                    curso_original
                )
            )

            # ================================================================
            # PERÍODO
            # ================================================================

            if serie_grade is not None:

                periodo = serie_grade

            else:

                periodo = 1

            if periodo <= 0:

                periodo = 1

            # ================================================================
            # CÓDIGO DA DISCIPLINA
            # ================================================================

            codigo_disciplina = (
                gerar_codigo_disciplina_curso(
                    disciplina,
                    nome_curso_unificado,
                    curso_unificado
                )
            )

            codigo_disciplina = truncar_texto(
                codigo_disciplina,
                30
            )

            # ================================================================
            # CHAVE LÓGICA
            # ================================================================
            #
            # O contexto original da turma é usado como parte da
            # deduplicação.
            #
            # Isso impede que:
            #
            #   DISC001 / 999
            #
            # seja confundido com:
            #
            #   DISC001 / 056
            #
            # ================================================================

            chave = (
                disciplina,
                curso_original_str
            )

            registro = {

                "codigoDisciplina":
                    codigo_disciplina,

                "nomeDisciplina":
                    truncar_texto(
                        nome_disciplina,
                        255
                    ),

                "codigoCurso":
                    truncar_texto(
                        curso_unificado,
                        30
                    ),

                "periodo":
                    periodo,

                "serie_ideal":
                    serie_grade,

                "cargaHoraria":
                    None,

                "tipoDisciplina":
                    None,

                # Informações auxiliares não gravadas
                # diretamente na tabela.
                "_curso_original":
                    curso_original_str,

                "_disciplina":
                    disciplina,

                "_nome_curso":
                    nome_curso_unificado,
            }

            # ================================================================
            # DEDUPLICAÇÃO
            # ================================================================
            #
            # Se a mesma disciplina/contexto original aparecer em várias
            # turmas, mantemos apenas um registro.
            #
            # Se houver diferentes séries, usamos a MENOR.
            # ================================================================

            if chave not in registros:

                registros[chave] = registro

            else:

                existente = registros[
                    chave
                ]

                periodo_existente = (
                    existente.get(
                        "periodo"
                    )
                    or 1
                )

                periodo_novo = (
                    registro.get(
                        "periodo"
                    )
                    or 1
                )

                if periodo_novo < periodo_existente:

                    existente[
                        "periodo"
                    ] = periodo_novo

                    existente[
                        "serie_ideal"
                    ] = registro[
                        "serie_ideal"
                    ]

        dados = list(
            registros.values()
        )

        # =====================================================================
        # SEGUNDA DEDUPLICAÇÃO
        # =====================================================================
        #
        # Após a unificação, dois códigos originais podem apontar para o
        # mesmo curso.
        #
        # Exemplo:
        #
        #   056 -> 056
        #   141 -> 056
        #
        # Se gerarem exatamente o mesmo codigoDisciplina e mesmo período,
        # precisamos consolidar.
        #
        # Caso o período seja diferente, os registros continuam distintos
        # somente se o modelo atual de codigoDisciplina permitir isso.
        # =====================================================================

        finais = {}

        for registro in dados:

            chave_final = (
                registro[
                    "codigoDisciplina"
                ]
            )

            if chave_final not in finais:

                finais[
                    chave_final
                ] = registro

                continue

            existente = finais[
                chave_final
            ]

            periodo_existente = (
                existente.get(
                    "periodo"
                )
                or 1
            )

            periodo_novo = (
                registro.get(
                    "periodo"
                )
                or 1
            )

            if periodo_novo < periodo_existente:

                finais[
                    chave_final
                ] = registro

        dados_finais = list(
            finais.values()
        )

        logger.info(
            "🔄 Registros transformados: %d",
            len(dados_finais)
        )

        # =====================================================================
        # DIAGNÓSTICO
        # =====================================================================

        compartilhadas = 0
        cursos_reais = 0

        for registro in dados_finais:

            if registro[
                "codigoCurso"
            ] == CURSO_COMPARTILHADO:

                compartilhadas += 1

            else:

                cursos_reais += 1

        logger.info(
            "📚 Disciplinas de cursos reais: %d",
            cursos_reais
        )

        logger.info(
            "🌐 Disciplinas compartilhadas: %d",
            compartilhadas
        )

        return dados_finais

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados
    ):
        """
        Reconstrói a tabela imp_002_disciplina.
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                logger.info(
                    "🧹 Limpando tabela destino..."
                )

                conn.execute(
                    """
                    DELETE FROM imp_002_disciplina
                    """
                )

                cursor = conn.cursor()

                for registro in (
                    dados_transformados
                ):

                    try:

                        cursor.execute(
                            """
                            INSERT INTO imp_002_disciplina
                            (
                                codigoDisciplina,
                                nomeDisciplina,
                                codigoCurso,
                                periodo,
                                serie_ideal,
                                cargaHoraria,
                                tipoDisciplina,
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
                                ?,
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                registro[
                                    "codigoDisciplina"
                                ],

                                registro[
                                    "nomeDisciplina"
                                ],

                                registro[
                                    "codigoCurso"
                                ],

                                registro[
                                    "periodo"
                                ],

                                registro[
                                    "serie_ideal"
                                ],

                                registro[
                                    "cargaHoraria"
                                ],

                                registro[
                                    "tipoDisciplina"
                                ],
                            )
                        )

                        inseridos += 1

                    except Exception as e:

                        erros += 1

                        logger.error(
                            "❌ Erro inserindo disciplina "
                            "%s: %s",

                            registro[
                                "codigoDisciplina"
                            ],

                            e
                        )

                conn.commit()

        except Exception:

            logger.exception(
                "❌ Erro durante reconstrução da tabela."
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

        print("=" * 90)

        print(
            "IMPORTAÇÃO: imp_002_disciplina"
        )

        print("=" * 90)

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
            f"📚 Situação: {SITUACAO_TURMA_VALIDA}"
        )

        print("=" * 90)

        # =====================================================================
        # CONSULTA
        # =====================================================================

        dados = (
            self.obter_dados_lyceum()
        )

        print(
            f"📊 Turmas encontradas: {len(dados)}"
        )

        # =====================================================================
        # TRANSFORMAÇÃO
        # =====================================================================

        transformados = (
            self.transformar_dados(
                dados
            )
        )

        print(
            f"✅ Disciplinas finais: "
            f"{len(transformados)}"
        )

        # =====================================================================
        # IMPORTAÇÃO
        # =====================================================================

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']}"
        )

        print(
            f"❌ Erros: "
            f"{resultado['total_erros']}"
        )

        print("=" * 90)

        logger.info(
            "FIM imp_002_disciplina"
        )

        return transformados


# =============================================================================
# PLAY DO VS CODE
# =============================================================================

if __name__ == "__main__":

    ImportadorDisciplina().executar_importacao()