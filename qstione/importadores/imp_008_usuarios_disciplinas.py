"""
qstione/importadores/imp_008_usuarios_disciplinas.py

Importador independente para imp_008_usuarios_disciplinas.

REGRAS DE NEGÓCIO
-----------------

1. DOCENTES NORMAIS

   A origem da disciplina/oferta é a TURMA REAL:

       LY_TURMA_DOCENTE
              ↓
       LY_TURMA
              ↓
       LY_DOCENTE
              ↓
       disciplina + curso + e-mail


2. CURSO

   O curso utiliza exatamente o MAPEAMENTO_CURSOS do
   imp_002_disciplina.py.

   Exemplo:

       056 -> 056
       141 -> 056

       065 -> 065
       036 -> 065
       037 -> 065


3. TURMAS COMPARTILHADAS

   Uma turma somente será considerada compartilhada quando
   o campo LY_TURMA.curso original for:

       NULL
       vazio
       999

   Nesses casos:

       curso = 999
       nome_curso = COMPARTILHADA

   IMPORTANTE:

   Uma disciplina que possua um curso real NÃO será transformada
   em curso 999 somente porque seu código possui '-COM'.


4. DISCIPLINAS COMPARTILHADAS

   Uma disciplina compartilhada também pode ser identificada
   através de LY_MATRICULA.

   Para o ano/período configurado em:

       ANO_VIGENTE
       PERIODOS_VIGENTES

   são identificadas as combinações:

       turma + disciplina

   que possuem mais de uma ocorrência.

   Para essas disciplinas é criada a identificação:

       disciplina + '-COM'

   Exemplo:

       MAT001
       ↓
       MAT001-COM


5. CURSOS DE UMA DISCIPLINA COMPARTILHADA

   Depois de identificar somente as disciplinas compartilhadas,
   consulta-se LY_MATRICULA + LY_ALUNO para descobrir em quais
   cursos os alunos daquela disciplina estão matriculados.

   O MAPEAMENTO_CURSOS é aplicado nesse momento.

   Exemplo:

       disciplina: MAT001-COM

       cursos encontrados:
           056
           141

       MAPEAMENTO_CURSOS:
           056 -> 056
           141 -> 056

       resultado:

           MAT001-COM -> curso 056


6. NDE

   Os usuários são obtidos de:

       imp_nde_cursos
       imp_nde_membros

   O curso informado nas tabelas do NDE também passa pelo
   MAPEAMENTO_CURSOS.


7. NDE + DISCIPLINA COMPARTILHADA

   O usuário NDE somente recebe acesso à disciplina compartilhada
   quando o curso unificado do usuário estiver entre os cursos
   identificados para aquela disciplina.

   Exemplo:

       MAT001-COM -> curso 056

       NDE:
           professor1 -> 056
           professor2 -> 031

       Resultado:

           professor1 -> MAT001 compartilhada

       professor2 NÃO recebe acesso.


8. CURSO 999

   O curso 999 representa exclusivamente:

       - turmas cujo curso é NULL;
       - turmas cujo curso é vazio;
       - turmas cujo curso é 999;
       - disciplinas compartilhadas geradas pela regra de
         compartilhamento via LY_MATRICULA.

   Não é permitido converter uma turma com curso real
   diretamente para 999.


9. GERAÇÃO DO CÓDIGO DA DISCIPLINA

   O '-COM' é utilizado apenas para identificar a disciplina
   compartilhada durante o processamento.

   Antes de chamar:

       gerar_codigo_disciplina_curso()

   o '-COM' é removido.

   Exemplo:

       MAT001-COM
           ↓
       MAT001
           ↓
       gerar_codigo_disciplina_curso(
           'MAT001',
           'COMPARTILHADA',
           '999'
       )


10. EXECUÇÃO

    A tabela destino é reconstruída a cada execução:

        DELETE FROM imp_008_usuarios_disciplinas

    O arquivo pode ser executado diretamente pelo botão Play
    do VS Code.
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
    converter_minusculas,
    truncar_texto,
    gerar_codigo_disciplina_curso,
)

from qstione.core.validacoes import validar_email

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
# LOG
# =============================================================================

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


# =============================================================================
# CONSTANTES
# =============================================================================

CURSO_COMPARTILHADO = "999"

SUFIXO_COMPARTILHADA = "-COM"


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorUsuariosDisciplinas:
    """
    Importa os usuários que possuem acesso às disciplinas.

    Existem dois fluxos principais:

    1. Docentes das turmas reais.
    2. Usuários NDE, incluindo o acesso controlado às disciplinas
       compartilhadas.

    O curso 999 não representa acesso global.
    """

    def __init__(self):
        """
        Inicializa o importador e prepara os placeholders utilizados
        nas consultas SQL.
        """

        self.periodos_placeholders = ",".join(
            "?" for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?" for _ in FACULDADES_INCLUIDAS
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

        logger.info(
            "LOG_FILE=%s",
            LOG_FILE
        )

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(self) -> bool:
        """
        Verifica se a tabela destino existe.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                resultado = conn.execute(
                    """
                    SELECT 1
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ?
                      AND TABLE_TYPE = 'BASE TABLE'
                    """,
                    (
                        "imp_008_usuarios_disciplinas",
                    )
                ).fetchone()

                return resultado is not None

        except Exception:

            logger.exception(
                "Erro ao verificar existência da tabela."
            )

            return False

    # =========================================================================
    # ÍNDICE
    # =========================================================================

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

                resultado = conn.execute(
                    """
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = ?
                    """,
                    (
                        nome_indice,
                    )
                ).fetchone()

                return resultado is not None

        except Exception:

            logger.exception(
                "Erro ao verificar índice %s.",
                nome_indice
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela destino caso ela ainda não exista.
        """

        if not self._tabela_existe():

            logger.info(
                "Criando tabela imp_008_usuarios_disciplinas..."
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_008_usuarios_disciplinas (
                        codigoDisciplina NVARCHAR(30) NOT NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        status CHAR(1) NOT NULL DEFAULT 'S',
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoDisciplina,
                            emailUsuario
                        )
                    )
                    """
                )

                conn.commit()

            logger.info(
                "🆕 Tabela criada com sucesso."
            )

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):
        """
        Cria os índices auxiliares caso ainda não existam.
        """

        indices = [

            (
                "idx_usuarios_disciplinas_email",

                """
                CREATE INDEX idx_usuarios_disciplinas_email
                ON imp_008_usuarios_disciplinas(emailUsuario)
                """
            ),

            (
                "idx_usuarios_disciplinas_codigo",

                """
                CREATE INDEX idx_usuarios_disciplinas_codigo
                ON imp_008_usuarios_disciplinas(codigoDisciplina)
                """
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
                    nome_indice
                )

            except Exception:

                logger.exception(
                    "Erro ao criar índice %s.",
                    nome_indice
                )

    # =========================================================================
    # NORMALIZAÇÃO DO CURSO
    # =========================================================================

    @staticmethod
    def _normalizar_curso(curso):
        """
        Normaliza o código original do curso.

        SOMENTE estes valores representam curso compartilhado:

            NULL
            vazio
            999

        Cursos reais passam pelo MAPEAMENTO_CURSOS.

        Returns
        -------
        tuple[str, str]
            Código unificado e nome do curso.
        """

        # ---------------------------------------------------------------------
        # NULL
        # ---------------------------------------------------------------------

        if curso is None:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        # ---------------------------------------------------------------------
        # STRING NORMALIZADA
        # ---------------------------------------------------------------------

        curso = str(
            curso
        ).strip()

        # ---------------------------------------------------------------------
        # VAZIO
        # ---------------------------------------------------------------------

        if not curso:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        # ---------------------------------------------------------------------
        # 999
        # ---------------------------------------------------------------------

        if curso == CURSO_COMPARTILHADO:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA"
            )

        # ---------------------------------------------------------------------
        # MAPEAMENTO DE CURSOS REAIS
        # ---------------------------------------------------------------------

        if curso in MAPEAMENTO_CURSOS:

            curso_unificado, nome_curso = (
                MAPEAMENTO_CURSOS[
                    curso
                ]
            )

            return (
                str(
                    curso_unificado
                ).strip(),

                str(
                    nome_curso
                ).strip()
            )

        # ---------------------------------------------------------------------
        # CURSO NÃO MAPEADO
        # ---------------------------------------------------------------------

        return (
            curso,
            curso
        )

    # =========================================================================
    # DISCIPLINAS COMPARTILHADAS
    # =========================================================================

    def _obter_disciplinas_compartilhadas(self):
        """
        Identifica exclusivamente disciplinas compartilhadas.

        Uma disciplina somente poderá receber o sufixo '-COM' quando
        a TURMA correspondente possuir curso:

            NULL
            vazio
            999

        A existência de múltiplos alunos em LY_MATRICULA, sozinha,
        NÃO é suficiente para transformar uma disciplina em compartilhada.

        A relação utilizada é:

            LY_MATRICULA
                ↓
            LY_TURMA
                ↓
            LY_ALUNO

        A combinação turma + disciplina somente será considerada
        compartilhada quando a LY_TURMA correspondente não possuir
        um curso real.

        Retorna:
            {
                'DISCIPLINA-COM': {'curso1', 'curso2', ...}
            }
        """

        logger.info(
            "🔎 Identificando disciplinas compartilhadas..."
        )

        query = f"""
            WITH duplicadas AS (

                SELECT
                    m.turma,
                    m.disciplina

                FROM LY_MATRICULA m

                INNER JOIN LY_TURMA t
                    ON t.ano = m.ano
                AND t.semestre = m.semestre
                AND t.turma = m.turma
                AND t.disciplina = m.disciplina

                WHERE m.ano = ?

                AND m.semestre IN (
                    {self.periodos_placeholders}
                )

                AND m.disciplina IS NOT NULL

                AND LTRIM(RTRIM(
                    CAST(m.disciplina AS NVARCHAR(100))
                )) <> ''

                -- =========================================================
                -- SOMENTE TURMAS SEM CURSO REAL
                -- =========================================================

                AND (
                        t.curso IS NULL

                        OR LTRIM(RTRIM(
                            CAST(t.curso AS NVARCHAR(30))
                        )) = ''

                        OR LTRIM(RTRIM(
                            CAST(t.curso AS NVARCHAR(30))
                        )) = '999'
                )

                GROUP BY
                    m.turma,
                    m.disciplina

                HAVING COUNT(*) > 1
            )

            SELECT DISTINCT

                m.disciplina + '-COM' AS disciplina_com,

                a.curso

            FROM LY_MATRICULA m

            INNER JOIN LY_TURMA t
                ON t.ano = m.ano
            AND t.semestre = m.semestre
            AND t.turma = m.turma
            AND t.disciplina = m.disciplina

            INNER JOIN LY_ALUNO a
                ON m.aluno = a.aluno

            WHERE m.ano = ?

            AND m.semestre IN (
                {self.periodos_placeholders}
            )

            -- =============================================================
            -- GARANTE NOVAMENTE QUE A TURMA NÃO POSSUI CURSO REAL
            -- =============================================================

            AND (
                    t.curso IS NULL

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(30))
                    )) = ''

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(30))
                    )) = '999'
            )

            AND EXISTS (

                SELECT 1

                FROM duplicadas d

                WHERE d.turma = m.turma
                    AND d.disciplina = m.disciplina
            )

            AND m.disciplina IS NOT NULL

            AND LTRIM(RTRIM(
                CAST(m.disciplina AS NVARCHAR(100))
            )) <> ''

            AND a.curso IS NOT NULL

            AND LTRIM(RTRIM(
                CAST(a.curso AS NVARCHAR(30))
            )) <> ''

            ORDER BY
                disciplina_com
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,

            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
        )

        try:

            with get_db_connection() as conn:

                rows = conn.execute(
                    query,
                    params
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro ao consultar disciplinas compartilhadas."
            )

            return {}

        disciplinas_por_curso = {}

        for disciplina_com, curso_original in rows:

            if not disciplina_com:
                continue

            if curso_original is None:
                continue

            disciplina_com = str(
                disciplina_com
            ).strip()

            curso_original = str(
                curso_original
            ).strip()

            if not curso_original:
                continue

            # =============================================================
            # NORMALIZA CURSO DO ALUNO
            # =============================================================

            curso_unificado, _ = (
                self._normalizar_curso(
                    curso_original
                )
            )

            # =============================================================
            # 999 NÃO É CURSO ACADÊMICO DE ORIGEM
            #
            # O 999 aqui é o destino da disciplina compartilhada.
            # Os cursos que determinam quem recebe acesso são os cursos
            # reais dos alunos.
            # =============================================================

            if curso_unificado == CURSO_COMPARTILHADO:
                continue

            disciplinas_por_curso.setdefault(
                disciplina_com,
                set()
            ).add(
                curso_unificado
            )

        logger.info(
            "📚 Disciplinas compartilhadas encontradas: %d",
            len(disciplinas_por_curso)
        )

        total_relacoes = sum(
            len(cursos)
            for cursos in disciplinas_por_curso.values()
        )

        logger.info(
            "🔗 Relações disciplina compartilhada/curso: %d",
            total_relacoes
        )

        for disciplina_com, cursos in sorted(
            disciplinas_por_curso.items()
        ):

            logger.info(
                "   %s -> cursos %s",
                disciplina_com,
                sorted(cursos)
            )

        return disciplinas_por_curso

    # =========================================================================
    # NDE POR CURSO
    # =========================================================================

    def _obter_emails_nde_por_curso(self):
        """
        Obtém usuários NDE agrupados pelo curso unificado.
        """

        nde_por_curso = {}

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                # =============================================================
                # COORDENADORES NDE
                # =============================================================

                rows = conn.execute(
                    """
                    SELECT
                        codigoCurso,
                        emailCoordenador

                    FROM imp_nde_cursos

                    WHERE codigoCurso IS NOT NULL
                      AND emailCoordenador IS NOT NULL
                      AND LTRIM(RTRIM(emailCoordenador)) <> ''
                      AND status = 'S'
                    """
                ).fetchall()

                for curso, email in rows:

                    curso_unificado, _ = (
                        self._normalizar_curso(
                            curso
                        )
                    )

                    email = converter_minusculas(
                        str(
                            email
                        ).strip()
                    )

                    if not validar_email(
                        email
                    ):
                        continue

                    nde_por_curso.setdefault(
                        curso_unificado,
                        set()
                    ).add(
                        email
                    )

                # =============================================================
                # MEMBROS NDE
                # =============================================================

                rows = conn.execute(
                    """
                    SELECT
                        codigoCurso,
                        emailMembro

                    FROM imp_nde_membros

                    WHERE codigoCurso IS NOT NULL
                      AND emailMembro IS NOT NULL
                      AND LTRIM(RTRIM(emailMembro)) <> ''
                      AND status = 'S'
                    """
                ).fetchall()

                for curso, email in rows:

                    curso_unificado, _ = (
                        self._normalizar_curso(
                            curso
                        )
                    )

                    email = converter_minusculas(
                        str(
                            email
                        ).strip()
                    )

                    if not validar_email(
                        email
                    ):
                        continue

                    nde_por_curso.setdefault(
                        curso_unificado,
                        set()
                    ).add(
                        email
                    )

        except Exception:

            logger.exception(
                "Erro ao consultar usuários NDE."
            )

            return {}

        total_usuarios = sum(
            len(usuarios)
            for usuarios in nde_por_curso.values()
        )

        logger.info(
            "👥 Cursos com usuários NDE: %d",
            len(nde_por_curso)
        )

        logger.info(
            "👥 Relações NDE/curso: %d",
            total_usuarios
        )

        return nde_por_curso

    # =========================================================================
    # NDE -> DISCIPLINAS COMPARTILHADAS
    # =========================================================================

    def _gerar_acessos_nde_compartilhados(
        self,
        disciplinas_compartilhadas,
        nde_por_curso
    ):
        """
        Relaciona usuários NDE às disciplinas compartilhadas.

        O vínculo somente ocorre quando o curso do NDE estiver
        associado à disciplina compartilhada.
        """

        resultados = set()

        for disciplina_com, cursos_origem in (
            disciplinas_compartilhadas.items()
        ):

            for curso in cursos_origem:

                usuarios = nde_por_curso.get(
                    curso,
                    set()
                )

                if not usuarios:
                    continue

                logger.info(
                    "🔗 %s -> curso %s -> %d usuários NDE",
                    disciplina_com,
                    curso,
                    len(usuarios)
                )

                for email in usuarios:

                    resultados.add(
                        (
                            disciplina_com,
                            CURSO_COMPARTILHADO,
                            email
                        )
                    )

        logger.info(
            "🌐 Vínculos NDE/disciplina compartilhada: %d",
            len(resultados)
        )

        return resultados

    # =========================================================================
    # DOCENTES DAS TURMAS
    # =========================================================================

    def _obter_docentes_turmas(self):
        """
        Obtém os docentes vinculados às turmas do período vigente.

        IMPORTANTE:

        O curso original da LY_TURMA é preservado.

        Assim conseguimos distinguir:

            NULL -> compartilhada
            vazio -> compartilhada
            999 -> compartilhada
            curso real -> curso real
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
                        CAST(t.curso AS NVARCHAR(30))
                    )) = ''

                    OR LTRIM(RTRIM(
                        CAST(t.curso AS NVARCHAR(30))
                    )) = '999'

                    OR c.faculdade IN (
                        {self.faculdades_placeholders}
                    )
                  )

              AND d.mailbox IS NOT NULL

              AND LTRIM(RTRIM(d.mailbox)) <> ''
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        )

        logger.info(
            "👨‍🏫 Consultando docentes das turmas..."
        )

        try:

            with get_db_connection() as conn:

                rows = conn.execute(
                    query,
                    params
                ).fetchall()

        except Exception:

            logger.exception(
                "Erro ao consultar docentes das turmas."
            )

            return []

        logger.info(
            "👨‍🏫 Vínculos docente/disciplina encontrados: %d",
            len(rows)
        )

        return rows

    # =========================================================================
    # CONSULTA PRINCIPAL
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Monta todos os vínculos de usuários com disciplinas.
        """

        resultados = set()

        # =====================================================================
        # 1. DOCENTES DAS TURMAS
        # =====================================================================

        dados_docentes = (
            self._obter_docentes_turmas()
        )

        for disciplina, curso, email in (
            dados_docentes
        ):

            if not disciplina:
                continue

            if not email:
                continue

            email = converter_minusculas(
                str(
                    email
                ).strip()
            )

            if not validar_email(email):

                logger.warning(
                    "E-mail inválido para disciplina %s: %s",
                    disciplina,
                    email
                )

                continue

            resultados.add(
                (
                    str(
                        disciplina
                    ).strip(),

                    curso,

                    email
                )
            )

        logger.info(
            "👨‍🏫 Registros docentes adicionados: %d",
            len(resultados)
        )

        # =====================================================================
        # 2. DISCIPLINA/CURSO DOS DOCENTES
        # =====================================================================

        combinacoes_disciplina_curso = set()

        for disciplina, curso, _ in (
            dados_docentes
        ):

            if not disciplina:
                continue

            curso_unificado, _ = (
                self._normalizar_curso(
                    curso
                )
            )

            combinacoes_disciplina_curso.add(
                (
                    str(
                        disciplina
                    ).strip(),

                    curso_unificado
                )
            )

        logger.info(
            "📚 Combinações disciplina/curso dos docentes: %d",
            len(combinacoes_disciplina_curso)
        )

        # =====================================================================
        # 3. NDE POR CURSO
        # =====================================================================

        nde_por_curso = (
            self._obter_emails_nde_por_curso()
        )

        # =====================================================================
        # 4. NDE NAS DISCIPLINAS NORMAIS
        # =====================================================================

        nde_registros = 0

        for disciplina, curso_unificado in (
            combinacoes_disciplina_curso
        ):

            if curso_unificado == CURSO_COMPARTILHADO:
                continue

            usuarios = nde_por_curso.get(
                curso_unificado,
                set()
            )

            for email in usuarios:

                resultados.add(
                    (
                        disciplina,
                        curso_unificado,
                        email
                    )
                )

                nde_registros += 1

        logger.info(
            "👥 Vínculos NDE em disciplinas próprias: %d",
            nde_registros
        )

        # =====================================================================
        # 5. DISCIPLINAS COMPARTILHADAS
        # =====================================================================

        disciplinas_compartilhadas = (
            self._obter_disciplinas_compartilhadas()
        )

        # =====================================================================
        # 6. NDE -> DISCIPLINAS COMPARTILHADAS
        # =====================================================================

        acessos_nde_compartilhados = (
            self._gerar_acessos_nde_compartilhados(
                disciplinas_compartilhadas,
                nde_por_curso
            )
        )

        # =====================================================================
        # 7. ADICIONA VÍNCULOS COMPARTILHADOS
        # =====================================================================

        for disciplina_com, curso, email in (
            acessos_nde_compartilhados
        ):

            resultados.add(
                (
                    disciplina_com,
                    curso,
                    email
                )
            )

        logger.info(
            "🌐 Vínculos compartilhados adicionados: %d",
            len(acessos_nde_compartilhados)
        )

        # =====================================================================
        # RESULTADO FINAL
        # =====================================================================

        logger.info(
            "📊 Resultado bruto final: %d",
            len(resultados)
        )

        return list(
            resultados
        )

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum
    ):
        """
        Converte os dados para o formato da tabela destino.

        REGRA FUNDAMENTAL:

        O curso somente será convertido para 999 quando o curso
        ORIGINAL da turma for:

            NULL
            vazio
            999

        Uma disciplina com curso real permanece no curso real
        após o MAPEAMENTO_CURSOS.
        """

        dados = []

        for disciplina, curso, email in (
            dados_lyceum
        ):

            if not disciplina:
                continue

            if not validar_email(
                email
            ):
                continue

            disciplina = str(
                disciplina
            ).strip()

            # =================================================================
            # PRESERVA O CURSO ORIGINAL
            # =================================================================

            curso_original = curso

            curso_original_str = (
                str(
                    curso_original
                ).strip()
                if curso_original is not None
                else ""
            )

            # =================================================================
            # DEFINE SE A TURMA É REALMENTE COMPARTILHADA
            # =================================================================

            curso_eh_compartilhado = (
                curso_original is None
                or curso_original_str == ""
                or curso_original_str == CURSO_COMPARTILHADO
            )

            # =================================================================
            # NORMALIZA CURSO
            # =================================================================

            curso_unificado, nome_curso_unificado = (
                self._normalizar_curso(
                    curso_original
                )
            )

            # =================================================================
            # DISCIPLINA COM SUFIXO -COM
            # =================================================================

            possui_sufixo_com = (
                disciplina.endswith(
                    SUFIXO_COMPARTILHADA
                )
            )

            # =================================================================
            # SOMENTE É COMPARTILHADA QUANDO:
            #
            #   1. possui -COM
            #   2. curso original é NULL/vazio/999
            #
            # =================================================================

            eh_compartilhada = (
                possui_sufixo_com
                and curso_eh_compartilhado
            )

            if eh_compartilhada:

                disciplina_base = disciplina[
                    :-len(
                        SUFIXO_COMPARTILHADA
                    )
                ].strip()

                curso_unificado = (
                    CURSO_COMPARTILHADO
                )

                nome_curso_unificado = (
                    "COMPARTILHADA"
                )

            else:

                # -------------------------------------------------------------
                # DISCIPLINA NORMAL
                #
                # Mesmo que termine em -COM, se a turma possuir um
                # curso real ela permanece nesse curso.
                # -------------------------------------------------------------

                disciplina_base = disciplina

            # =================================================================
            # VALIDAÇÃO
            # =================================================================

            if not disciplina_base:
                continue

            # =================================================================
            # GERA CÓDIGO DA DISCIPLINA
            # =================================================================

            codigo_disciplina = (
                gerar_codigo_disciplina_curso(
                    disciplina_base,
                    nome_curso_unificado,
                    curso_unificado
                )
            )

            codigo_disciplina = truncar_texto(
                codigo_disciplina,
                30
            )

            # =================================================================
            # E-MAIL
            # =================================================================

            email_final = converter_minusculas(
                str(
                    email
                ).strip()
            )

            email_final = truncar_texto(
                email_final,
                100
            )

            dados.append(
                {
                    "codigoDisciplina": codigo_disciplina,
                    "emailUsuario": email_final,
                }
            )

        # =====================================================================
        # DEDUPLICAÇÃO
        # =====================================================================

        unicos = {}

        for registro in dados:

            chave = (
                registro[
                    "codigoDisciplina"
                ],

                registro[
                    "emailUsuario"
                ],
            )

            unicos[chave] = registro

        dados_finais = list(
            unicos.values()
        )

        logger.info(
            "🔄 Registros após transformação/deduplicação: %d",
            len(dados_finais)
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
        Reconstrói a tabela imp_008_usuarios_disciplinas.
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                logger.info(
                    "🧹 Limpando imp_008_usuarios_disciplinas..."
                )

                conn.execute(
                    """
                    DELETE FROM imp_008_usuarios_disciplinas
                    """
                )

                cursor = conn.cursor()

                for registro in (
                    dados_transformados
                ):

                    try:

                        cursor.execute(
                            """
                            INSERT INTO imp_008_usuarios_disciplinas
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

                    except Exception as e:

                        erros += 1

                        logger.error(
                            "❌ Erro ao inserir "
                            "%s - %s: %s",

                            registro[
                                "codigoDisciplina"
                            ],

                            registro[
                                "emailUsuario"
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
        """
        Executa todo o processo de importação.

        Pode ser executado diretamente pelo botão Play do VS Code.
        """

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

        # =====================================================================
        # CONSULTA
        # =====================================================================

        dados = (
            self.obter_dados_lyceum()
        )

        print(
            f"📊 Registros brutos: "
            f"{len(dados)}"
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
            f"✅ Registros únicos: "
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

        print("=" * 80)

        logger.info(
            "RESULTADO FINAL | "
            "Processados=%d | "
            "Inseridos=%d | "
            "Erros=%d",

            resultado[
                "total_processados"
            ],

            resultado[
                "total_inseridos"
            ],

            resultado[
                "total_erros"
            ]
        )

        logger.info(
            "FIM imp_008_usuarios_disciplinas"
        )

        return transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    importador = (
        ImportadorUsuariosDisciplinas()
    )

    importador.executar_importacao()