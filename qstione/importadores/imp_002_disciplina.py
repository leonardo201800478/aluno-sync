#!/usr/bin/env python3
# qstione/importadores/imp_002_disciplina.py

"""
Importador independente para imp_002_disciplina.

FONTE DE VERDADE
----------------
A unidade de origem é a TURMA existente em LY_TURMA.

    LY_TURMA
       |
       +-- disciplina
       |
       +-- curso
       |
       +-- ano
       |
       +-- semestre
       |
       +-- situação
       |
       +-- turma
       |
       +-- LY_CURSO.faculdade
       |
       +-- LY_DISCIPLINA
       |
       +-- LY_GRADE

REGRAS DE NEGÓCIO
-----------------

1. A existência da disciplina no importador NÃO depende de:
       - LY_MATRICULA
       - LY_ALUNO
       - LY_TURMA_DOCENTE

   Basta existir uma turma válida em LY_TURMA.

2. A turma deve pertencer a:
       ANO_VIGENTE
       PERIODOS_VIGENTES
       SITUACAO_TURMA_VALIDA

3. O curso é SEMPRE obtido de:
       LY_TURMA.curso

   Nunca:
       LY_MATRICULA.curso
       LY_GRADE.curso
       LY_DISCIPLINA.curso

4. Quando LY_TURMA.curso for NULL ou vazio:

       curso = 999
       nome_curso = COMPARTILHADA

   A turma continua válida mesmo sem curso.

5. Quando LY_TURMA.curso estiver preenchido:

       LY_TURMA.curso
            |
            v
       LY_CURSO.faculdade

   A faculdade precisa estar em:
       FACULDADES_INCLUIDAS

6. A disciplina é identificada pelo contexto da própria turma.

7. O código final da disciplina é gerado por:

       gerar_codigo_disciplina_curso(
           disciplina,
           nome_curso_unificado,
           curso_unificado
       )

8. Cursos duplicados/alternativos são unificados por
   MAPEAMENTO_CURSOS.

9. LY_GRADE é utilizada somente para obter serie_ideal,
   usando o curso REAL da turma.

10. Para turma compartilhada (curso 999), não existe curso
    real para relacionar com LY_GRADE. Nesse caso, o período
    será obtido somente se houver uma informação aplicável;
    caso contrário, será utilizado 1.

11. A área de conhecimento da disciplina é utilizada como
    filtro.

    Áreas:
       - presentes em AREAS_CONHECIMENTO_INCLUIDAS
       - NULL
       - vazia

    são aceitas.

12. Cada execução reconstrói integralmente a tabela:

       DELETE FROM imp_002_disciplina

    antes dos novos INSERTs.

13. O arquivo pode ser executado diretamente pelo botão
    Play do VS Code.
"""

import os
import sys
import logging


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
    converter_inteiro,
    gerar_codigo_disciplina_curso,
    truncar_texto,
)

from qstione.core.validacoes import (
    validar_codigo_disciplina,
    validar_codigo_curso,
)

from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    AREAS_CONHECIMENTO_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)


# =============================================================================
# MAPEAMENTO DE CURSOS
# =============================================================================
#
# ESTE MAPEAMENTO É A FONTE CENTRAL DOS CÓDIGOS UNIFICADOS.
#
# Os demais importadores devem importar MAPEAMENTO_CURSOS deste arquivo
# em vez de criar seus próprios mapeamentos.
#
# =============================================================================

MAPEAMENTO_CURSOS = {
    "034": ("034", "ADMINISTRAÇÃO"),

    "064": ("064", "CIÊNCIAS BIOLÓGICAS"),
    "062": ("064", "CIÊNCIAS BIOLÓGICAS"),
    "057": ("064", "CIÊNCIAS BIOLÓGICAS"),

    "009": ("009", "CIÊNCIAS CONTÁBEIS"),
    "023": ("009", "CIÊNCIAS CONTÁBEIS"),

    "055": (
        "055",
        "CURSO SUPERIOR DE TECNOLOGIA EM GESTÃO DE RECURSOS HUMANOS",
    ),

    "056": ("056", "DESIGN"),
    "141": ("056", "DESIGN"),

    "031": ("031", "DIREITO"),

    "065": ("065", "EDUCAÇÃO FÍSICA"),
    "036": ("065", "EDUCAÇÃO FÍSICA"),
    "037": ("065", "EDUCAÇÃO FÍSICA"),

    "013": ("013", "ENFERMAGEM"),

    "079": ("079", "ENGENHARIA"),

    "006": ("006", "ENGENHARIA CIVIL"),
    "020": ("006", "ENGENHARIA CIVIL"),

    "097": ("097", "ENGENHARIA DA COMPUTAÇÃO"),

    "059": ("059", "ENGENHARIA DE PRODUÇÃO"),
    "142": ("059", "ENGENHARIA DE PRODUÇÃO"),

    "044": ("044", "ENGENHARIA ELÉTRICA"),
    "139": ("044", "ENGENHARIA ELÉTRICA"),

    "017": ("017", "ENGENHARIA MECÂNICA"),
    "132": ("017", "ENGENHARIA MECÂNICA"),

    "126": ("126", "FARMÁCIA"),

    "060": ("060", "JORNALISMO"),

    "014": ("014", "MEDICINA"),

    "024": ("024", "NUTRIÇÃO"),

    "007": ("007", "ODONTOLOGIA"),
    "130": ("007", "ODONTOLOGIA"),

    "128": ("128", "PEDAGOGIA"),

    "145": ("145", "PSICOLOGIA"),

    "061": ("061", "PUBLICIDADE E PROPAGANDA"),

    "025": ("025", "SERVIÇO SOCIAL"),

    "019": ("019", "SISTEMAS DE INFORMAÇÃO"),

    "999": ("999", "COMPARTILHADA"),
}


# =============================================================================
# LOG
# =============================================================================

LOG_DIR = os.path.join(
    ROOT,
    "logs",
)

os.makedirs(
    LOG_DIR,
    exist_ok=True,
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "imp_002_disciplina.log",
)

logger = logging.getLogger(
    "imp_002_disciplina"
)

logger.setLevel(
    logging.DEBUG
)

logger.handlers.clear()

file_handler = logging.FileHandler(
    LOG_FILE,
    encoding="utf-8",
)

file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)

logger.addHandler(
    file_handler
)

logger.propagate = False


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorDisciplinas:
    """
    Importador de disciplinas baseado nas turmas reais do Lyceum.
    """

    def __init__(self):

        self.periodos_placeholders = ",".join(
            "?" for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?" for _ in FACULDADES_INCLUIDAS
        )

        self.areas = [
            area
            for area in AREAS_CONHECIMENTO_INCLUIDAS
            if area not in (None, "")
        ]

        self.areas_placeholders = ",".join(
            "?" for _ in self.areas
        )

        logger.info("=" * 90)

        logger.info(
            "INÍCIO imp_002_disciplina"
        )

        logger.info(
            "ANO_VIGENTE=%s",
            ANO_VIGENTE
        )

        logger.info(
            "PERIODOS_VIGENTES=%s",
            PERIODOS_VIGENTES
        )

        logger.info(
            "FACULDADES_INCLUIDAS=%s",
            FACULDADES_INCLUIDAS
        )

        logger.info(
            "AREAS_CONHECIMENTO_INCLUIDAS=%s",
            AREAS_CONHECIMENTO_INCLUIDAS
        )

        logger.info(
            "SITUACAO_TURMA_VALIDA=%s",
            SITUACAO_TURMA_VALIDA
        )

        logger.info(
            "LOG_FILE=%s",
            LOG_FILE
        )

    # =========================================================================
    # NORMALIZAÇÃO DE CURSO
    # =========================================================================

    @staticmethod
    def normalizar_curso(curso):
        """
        Normaliza o código do curso utilizando MAPEAMENTO_CURSOS.

        Parameters
        ----------
        curso:
            Código original de LY_TURMA.curso.

        Returns
        -------
        tuple[str, str]
            Código e nome do curso unificado.

        Examples
        --------
        020 -> 006 / ENGENHARIA CIVIL

        062 -> 064 / CIÊNCIAS BIOLÓGICAS

        NULL -> 999 / COMPARTILHADA
        """

        if curso is None:
            return (
                "999",
                "COMPARTILHADA",
            )

        curso = str(curso).strip()

        if not curso:
            return (
                "999",
                "COMPARTILHADA",
            )

        if curso in MAPEAMENTO_CURSOS:

            curso_unificado, nome_curso = (
                MAPEAMENTO_CURSOS[curso]
            )

            return (
                str(curso_unificado),
                str(nome_curso),
            )

        return (
            curso,
            curso,
        )

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela: str,
    ) -> bool:
        """
        Verifica se uma tabela existe no banco Qstione.
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

            logger.warning(
                "Erro verificando tabela %s: %s",
                nome_tabela,
                e,
            )

            return False

    # =========================================================================
    # ÍNDICE
    # =========================================================================

    def _indice_existe(
        self,
        nome_indice: str,
    ) -> bool:
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

        except Exception as e:

            logger.warning(
                "Erro verificando índice %s: %s",
                nome_indice,
                e,
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela destino caso ela não exista.
        """

        if not self._tabela_existe(
            "imp_002_disciplina"
        ):

            logger.info(
                "Criando tabela imp_002_disciplina..."
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_002_disciplina (
                        codigoDisciplina NVARCHAR(30) NOT NULL,
                        nomeDisciplina NVARCHAR(100) NOT NULL,
                        codigoCurso NVARCHAR(30) NOT NULL,
                        periodo INTEGER NOT NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoDisciplina,
                            codigoCurso,
                            periodo
                        )
                    )
                    """
                )

                conn.commit()

            logger.info(
                "Tabela imp_002_disciplina criada."
            )

        # ---------------------------------------------------------------------
        # ÍNDICES
        # ---------------------------------------------------------------------

        indices = [

            (
                "idx_disciplinas_curso",
                """
                CREATE INDEX idx_disciplinas_curso
                ON imp_002_disciplina(codigoCurso)
                """,
            ),

            (
                "idx_disciplinas_nome",
                """
                CREATE INDEX idx_disciplinas_nome
                ON imp_002_disciplina(nomeDisciplina)
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

                logger.info(
                    "Índice criado: %s",
                    nome_indice,
                )

            except Exception as e:

                logger.warning(
                    "Índice %s não pôde ser criado: %s",
                    nome_indice,
                    e,
                )

    # =========================================================================
    # CONSULTA PRINCIPAL
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém as disciplinas diretamente das turmas válidas.

        IMPORTANTE
        ----------

        Não existe JOIN com:

            LY_MATRICULA
            LY_ALUNO
            LY_TURMA_DOCENTE

        Portanto uma turma é válida independentemente de possuir:

            aluno
            docente

        A faculdade é validada somente quando a turma possui
        curso definido.

        Para turma compartilhada:

            t.curso IS NULL

        o registro é preservado.
        """

        query = f"""
            SELECT DISTINCT

                t.disciplina,

                d.nome AS nome_disciplina,

                t.curso,

                g.serie_ideal,

                t.turma,

                t.ano,

                t.semestre

            FROM LY_TURMA t

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            LEFT JOIN LY_DISCIPLINA d
                ON d.disciplina = t.disciplina

            LEFT JOIN LY_GRADE g
                ON g.disciplina = t.disciplina
               AND g.curso = t.curso

            WHERE t.ano = ?

              AND t.semestre IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND (
                    t.curso IS NULL

                    OR c.faculdade IN (
                        {self.faculdades_placeholders}
                    )
                  )

              AND (
                    d.area_conhecimento IN (
                        {self.areas_placeholders}
                    )

                    OR d.area_conhecimento IS NULL

                    OR LTRIM(RTRIM(d.area_conhecimento)) = ''
                  )

            ORDER BY
                t.disciplina,
                t.curso,
                t.turma
        """

        params = [
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
            *self.areas,
        ]

        logger.info(
            "Consultando LY_TURMA..."
        )

        logger.info(
            "A consulta NÃO depende de aluno ou docente."
        )

        with get_db_connection() as conn:

            cursor = conn.cursor()

            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

        logger.info(
            "Linhas de turmas/disciplina retornadas: %d",
            len(rows),
        )

        return rows

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum,
    ):
        """
        Consolida as turmas em combinações:

            disciplina
            +
            curso unificado

        e obtém o menor serie_ideal disponível.

        A combinação é baseada no curso da própria turma.
        """

        disciplinas = {}

        for (
            disciplina,
            nome_disciplina,
            curso,
            serie_ideal,
            turma,
            ano,
            semestre,
        ) in dados_lyceum:

            # -----------------------------------------------------------------
            # DISCIPLINA
            # -----------------------------------------------------------------

            if not validar_codigo_disciplina(
                disciplina
            ):

                logger.warning(
                    "Código de disciplina inválido: %s",
                    disciplina,
                )

                continue

            disciplina = str(
                disciplina
            ).strip()

            # -----------------------------------------------------------------
            # CURSO
            # -----------------------------------------------------------------

            curso_unificado, nome_curso_unificado = (
                self.normalizar_curso(
                    curso
                )
            )

            # -----------------------------------------------------------------
            # REGISTRO DA DISCIPLINA
            # -----------------------------------------------------------------

            if disciplina not in disciplinas:

                disciplinas[disciplina] = {
                    "nome_disciplina": (
                        nome_disciplina
                    ),
                    "cursos": {},
                }

            if (
                curso_unificado
                not in disciplinas[disciplina]["cursos"]
            ):

                disciplinas[disciplina]["cursos"][
                    curso_unificado
                ] = {
                    "nome_curso": (
                        nome_curso_unificado
                    ),
                    "periodos": set(),
                    "turmas": set(),
                }

            curso_info = (
                disciplinas[disciplina]["cursos"][
                    curso_unificado
                ]
            )

            # -----------------------------------------------------------------
            # TURMA
            # -----------------------------------------------------------------

            if turma is not None:

                curso_info["turmas"].add(
                    str(turma).strip()
                )

            # -----------------------------------------------------------------
            # PERÍODO
            # -----------------------------------------------------------------

            if serie_ideal is not None:

                try:

                    periodo = converter_inteiro(
                        serie_ideal
                    )

                    if periodo is not None:

                        curso_info[
                            "periodos"
                        ].add(
                            periodo
                        )

                except Exception:

                    logger.warning(
                        "Não foi possível converter "
                        "serie_ideal=%s | disciplina=%s | curso=%s",
                        serie_ideal,
                        disciplina,
                        curso_unificado,
                    )

        # =========================================================================
        # CONVERSÃO FINAL
        # =========================================================================

        dados_transformados = []

        cont_periodo_zero = 0

        for disciplina, info in disciplinas.items():

            nome_disciplina_original = (
                info["nome_disciplina"]
            )

            # ---------------------------------------------------------------------
            # NOME DA DISCIPLINA
            # ---------------------------------------------------------------------

            if nome_disciplina_original:

                nome_disciplina = truncar_texto(
                    str(
                        nome_disciplina_original
                    ).strip(),
                    100,
                )

            else:

                nome_disciplina = truncar_texto(
                    disciplina,
                    100,
                )

                logger.debug(
                    "Nome da disciplina não encontrado: %s",
                    disciplina,
                )

            # ---------------------------------------------------------------------
            # CURSOS
            # ---------------------------------------------------------------------

            for (
                curso_unificado,
                curso_data,
            ) in info["cursos"].items():

                nome_curso = (
                    curso_data["nome_curso"]
                )

                periodos = (
                    curso_data["periodos"]
                )

                turmas = (
                    curso_data["turmas"]
                )

                # -------------------------------------------------------------
                # PERÍODO
                # -------------------------------------------------------------

                if not periodos:

                    periodo = 1

                    logger.warning(
                        "Sem série/período em LY_GRADE "
                        "para disciplina=%s curso=%s "
                        "turmas=%s. Utilizando período=1.",
                        disciplina,
                        curso_unificado,
                        sorted(turmas),
                    )

                else:

                    periodo_raw = min(
                        periodos
                    )

                    periodo = converter_inteiro(
                        periodo_raw
                    )

                    if periodo == 0:

                        periodo = 1

                        cont_periodo_zero += 1

                        logger.warning(
                            "Período 0 convertido para 1 | "
                            "disciplina=%s | curso=%s",
                            disciplina,
                            curso_unificado,
                        )

                # -------------------------------------------------------------
                # VALIDAÇÃO DO PERÍODO
                # -------------------------------------------------------------

                if (
                    periodo is None
                    or periodo < 1
                ):

                    logger.warning(
                        "Período inválido | "
                        "disciplina=%s | curso=%s | periodo=%s",
                        disciplina,
                        curso_unificado,
                        periodo,
                    )

                    continue

                # -------------------------------------------------------------
                # VALIDAÇÃO DO CURSO
                # -------------------------------------------------------------

                if curso_unificado != "999":

                    if not validar_codigo_curso(
                        curso_unificado
                    ):

                        logger.warning(
                            "Código de curso inválido | "
                            "disciplina=%s | curso=%s",
                            disciplina,
                            curso_unificado,
                        )

                        continue

                # -------------------------------------------------------------
                # CÓDIGO DA DISCIPLINA
                # -------------------------------------------------------------

                codigo_disciplina_final = (
                    gerar_codigo_disciplina_curso(
                        disciplina,
                        nome_curso,
                        curso_unificado,
                    )
                )

                codigo_disciplina_final = (
                    truncar_texto(
                        codigo_disciplina_final,
                        30,
                    )
                )

                # -------------------------------------------------------------
                # REGISTRO
                # -------------------------------------------------------------

                dados_transformados.append(
                    {
                        "codigoDisciplina": (
                            codigo_disciplina_final
                        ),

                        "nomeDisciplina": (
                            nome_disciplina
                        ),

                        "codigoCurso": (
                            str(
                                curso_unificado
                            )[:30]
                        ),

                        "periodo": periodo,
                    }
                )

        if cont_periodo_zero:

            logger.info(
                "Total de períodos 0 convertidos para 1: %d",
                cont_periodo_zero,
            )

        return dados_transformados

    # =========================================================================
    # LIMPEZA
    # =========================================================================

    def limpar_tabela(self):
        """
        Remove todos os registros existentes antes da nova carga.
        """

        self._criar_tabela()

        logger.info(
            "Limpando tabela imp_002_disciplina..."
        )

        with get_db_connection(
            database_name="qstione"
        ) as conn:

            conn.execute(
                """
                DELETE FROM imp_002_disciplina
                """
            )

            conn.commit()

        logger.info(
            "Tabela imp_002_disciplina limpa."
        )

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ):
        """
        Reconstrói a tabela imp_002_disciplina.

        Não utiliza MERGE porque a regra dos importadores deste projeto
        é reconstruir integralmente a tabela a cada execução.
        """

        self._criar_tabela()

        total_inseridos = 0
        total_erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                # -------------------------------------------------------------
                # LIMPA
                # -------------------------------------------------------------

                logger.info(
                    "DELETE FROM imp_002_disciplina"
                )

                conn.execute(
                    """
                    DELETE FROM imp_002_disciplina
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
                            INSERT INTO imp_002_disciplina
                            (
                                codigoDisciplina,
                                nomeDisciplina,
                                codigoCurso,
                                periodo,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES
                            (
                                ?,
                                ?,
                                ?,
                                ?,
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                reg["codigoDisciplina"],
                                reg["nomeDisciplina"],
                                reg["codigoCurso"],
                                reg["periodo"],
                            ),
                        )

                        total_inseridos += 1

                    except Exception as e:

                        total_erros += 1

                        logger.error(
                            "Erro ao inserir "
                            "disciplina=%s | curso=%s | periodo=%s | erro=%s",
                            reg["codigoDisciplina"],
                            reg["codigoCurso"],
                            reg["periodo"],
                            e,
                        )

                conn.commit()

        except Exception as e:

            logger.exception(
                "Erro durante reconstrução da tabela."
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
            "total_inseridos": total_inseridos,
            "total_atualizados": 0,
            "total_erros": total_erros,
            "total_processados": len(
                dados_transformados
            ),
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(self):
        """
        Executa o importador completo.
        """

        print("=" * 70)
        print(
            "IMPORTAÇÃO: imp_002_disciplina"
        )
        print("=" * 70)

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

        print(
            f"📄 Log: {LOG_FILE}"
        )

        # ---------------------------------------------------------------------
        # OBTÉM
        # ---------------------------------------------------------------------

        dados_lyceum = (
            self.obter_dados_lyceum()
        )

        logger.info(
            "📊 Combinações/turmas retornadas: %d",
            len(dados_lyceum),
        )

        print(
            f"📊 Turmas encontradas: "
            f"{len(dados_lyceum)}"
        )

        # ---------------------------------------------------------------------
        # TRANSFORMA
        # ---------------------------------------------------------------------

        dados_transformados = (
            self.transformar_dados(
                dados_lyceum
            )
        )

        logger.info(
            "✅ Registros para importação: %d",
            len(dados_transformados),
        )

        print(
            f"✅ Registros disciplina/curso: "
            f"{len(dados_transformados)}"
        )

        # ---------------------------------------------------------------------
        # IMPORTA
        # ---------------------------------------------------------------------

        resultado = (
            self.importar_para_qstione(
                dados_transformados
            )
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']} "
            f"| Erros: "
            f"{resultado['total_erros']}"
        )

        logger.info(
            "RESULTADO FINAL | "
            "Inseridos=%d | Atualizados=%d | Erros=%d | Processados=%d",
            resultado["total_inseridos"],
            resultado["total_atualizados"],
            resultado["total_erros"],
            resultado["total_processados"],
        )

        logger.info(
            "FIM imp_002_disciplina"
        )

        return dados_transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    importador = (
        ImportadorDisciplinas()
    )

    importador.executar_importacao()