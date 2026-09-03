
"""
qstione/importadores/imp_008_usuarios_disciplinas.py

Importador independente para imp_008_usuarios_disciplinas.

REGRAS
------

1. A origem dos vínculos é a turma:

       LY_TURMA_DOCENTE
              ↓
       LY_TURMA
              ↓
       LY_TURMA.curso

2. A faculdade da turma é determinada por:

       LY_TURMA.curso
              ↓
       LY_CURSO.faculdade

3. LY_DISCIPLINA.faculdade NÃO é utilizada para determinar
   a faculdade da turma.

4. São considerados:
       - ANO_VIGENTE;
       - TODOS os PERIODOS_VIGENTES;
       - SITUACAO_TURMA_VALIDA;
       - FACULDADES_INCLUIDAS.

5. Curso NULL, vazio ou 999 representa COMPARTILHADA.

6. Curso real nunca é convertido automaticamente para 999.

7. O código do curso usa MAPEAMENTO_CURSOS do imp_002.

8. O código da disciplina é gerado por:

       gerar_codigo_disciplina_curso(
           disciplina,
           nome_curso_unificado,
           curso_unificado
       )

9. Para disciplina compartilhada com sufixo -COM:

       DISC001-COM
              ↓
       DISC001
              ↓
       curso = 999
              ↓
       COMPARTILHADA

10. Usuários NDE recebem acesso às disciplinas compartilhadas
    somente quando o curso do NDE estiver relacionado à disciplina
    compartilhada.

11. A tabela é reconstruída integralmente.
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
    converter_minusculas,
    truncar_texto,
    gerar_codigo_disciplina_curso,
)

from qstione.core.validacoes import (
    validar_email,
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

LOG_DIR = os.path.join(
    ROOT,
    "logs"
)

os.makedirs(
    LOG_DIR,
    exist_ok=True
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "imp_008_usuarios_disciplinas.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(
    "imp_008_usuarios_disciplinas"
)


# ============================================================================
# CONSTANTES
# ============================================================================

CURSO_COMPARTILHADO = "999"

SUFIXO_COMPARTILHADA = "-COM"


# ============================================================================
# IMPORTADOR
# ============================================================================

class ImportadorUsuariosDisciplinas:

    def __init__(self):

        self.periodos_placeholders = ",".join(
            "?"
            for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?"
            for _ in FACULDADES_INCLUIDAS
        )

        logger.info("=" * 80)

        logger.info(
            "INÍCIO imp_008_usuarios_disciplinas"
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
            "SITUACAO_TURMA_VALIDA=%s",
            SITUACAO_TURMA_VALIDA
        )

    # ========================================================================
    # CURSO
    # ========================================================================

    @staticmethod
    def _normalizar_curso(curso):

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
                        "imp_008_usuarios_disciplinas",
                    )
                ).fetchone() is not None

        except Exception:

            logger.exception(
                "Erro ao verificar tabela."
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
                "idx_usuarios_disciplinas_email",

                """
                CREATE INDEX
                    idx_usuarios_disciplinas_email
                ON imp_008_usuarios_disciplinas
                    (emailUsuario)
                """
            ),

            (
                "idx_usuarios_disciplinas_disciplina",

                """
                CREATE INDEX
                    idx_usuarios_disciplinas_disciplina
                ON imp_008_usuarios_disciplinas
                    (codigoDisciplina)
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
                    "Não foi possível criar índice %s: %s",
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
                    CREATE TABLE
                        imp_008_usuarios_disciplinas (

                        codigoDisciplina
                            NVARCHAR(30) NOT NULL,

                        emailUsuario
                            NVARCHAR(100) NOT NULL,

                        status
                            CHAR(1) NOT NULL
                            DEFAULT 'S',

                        data_criacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao
                            DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoDisciplina,
                            emailUsuario
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
    # DOCENTES
    # ========================================================================

    def _obter_docentes_turmas(self):
        """
        Obtém docentes das turmas válidas.

        Faculdade:

            LY_TURMA.curso
                 ↓
            LY_CURSO.faculdade
        """

        query = f"""
            SELECT DISTINCT

                td.disciplina,

                t.curso,

                d.mailbox

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

              AND td.periodo IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

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

              AND (d.ativo = 'S' OR d.ativo IS NULL)

              AND d.mailbox IS NOT NULL

              AND LTRIM(RTRIM(d.mailbox)) <> ''

            ORDER BY
                td.disciplina,
                t.curso,
                d.mailbox
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

                return conn.execute(
                    query,
                    tuple(params)
                ).fetchall()

        except Exception:

            logger.exception(
                "Erro ao consultar docentes das turmas."
            )

            return []

    # ========================================================================
    # DISCIPLINAS COMPARTILHADAS
    # ========================================================================

    def _obter_disciplinas_compartilhadas(self):

        """
        Retorna:

            {
                disciplina_com: {
                    cursos_reais
                }
            }

        Uma disciplina compartilhada pode ser utilizada por
        mais de um curso.
        """

        query = f"""
            SELECT DISTINCT

                t.disciplina,

                t.curso

            FROM LY_TURMA t

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            WHERE t.ano = ?

              AND t.semestre IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

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

              AND (
                    t.disciplina LIKE '%{SUFIXO_COMPARTILHADA}'

                    OR t.curso IS NULL

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(100))
                    )) = ''

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(100))
                    )) = '999'
              )
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
                    query,
                    tuple(params)
                ).fetchall()

        except Exception:

            logger.exception(
                "Erro ao consultar disciplinas compartilhadas."
            )

            return {}

        resultado = {}

        for disciplina, curso in rows:

            if disciplina is None:
                continue

            disciplina = str(
                disciplina
            ).strip()

            if not disciplina:
                continue

            if not disciplina.endswith(
                SUFIXO_COMPARTILHADA
            ):

                continue

            curso_unificado, _ = (
                self._normalizar_curso(curso)
            )

            resultado.setdefault(
                disciplina,
                set()
            ).add(
                curso_unificado
            )

        return resultado

    # ========================================================================
    # NDE
    # ========================================================================

    def _obter_nde_por_curso(self):

        query = """
            SELECT DISTINCT

                codigoCurso,

                emailMembro

            FROM imp_nde_membros

            WHERE codigoCurso IS NOT NULL

              AND emailMembro IS NOT NULL

              AND LTRIM(RTRIM(emailMembro)) <> ''

              AND status = 'S'
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                rows = conn.execute(
                    query
                ).fetchall()

        except Exception:

            logger.exception(
                "Erro ao consultar usuários NDE."
            )

            return {}

        resultado = {}

        for curso, email in rows:

            if email is None:
                continue

            email = converter_minusculas(
                str(email).strip()
            )

            if not validar_email(email):
                continue

            curso_unificado, _ = (
                self._normalizar_curso(curso)
            )

            resultado.setdefault(
                curso_unificado,
                set()
            ).add(
                email
            )

        return resultado

    # ========================================================================
    # TRANSFORMAÇÃO
    # ========================================================================

    def transformar_dados(
        self,
        dados_lyceum
    ):
        """
        Transforma docentes em vínculos disciplina/usuário.
        """

        dados = []

        # --------------------------------------------------------------------
        # DOCENTES
        # --------------------------------------------------------------------

        for disciplina, curso, email in dados_lyceum:

            if disciplina is None:
                continue

            disciplina = str(
                disciplina
            ).strip()

            if not disciplina:
                continue

            if email is None:
                continue

            email = converter_minusculas(
                str(email).strip()
            )

            if not validar_email(email):
                continue

            curso_unificado, nome_curso = (
                self._normalizar_curso(curso)
            )

            # ---------------------------------------------------------------
            # DISCIPLINA COMPARTILHADA
            # ---------------------------------------------------------------

            if disciplina.endswith(
                SUFIXO_COMPARTILHADA
            ):

                disciplina_base = (
                    disciplina[
                        : -len(SUFIXO_COMPARTILHADA)
                    ]
                )

                curso_unificado = (
                    CURSO_COMPARTILHADO
                )

                nome_curso = (
                    "COMPARTILHADA"
                )

            else:

                disciplina_base = disciplina

            if not disciplina_base:
                continue

            codigo_disciplina = (
                gerar_codigo_disciplina_curso(
                    disciplina_base,
                    nome_curso,
                    curso_unificado,
                )
            )

            codigo_disciplina = truncar_texto(
                codigo_disciplina,
                30
            )

            dados.append(
                {
                    "codigoDisciplina":
                        codigo_disciplina,

                    "emailUsuario":
                        truncar_texto(
                            email,
                            100
                        ),
                }
            )

        # --------------------------------------------------------------------
        # DEDUPLICAÇÃO
        # --------------------------------------------------------------------

        unicos = {}

        for registro in dados:

            chave = (
                registro["codigoDisciplina"],
                registro["emailUsuario"],
            )

            unicos[chave] = registro

        resultado = list(
            unicos.values()
        )

        logger.info(
            "🔄 Docentes após deduplicação: %d",
            len(resultado)
        )

        # --------------------------------------------------------------------
        # NDE NAS DISCIPLINAS COMPARTILHADAS
        # --------------------------------------------------------------------

        disciplinas_compartilhadas = (
            self._obter_disciplinas_compartilhadas()
        )

        nde_por_curso = (
            self._obter_nde_por_curso()
        )

        for disciplina_com, cursos in (
            disciplinas_compartilhadas.items()
        ):

            disciplina_base = (
                disciplina_com[
                    : -len(SUFIXO_COMPARTILHADA)
                ]
            )

            for curso in cursos:

                usuarios = (
                    nde_por_curso.get(
                        curso,
                        set()
                    )
                )

                if not usuarios:
                    continue

                codigo_disciplina = (
                    gerar_codigo_disciplina_curso(
                        disciplina_base,
                        "COMPARTILHADA",
                        CURSO_COMPARTILHADO,
                    )
                )

                codigo_disciplina = (
                    truncar_texto(
                        codigo_disciplina,
                        30
                    )
                )

                for email in usuarios:

                    resultado.append(
                        {
                            "codigoDisciplina":
                                codigo_disciplina,

                            "emailUsuario":
                                truncar_texto(
                                    email,
                                    100
                                ),
                        }
                    )

        # --------------------------------------------------------------------
        # DEDUPLICAÇÃO FINAL
        # --------------------------------------------------------------------

        unicos = {}

        for registro in resultado:

            chave = (
                registro["codigoDisciplina"],
                registro["emailUsuario"],
            )

            unicos[chave] = registro

        resultado_final = list(
            unicos.values()
        )

        resultado_final.sort(
            key=lambda x: (
                x["codigoDisciplina"],
                x["emailUsuario"],
            )
        )

        logger.info(
            "✅ Registros finais: %d",
            len(resultado_final)
        )

        return resultado_final

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

                logger.info(
                    "🧹 Limpando tabela..."
                )

                conn.execute(
                    """
                    DELETE
                    FROM imp_008_usuarios_disciplinas
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
                                imp_008_usuarios_disciplinas
                            (
                                codigoDisciplina,
                                emailUsuario,
                                status,
                                data_criacao,
                                data_atualizacao
                            )
                            VALUES
                            (
                                ?,
                                ?,
                                'S',
                                GETDATE(),
                                GETDATE()
                            )
                            """,
                            (
                                registro[
                                    "codigoDisciplina"
                                ],

                                registro[
                                    "emailUsuario"
                                ],
                            )
                        )

                        inseridos += 1

                    except Exception as exc:

                        erros += 1

                        logger.error(
                            "Erro ao inserir %s - %s: %s",
                            registro[
                                "codigoDisciplina"
                            ],
                            registro[
                                "emailUsuario"
                            ],
                            exc
                        )

                conn.commit()

        except Exception:

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

        print("=" * 80)

        print(
            "IMPORTAÇÃO: imp_008_usuarios_disciplinas"
        )

        print("=" * 80)

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

        print("=" * 80)

        dados = (
            self._obter_docentes_turmas()
        )

        print(
            f"📊 Registros brutos: "
            f"{len(dados)}"
        )

        transformados = (
            self.transformar_dados(
                dados
            )
        )

        print(
            f"✅ Registros únicos: "
            f"{len(transformados)}"
        )

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

        print("=" * 80)

        return transformados


# ============================================================================
# EXECUÇÃO DIRETA
# ============================================================================

if __name__ == "__main__":

    ImportadorUsuariosDisciplinas().executar_importacao()
