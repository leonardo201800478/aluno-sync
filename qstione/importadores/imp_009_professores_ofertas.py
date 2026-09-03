
"""
qstione/importadores/imp_009_professores_ofertas.py

Importador independente para imp_009_professores_ofertas.

===============================================================================
OBJETIVO
===============================================================================

Relaciona cada oferta do Qstione aos professores efetivamente vinculados
à turma no Lyceum.

===============================================================================
FONTE DOS DADOS
===============================================================================

Oferta:
    LY_TURMA

Professor da turma:
    LY_TURMA_DOCENTE

Dados do professor:
    LY_DOCENTE

E-mail:
    LY_DOCENTE.mailbox

Faculdade:
    LY_TURMA.curso
        ↓
    LY_CURSO.faculdade

IMPORTANTE:
    NÃO utiliza LY_DISCIPLINA.faculdade para determinar a faculdade.

===============================================================================
IDENTIFICAÇÃO DA OFERTA
===============================================================================

O codigoOferta é gerado EXATAMENTE com a mesma função do imp_005:

    gerar_codigo_oferta(
        disciplina,
        turma,
        ano,
        semestre
    )

===============================================================================
REGRAS
===============================================================================

1. Ano:
       ANO_VIGENTE

2. Período:
       todos os PERIODOS_VIGENTES

3. Situação:
       SITUACAO_TURMA_VALIDA

4. Faculdade:
       LY_TURMA.curso -> LY_CURSO.faculdade

5. Curso NULL ou vazio:
       é considerado compartilhado (999)

6. Professor:
       precisa existir em LY_TURMA_DOCENTE.

7. E-mail:
       sempre LY_DOCENTE.mailbox.

8. mailbox NULL ou vazio:
       professor não é exportado.

9. codigoOferta:
       exatamente igual ao imp_005.

10. Chave:
       (codigoOferta, emailProfessor)

11. A tabela destino é reconstruída a cada execução.

12. A reconstrução é transacional:
       DELETE + INSERT + COMMIT

       Se houver falha:
       ROLLBACK.

13. Não existe filtro por matrícula.

14. Não existe dependência de LY_DISCIPLINA.faculdade.
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
    gerar_codigo_oferta,
    converter_minusculas,
    truncar_texto,
)

from qstione.core.validacoes import (
    validar_email,
    validar_codigo_disciplina,
)

from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    AREAS_CONHECIMENTO_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)

from qstione.importadores.imp_002_disciplina import (
    MAPEAMENTO_CURSOS,
)


# =============================================================================
# LOGGING
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
    "imp_009_professores_ofertas.log",
)

logger = logging.getLogger(
    "imp_009_professores_ofertas"
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
        "%(asctime)s | %(levelname)s | %(message)s"
    )
)

logger.addHandler(
    file_handler
)

logger.propagate = False


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorProfessoresOfertas:
    """
    Importa professores vinculados às ofertas.

    A relação professor -> oferta é determinada exclusivamente
    por LY_TURMA_DOCENTE.
    """

    NOME_TABELA = (
        "imp_009_professores_ofertas"
    )

    # =========================================================================
    # INICIALIZAÇÃO
    # =========================================================================

    def __init__(self):

        if not PERIODOS_VIGENTES:

            raise ValueError(
                "PERIODOS_VIGENTES não pode estar vazio."
            )

        if not FACULDADES_INCLUIDAS:

            raise ValueError(
                "FACULDADES_INCLUIDAS não pode estar vazio."
            )

        self.periodos_placeholders = ",".join(
            "?"
            for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?"
            for _ in FACULDADES_INCLUIDAS
        )

        self.areas = [
            area
            for area in AREAS_CONHECIMENTO_INCLUIDAS
            if area not in (
                None,
                "",
            )
        ]

        self.areas_placeholders = ",".join(
            "?"
            for _ in self.areas
        )

        logger.info(
            "=" * 90
        )

        logger.info(
            "INÍCIO imp_009_professores_ofertas"
        )

        logger.info(
            "ANO_VIGENTE=%s",
            ANO_VIGENTE,
        )

        logger.info(
            "PERIODOS_VIGENTES=%s",
            PERIODOS_VIGENTES,
        )

        logger.info(
            "FACULDADES_INCLUIDAS=%s",
            FACULDADES_INCLUIDAS,
        )

        logger.info(
            "SITUACAO_TURMA_VALIDA=%s",
            SITUACAO_TURMA_VALIDA,
        )

        logger.info(
            "LOG=%s",
            LOG_FILE,
        )

    # =========================================================================
    # TABELA EXISTE
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela,
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
                    ),
                ).fetchone()

                return row is not None

        except Exception:

            logger.exception(
                "Erro verificando tabela %s.",
                nome_tabela,
            )

            return False

    # =========================================================================
    # ÍNDICE EXISTE
    # =========================================================================

    def _indice_existe(
        self,
        nome_indice,
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
                      AND object_id =
                          OBJECT_ID(?)
                    """,
                    (
                        nome_indice,
                        self.NOME_TABELA,
                    ),
                ).fetchone()

                return row is not None

        except Exception:

            logger.exception(
                "Erro verificando índice %s.",
                nome_indice,
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):

        if self._tabela_existe(
            self.NOME_TABELA
        ):

            return True

        logger.info(
            "Criando tabela %s...",
            self.NOME_TABELA,
        )

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    f"""
                    CREATE TABLE {self.NOME_TABELA}
                    (
                        codigoOferta
                            NVARCHAR(30) NOT NULL,

                        emailProfessor
                            NVARCHAR(100) NOT NULL,

                        data_criacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY
                        (
                            codigoOferta,
                            emailProfessor
                        )
                    )
                    """
                )

                conn.commit()

            print(
                "🆕 Tabela imp_009_professores_ofertas criada."
            )

            logger.info(
                "Tabela %s criada.",
                self.NOME_TABELA,
            )

        except Exception:

            logger.exception(
                "Erro criando tabela %s.",
                self.NOME_TABELA,
            )

            return False

        self._criar_indices()

        return True

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):

        indices = [

            (
                "idx_professores_ofertas_email",

                f"""
                CREATE INDEX
                    idx_professores_ofertas_email
                ON {self.NOME_TABELA}
                (
                    emailProfessor
                )
                """,
            ),

            (
                "idx_professores_ofertas_codigo",

                f"""
                CREATE INDEX
                    idx_professores_ofertas_codigo
                ON {self.NOME_TABELA}
                (
                    codigoOferta
                )
                """,
            ),
        ]

        for (
            nome_indice,
            sql,
        ) in indices:

            if self._indice_existe(
                nome_indice
            ):

                continue

            try:

                with get_db_connection(
                    database_name="qstione"
                ) as conn:

                    conn.execute(
                        sql
                    )

                    conn.commit()

                logger.info(
                    "Índice criado: %s",
                    nome_indice,
                )

            except Exception as e:

                logger.warning(
                    "Não foi possível criar índice %s: %s",
                    nome_indice,
                    e,
                )

    # =========================================================================
    # CURSO UNIFICADO
    # =========================================================================

    @staticmethod
    def _curso_unificado(
        curso,
    ):
        """
        Aplica o mesmo MAPEAMENTO_CURSOS do imp_002.

        NULL/vazio:
            999

        Mapeado:
            código unificado

        Não mapeado:
            mantém original
        """

        if curso is None:

            return "999"

        curso = str(
            curso
        ).strip()

        if not curso:

            return "999"

        if curso == "999":

            return "999"

        if curso in MAPEAMENTO_CURSOS:

            return str(
                MAPEAMENTO_CURSOS[
                    curso
                ][0]
            ).strip()

        return curso

    # =========================================================================
    # OBTENÇÃO DOS DADOS
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém os vínculos professor -> turma.

        A faculdade é determinada por:

            LY_TURMA.curso
                ↓
            LY_CURSO.faculdade

        O e-mail é determinado por:

            LY_TURMA_DOCENTE.num_func
                ↓
            LY_DOCENTE.num_func
                ↓
            LY_DOCENTE.mailbox
        """

        # ---------------------------------------------------------------------
        # ÁREAS
        # ---------------------------------------------------------------------

        filtro_area = ""

        if self.areas:

            filtro_area = f"""
                AND (
                    dsc.area_conhecimento IN (
                        {self.areas_placeholders}
                    )

                    OR dsc.area_conhecimento IS NULL

                    OR dsc.area_conhecimento = ''
                )
            """

        else:

            filtro_area = """
                AND (
                    dsc.area_conhecimento IS NULL
                    OR dsc.area_conhecimento = ''
                )
            """

        # ---------------------------------------------------------------------
        # CONSULTA
        # ---------------------------------------------------------------------

        query = f"""
            SELECT DISTINCT

                t.disciplina,

                t.turma,

                t.ano,

                t.semestre,

                doc.[mailbox] AS mailbox,

                t.curso

            FROM LY_TURMA t

            INNER JOIN LY_DISCIPLINA dsc
                ON dsc.disciplina = t.disciplina

            INNER JOIN LY_TURMA_DOCENTE td
                ON td.disciplina = t.disciplina

               AND td.turma = t.turma

               AND td.ano = t.ano

               AND td.periodo = t.semestre

            INNER JOIN LY_DOCENTE doc
                ON doc.num_func = td.num_func

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            WHERE t.ano = ?

              AND t.semestre IN (
                    {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND (
                    t.curso IS NULL

                    OR LTRIM(
                        RTRIM(
                            CAST(
                                t.curso
                                AS NVARCHAR(30)
                            )
                        )
                    ) = ''

                    OR LTRIM(
                        RTRIM(
                            CAST(
                                t.curso
                                AS NVARCHAR(30)
                            )
                        )
                    ) = '999'

                    OR c.faculdade IN (
                        {self.faculdades_placeholders}
                    )
                  )

              {filtro_area}

              AND (doc.ativo = 'S' OR doc.ativo IS NULL)

              AND doc.[mailbox] IS NOT NULL

              AND LTRIM(
                    RTRIM(
                        CAST(
                            doc.[mailbox]
                            AS NVARCHAR(255)
                        )
                    )
                  ) <> ''

            ORDER BY

                t.disciplina,

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
            "Consultando LY_TURMA + "
            "LY_TURMA_DOCENTE + LY_DOCENTE..."
        )

        logger.info(
            "Faculdade determinada por "
            "LY_CURSO.faculdade."
        )

        logger.info(
            "E-mail determinado por "
            "LY_DOCENTE.mailbox."
        )

        try:

            with get_db_connection() as conn:

                rows = conn.execute(
                    query,
                    params,
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro ao consultar LYCEUM."
            )

            raise

        logger.info(
            "Registros encontrados na consulta: %d",
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
        Gera os vínculos:

            codigoOferta
            emailProfessor

        A chave é:

            codigoOferta + emailProfessor
        """

        resultado = []

        descartados_disciplina = 0
        descartados_email = 0
        descartados_oferta = 0

        for (
            disciplina,
            turma,
            ano,
            semestre,
            email,
            curso,
        ) in dados_lyceum:

            # -----------------------------------------------------------------
            # DISCIPLINA
            # -----------------------------------------------------------------

            if not validar_codigo_disciplina(
                disciplina
            ):

                descartados_disciplina += 1

                logger.warning(
                    "Disciplina inválida: %s | turma=%s",
                    disciplina,
                    turma,
                )

                continue

            # -----------------------------------------------------------------
            # E-MAIL
            # -----------------------------------------------------------------

            if not validar_email(
                email
            ):

                descartados_email += 1

                logger.warning(
                    "E-mail inválido: %s | "
                    "disciplina=%s | turma=%s",
                    email,
                    disciplina,
                    turma,
                )

                continue

            # -----------------------------------------------------------------
            # CURSO
            # -----------------------------------------------------------------

            curso_unificado = (
                self._curso_unificado(
                    curso
                )
            )

            # -----------------------------------------------------------------
            # CÓDIGO DA OFERTA
            # -----------------------------------------------------------------

            codigo_oferta = (
                gerar_codigo_oferta(
                    disciplina,
                    turma,
                    ano,
                    semestre,
                )
            )

            codigo_oferta = (
                truncar_texto(
                    codigo_oferta,
                    30,
                )
            )

            if not codigo_oferta:

                descartados_oferta += 1

                logger.warning(
                    "Código de oferta vazio: "
                    "disciplina=%s | turma=%s | "
                    "ano=%s | semestre=%s",
                    disciplina,
                    turma,
                    ano,
                    semestre,
                )

                continue

            # -----------------------------------------------------------------
            # E-MAIL FINAL
            # -----------------------------------------------------------------

            email_final = (
                converter_minusculas(
                    str(email).strip()
                )
            )

            email_final = (
                truncar_texto(
                    email_final,
                    100,
                )
            )

            # -----------------------------------------------------------------
            # REGISTRO
            # -----------------------------------------------------------------

            resultado.append(
                {
                    "codigoOferta":
                        codigo_oferta,

                    "emailProfessor":
                        email_final,

                    "codigoCurso":
                        truncar_texto(
                            curso_unificado,
                            30,
                        ),
                }
            )

        # ---------------------------------------------------------------------
        # DEDUPLICAÇÃO
        # ---------------------------------------------------------------------

        unicos = {}

        duplicados = 0

        for registro in resultado:

            chave = (
                registro[
                    "codigoOferta"
                ],
                registro[
                    "emailProfessor"
                ],
            )

            if chave in unicos:

                duplicados += 1

                continue

            unicos[
                chave
            ] = registro

        dados_finais = list(
            unicos.values()
        )

        # ---------------------------------------------------------------------
        # LOG
        # ---------------------------------------------------------------------

        logger.info(
            "Transformação concluída."
        )

        logger.info(
            "Registros recebidos: %d",
            len(dados_lyceum),
        )

        logger.info(
            "Registros transformados: %d",
            len(resultado),
        )

        logger.info(
            "Duplicidades removidas: %d",
            duplicados,
        )

        logger.info(
            "Disciplinas inválidas: %d",
            descartados_disciplina,
        )

        logger.info(
            "E-mails inválidos: %d",
            descartados_email,
        )

        logger.info(
            "Ofertas inválidas: %d",
            descartados_oferta,
        )

        logger.info(
            "Registros finais: %d",
            len(dados_finais),
        )

        return dados_finais

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ):
        """
        Reconstrói integralmente a tabela.

        A operação é atômica:

            DELETE
              ↓
            INSERTS
              ↓
            COMMIT

        Qualquer erro:

            ROLLBACK
        """

        if not self._criar_tabela():

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 1,
                "total_processados":
                    len(dados_transformados),
                "rollback": False,
            }

        # ---------------------------------------------------------------------
        # PROTEÇÃO CONTRA CARGA VAZIA
        # ---------------------------------------------------------------------

        if not dados_transformados:

            logger.warning(
                "Nenhum registro válido foi encontrado."
            )

            logger.warning(
                "A tabela não será limpa."
            )

            print(
                "⚠️ Nenhum registro válido encontrado."
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 0,
                "total_processados": 0,
                "rollback": False,
            }

        inseridos = 0

        total_processados = len(
            dados_transformados
        )

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                cursor = conn.cursor()

                try:

                    # ---------------------------------------------------------
                    # DELETE
                    # ---------------------------------------------------------

                    logger.info(
                        "Limpando %s...",
                        self.NOME_TABELA,
                    )

                    cursor.execute(
                        f"""
                        DELETE FROM
                            {self.NOME_TABELA}
                        """
                    )

                    # ---------------------------------------------------------
                    # INSERT
                    # ---------------------------------------------------------

                    for indice, registro in enumerate(
                        dados_transformados,
                        start=1,
                    ):

                        cursor.execute(
                            f"""
                            INSERT INTO
                                {self.NOME_TABELA}
                            (
                                codigoOferta,
                                emailProfessor,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES
                            (
                                ?,
                                ?,
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                registro[
                                    "codigoOferta"
                                ],

                                registro[
                                    "emailProfessor"
                                ],
                            ),
                        )

                        inseridos += 1

                        if (
                            indice % 1000 == 0
                            or indice == total_processados
                        ):

                            logger.info(
                                "Inseridos %d/%d",
                                indice,
                                total_processados,
                            )

                    # ---------------------------------------------------------
                    # COMMIT
                    # ---------------------------------------------------------

                    conn.commit()

                    logger.info(
                        "COMMIT realizado com sucesso."
                    )

                except Exception:

                    # ---------------------------------------------------------
                    # ROLLBACK
                    # ---------------------------------------------------------

                    try:

                        conn.rollback()

                        logger.error(
                            "ROLLBACK realizado."
                        )

                    except Exception:

                        logger.exception(
                            "Falha ao executar ROLLBACK."
                        )

                    raise

        except Exception as e:

            logger.exception(
                "❌ Erro durante reconstrução da tabela."
            )

            print(
                f"❌ Erro durante reconstrução: {e}"
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 1,
                "total_processados":
                    total_processados,
                "rollback": True,
            }

        return {
            "total_inseridos": inseridos,
            "total_atualizados": 0,
            "total_erros": 0,
            "total_processados":
                total_processados,
            "rollback": False,
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(self):

        print(
            "=" * 80
        )

        print(
            "IMPORTAÇÃO: imp_009_professores_ofertas"
        )

        print(
            "=" * 80
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
            "👨‍🏫 Professor: LY_TURMA_DOCENTE"
        )

        print(
            "📧 E-mail: LY_DOCENTE.mailbox"
        )

        print(
            "🏫 Faculdade: LY_CURSO.faculdade"
        )

        print(
            f"📄 Log: {LOG_FILE}"
        )

        print(
            "=" * 80
        )

        # =====================================================================
        # 1. CONSULTA
        # =====================================================================

        try:

            dados = (
                self.obter_dados_lyceum()
            )

        except Exception as e:

            print(
                f"❌ Erro ao consultar LYCEUM: {e}"
            )

            return []

        print(
            f"📊 Registros encontrados: "
            f"{len(dados)}"
        )

        # =====================================================================
        # 2. TRANSFORMAÇÃO
        # =====================================================================

        try:

            transformados = (
                self.transformar_dados(
                    dados
                )
            )

        except Exception as e:

            logger.exception(
                "Erro durante transformação."
            )

            print(
                f"❌ Erro durante transformação: {e}"
            )

            return []

        print(
            f"✅ Registros únicos: "
            f"{len(transformados)}"
        )

        # =====================================================================
        # 3. IMPORTAÇÃO
        # =====================================================================

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        # =====================================================================
        # 4. RESULTADO
        # =====================================================================

        print(
            "=" * 80
        )

        print(
            "RESULTADO"
        )

        print(
            "=" * 80
        )

        print(
            f"📊 Processados: "
            f"{resultado['total_processados']}"
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']}"
        )

        print(
            f"✗ Erros: "
            f"{resultado['total_erros']}"
        )

        if resultado.get(
            "rollback",
            False
        ):

            print(
                "↩️ ROLLBACK executado."
            )

            print(
                "❌ Importação cancelada."
            )

        else:

            print(
                "✅ Importação concluída."
            )

        print(
            "=" * 80
        )

        logger.info(
            "RESULTADO FINAL | "
            "Processados=%d | "
            "Inseridos=%d | "
            "Erros=%d | "
            "Rollback=%s",
            resultado[
                "total_processados"
            ],
            resultado[
                "total_inseridos"
            ],
            resultado[
                "total_erros"
            ],
            resultado.get(
                "rollback",
                False
            ),
        )

        logger.info(
            "FIM imp_009_professores_ofertas"
        )

        return transformados


# =============================================================================
# PLAY DO VS CODE
# =============================================================================

if __name__ == "__main__":

    ImportadorProfessoresOfertas().executar_importacao()
