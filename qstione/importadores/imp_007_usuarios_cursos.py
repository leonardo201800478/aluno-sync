
"""
qstione/importadores/imp_007_usuarios_cursos.py

Importador independente para imp_007_usuarios_cursos.

===============================================================================
REGRAS DE NEGÓCIO
===============================================================================

1. LY_TURMA é a fonte de verdade para determinar o curso do docente.

2. A faculdade da turma é determinada exclusivamente por:

       LY_TURMA.curso
            ↓
       LY_CURSO.curso
            ↓
       LY_CURSO.faculdade

3. LY_DISCIPLINA.faculdade NÃO é utilizada para determinar
   a faculdade da turma.

4. São considerados:

       - ANO_VIGENTE;
       - TODOS os PERIODOS_VIGENTES;
       - SITUACAO_TURMA_VALIDA;
       - FACULDADES_INCLUIDAS.

5. O código do curso segue exatamente MAPEAMENTO_CURSOS
   definido em imp_002_disciplina.py.

6. Somente docentes ativos são considerados.

7. O e-mail do docente é obtido de LY_DOCENTE.mailbox.

8. USUÁRIOS ESPECIAIS:

       camila.felicio@foa.org.br -> G

       gildo.bernardo@foa.org.br -> C

9. COORDENADORES:

       origem:
           LY_COORDENACAO

       papel:
           C

10. AVALIADORES:

       origem:
           imp_nde_membros

       papel:
           A

11. DEMAIS DOCENTES:

       origem:
           LY_TURMA_DOCENTE

       papel:
           P

12. PRIORIDADE GLOBAL DE PAPÉIS:

       G > C > A > P

    Essa prioridade vale para TODOS os cursos.

13. Se o mesmo usuário aparecer no mesmo curso com mais de um papel:

       G + C -> G
       G + A -> G
       G + P -> G

       C + A -> C
       C + P -> C

       A + P -> A

14. O papel C sempre prevalece sobre A e P,
    independentemente da origem do outro vínculo.

15. O papel A sempre prevalece sobre P,
    independentemente da origem do outro vínculo.

16. Todo usuário encontrado em um curso real também recebe
    acesso ao curso 999, preservando o papel:

       P -> P
       C -> C
       A -> A
       G -> G

17. O curso 999 NÃO recebe papel adicional para membros NDE
    apenas por serem NDE.

18. Os usuários especiais seguem a mesma regra de consolidação.

19. A tabela é reconstruída a cada execução.

20. Chave lógica:

       (codigoCurso, emailUsuario)

21. O processo é idempotente:
    executar novamente produz a mesma fotografia da origem,
    respeitando as regras acima.

===============================================================================
IMPORTANTE SOBRE A PRIORIDADE
===============================================================================

A prioridade NÃO depende da ordem em que os registros são encontrados.

Exemplo:

    primeiro:
        professor P

    depois:
        coordenador C

Resultado:

        C

Da mesma forma:

    primeiro:
        NDE A

    depois:
        professor P

Resultado:

        A

E:

    primeiro:
        professor P

    depois:
        usuário especial G

Resultado:

        G

Isso é garantido pela função _melhor_papel().

===============================================================================
CURSO 999
===============================================================================

O 999 representa o curso compartilhado.

Um usuário vinculado ao curso 056 como C terá:

       056 | usuario@exemplo.com | C
       999 | usuario@exemplo.com | C

Um usuário vinculado ao curso 056 como A terá:

       056 | usuario@exemplo.com | A
       999 | usuario@exemplo.com | A

Um professor:

       056 | usuario@exemplo.com | P
       999 | usuario@exemplo.com | P

===============================================================================
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


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
# IMPORTS DO PROJETO
# =============================================================================

from core.database import get_db_connection

from qstione.core.transformacoes import (
    converter_minusculas,
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
    SITUACAO_TURMA_VALIDA,
)

from qstione.importadores.imp_002_disciplina import (
    MAPEAMENTO_CURSOS,
)


# =============================================================================
# LOG
# =============================================================================

logger = logging.getLogger(
    "imp_007_usuarios_cursos"
)

if not logger.handlers:

    handler = logging.StreamHandler()

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(
        handler
    )

logger.setLevel(
    logging.INFO
)


# =============================================================================
# CONSTANTES
# =============================================================================

CURSO_COMPARTILHADO = "999"

PAPEL_GERAL = "G"

PAPEL_COORDENADOR = "C"

PAPEL_AVALIADOR = "A"

PAPEL_PROFESSOR = "P"


# =============================================================================
# USUÁRIOS ESPECIAIS
# =============================================================================

USUARIO_GERAL = (
    "camila.felicio@foa.org.br"
)

USUARIO_COORDENADOR = (
    "gildo.bernardo@foa.org.br"
)


# =============================================================================
# PRIORIDADE DOS PAPÉIS
# =============================================================================
#
# Quanto MENOR o número, MAIOR a prioridade.
#
# Portanto:
#
#       G = 1
#       C = 2
#       A = 3
#       P = 4
#
# Isso permite comparar os papéis independentemente da ordem
# em que os registros forem encontrados.
# =============================================================================

PRIORIDADE_PAPEIS = {

    PAPEL_GERAL: 1,

    PAPEL_COORDENADOR: 2,

    PAPEL_AVALIADOR: 3,

    PAPEL_PROFESSOR: 4,
}


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorUsuariosCursos:
    """
    Importa usuários por curso para o Qstione.

    Fontes:

        LY_TURMA_DOCENTE
        LY_COORDENACAO
        imp_nde_membros
        usuários especiais

    A consolidação final ocorre pela chave:

        (codigoCurso, emailUsuario)

    com prioridade:

        G > C > A > P
    """

    # =========================================================================
    # INIT
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

        logger.info(
            "=" * 80
        )

        logger.info(
            "Inicializando imp_007_usuarios_cursos"
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
            "Prioridade: G > C > A > P"
        )

        logger.info(
            "=" * 80
        )

    # =========================================================================
    # NORMALIZAÇÃO DE CURSO
    # =========================================================================

    @staticmethod
    def _curso_unificado(
        curso: Any
    ) -> Tuple[str, str]:
        """
        Converte um curso original para o código utilizado pelo Qstione.

        Retorno:

            (
                codigo_curso,
                nome_curso
            )

        Regras:

            NULL / vazio / 999
                -> 999 / COMPARTILHADA

            curso presente em MAPEAMENTO_CURSOS
                -> código e nome mapeados

            curso não mapeado
                -> mantém o código original
                   e utiliza o próprio código como nome

        IMPORTANTE:

        Esta função somente deve ser chamada depois que a faculdade
        e demais informações dependentes do curso original já tiverem
        sido resolvidas.
        """

        if curso is None:

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA",
            )

        curso = str(
            curso
        ).strip()

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

        mapeamento = (
            MAPEAMENTO_CURSOS.get(
                curso
            )
        )

        if mapeamento is None:

            logger.debug(
                "Curso %s não possui mapeamento. "
                "Mantendo código original.",
                curso,
            )

            return (
                curso,
                curso,
            )

        codigo, nome = mapeamento

        codigo = str(
            codigo
        ).strip()

        nome = str(
            nome
        ).strip()

        if not codigo:

            logger.warning(
                "Mapeamento inválido para curso %s. "
                "Usando curso original.",
                curso,
            )

            return (
                curso,
                curso,
            )

        return (
            codigo,
            nome or codigo,
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
                "Erro ao verificar tabela %s.",
                nome_tabela,
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
        Verifica se um índice existe no banco.
        """

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
                    ),
                ).fetchone()

            return row is not None

        except Exception:

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(
        self
    ) -> None:
        """
        Cria a tabela de destino caso ainda não exista.
        """

        tabela = (
            "imp_007_usuarios_cursos"
        )

        if not self._tabela_existe(
            tabela
        ):

            logger.info(
                "🆕 Criando tabela %s...",
                tabela,
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_007_usuarios_cursos (

                        codigoCurso NVARCHAR(30)
                            NOT NULL,

                        emailUsuario NVARCHAR(100)
                            NOT NULL,

                        papelUsuario NVARCHAR(1)
                            NOT NULL,

                        data_criacao DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoCurso,
                            emailUsuario
                        )
                    )
                    """
                )

                conn.commit()

            logger.info(
                "✅ Tabela criada."
            )

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(
        self
    ) -> None:
        """
        Cria índices auxiliares.
        """

        indices = [

            (
                "idx_usuarios_cursos_email",

                """
                CREATE INDEX
                    idx_usuarios_cursos_email
                ON imp_007_usuarios_cursos(
                    emailUsuario
                )
                """,
            ),

            (
                "idx_usuarios_cursos_curso",

                """
                CREATE INDEX
                    idx_usuarios_cursos_curso
                ON imp_007_usuarios_cursos(
                    codigoCurso
                )
                """,
            ),

            (
                "idx_usuarios_cursos_papel",

                """
                CREATE INDEX
                    idx_usuarios_cursos_papel
                ON imp_007_usuarios_cursos(
                    papelUsuario
                )
                """,
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

                    conn.execute(
                        sql
                    )

                    conn.commit()

                logger.info(
                    "🆕 Índice criado: %s",
                    nome,
                )

            except Exception as exc:

                logger.warning(
                    "⚠️ Não foi possível criar "
                    "índice %s: %s",
                    nome,
                    exc,
                )

    # =========================================================================
    # COORDENADORES
    # =========================================================================

    def obter_coordenadores(
        self
    ) -> Dict[
        Tuple[str, str],
        bool,
    ]:
        """
        Obtém os coordenadores por curso.

        Retorna:

            {
                (
                    num_func,
                    curso_unificado
                ): True
            }

        A faculdade é determinada através de:

            LY_COORDENACAO.curso
                ↓
            LY_CURSO.faculdade
        """

        sql = f"""
            SELECT DISTINCT

                co.num_func,

                co.curso

            FROM LY_COORDENACAO co

            INNER JOIN LY_CURSO c

                ON c.curso = co.curso

            WHERE c.faculdade IN (
                {self.faculdades_placeholders}
            )
        """

        try:

            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                rows = conn.execute(
                    sql,
                    tuple(
                        FACULDADES_INCLUIDAS
                    ),
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro ao consultar "
                "LY_COORDENACAO."
            )

            return {}

        resultado = {}

        for (
            num_func,
            curso,
        ) in rows:

            if num_func is None:
                continue

            curso_unificado, _ = (
                self._curso_unificado(
                    curso
                )
            )

            chave = (
                str(
                    num_func
                ).strip(),

                curso_unificado,
            )

            resultado[
                chave
            ] = True

        logger.info(
            "👤 Coordenadores encontrados: %d",
            len(resultado),
        )

        return resultado

    # =========================================================================
    # DOCENTES DAS TURMAS
    # =========================================================================

    def obter_docentes_turmas(
        self
    ) -> List[
        Tuple[
            Any,
            Any,
            Any,
        ]
    ]:
        """
        Obtém docentes das turmas válidas.

        Retorna:

            num_func
            mailbox
            curso_original

        Faculdade:

            LY_TURMA.curso
                ↓
            LY_CURSO.faculdade

        Não utiliza LY_DISCIPLINA.faculdade.
        """

        sql = f"""
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

              AND td.periodo IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND c.faculdade IN (
                  {self.faculdades_placeholders}
              )

              AND (
                  d.ativo = 'S'
                  OR d.ativo IS NULL
              )

              AND d.mailbox IS NOT NULL

              AND LTRIM(RTRIM(
                  d.mailbox
              )) <> ''

            ORDER BY

                td.num_func,

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

                rows = conn.execute(
                    sql,
                    tuple(params),
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro ao consultar "
                "LY_TURMA_DOCENTE."
            )

            return []

        logger.info(
            "👨‍🏫 Vínculos docente/turma encontrados: %d",
            len(rows),
        )

        # Diagnóstico dos vínculos encontrados para o docente 6980.
        # Mantido como INFO temporariamente para confirmar no log que
        # os registros T01/8829 e T02/8806 chegaram à transformação.
        for row in rows:
            num_func, mailbox, curso = row
            if str(num_func).strip() == "6980":
                logger.info(
                    "🔎 DOCENTE 6980 encontrado: num_func=%s | mailbox=%s | curso=%s",
                    num_func,
                    mailbox,
                    curso,
                )

        return rows

    # =========================================================================
    # MEMBROS NDE
    # =========================================================================

    def obter_membros_nde(
        self
    ) -> List[
        Tuple[
            Any,
            Any,
        ]
    ]:
        """
        Obtém os avaliadores ativos do NDE.

        Origem:

            imp_nde_membros

        Retorna:

            codigoCurso
            emailMembro
        """

        sql = """
            SELECT DISTINCT

                codigoCurso,

                emailMembro

            FROM imp_nde_membros

            WHERE codigoCurso IS NOT NULL

              AND LTRIM(RTRIM(
                  CAST(
                      codigoCurso
                      AS NVARCHAR(30)
                  )
              )) <> ''

              AND emailMembro IS NOT NULL

              AND LTRIM(RTRIM(
                  emailMembro
              )) <> ''

              AND status = 'S'
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                rows = conn.execute(
                    sql
                ).fetchall()

        except Exception:

            logger.exception(
                "❌ Erro ao consultar "
                "imp_nde_membros."
            )

            return []

        logger.info(
            "👥 Avaliadores NDE encontrados: %d",
            len(rows),
        )

        return rows

    # =========================================================================
    # PAPEL
    # =========================================================================

    @staticmethod
    def _melhor_papel(
        papel_atual: Optional[str],
        novo_papel: Optional[str],
    ) -> Optional[str]:
        """
        Retorna o papel de MAIOR prioridade.

        Hierarquia:

            G > C > A > P

        A ordem de chegada dos registros não influencia o resultado.
        """

        if not papel_atual:

            return novo_papel

        if not novo_papel:

            return papel_atual

        papel_atual = str(
            papel_atual
        ).strip().upper()

        novo_papel = str(
            novo_papel
        ).strip().upper()

        prioridade_atual = (
            PRIORIDADE_PAPEIS.get(
                papel_atual,
                999,
            )
        )

        prioridade_nova = (
            PRIORIDADE_PAPEIS.get(
                novo_papel,
                999,
            )
        )

        if (
            prioridade_nova
            < prioridade_atual
        ):

            return novo_papel

        return papel_atual

    # =========================================================================
    # ADICIONA REGISTRO
    # =========================================================================

    def _adicionar_registro(
        self,
        registros: Dict[
            Tuple[str, str],
            Dict[str, str],
        ],
        curso: Any,
        email: Any,
        papel: str,
        origem: str,
    ) -> None:
        """
        Adiciona ou consolida um vínculo.

        Chave:

            (codigoCurso, emailUsuario)

        A prioridade é aplicada independentemente da origem.
        """

        # ---------------------------------------------------------------------
        # E-MAIL
        # ---------------------------------------------------------------------

        if email is None:
            return

        email = converter_minusculas(
            str(
                email
            ).strip()
        )

        if not email:
            return

        if not validar_email(
            email
        ):

            logger.warning(
                "⚠️ E-mail inválido ignorado: %s",
                email,
            )

            return

        # ---------------------------------------------------------------------
        # CURSO
        # ---------------------------------------------------------------------

        curso_unificado, _ = (
            self._curso_unificado(
                curso
            )
        )

        curso_unificado = str(
            curso_unificado
        ).strip()

        if not curso_unificado:

            return

        if not validar_codigo_curso(
            curso_unificado
        ):

            logger.warning(
                "⚠️ Código de curso inválido "
                "ignorado: %s | email=%s",
                curso_unificado,
                email,
            )

            return

        # ---------------------------------------------------------------------
        # PAPEL
        # ---------------------------------------------------------------------

        # O papel já foi determinado pela origem do registro antes de chegar
        # aqui. Não chamar determinar_papel_usuario() neste ponto:
        # essa função exige num_func, curso e coordenadores_dict.
        papel = str(
            papel
        ).strip().upper()

        if not validar_papel_usuario(
            papel
        ):

            logger.warning(
                "⚠️ Papel inválido ignorado: "
                "%s | curso=%s | email=%s",
                papel,
                curso_unificado,
                email,
            )

            return

        # ---------------------------------------------------------------------
        # CHAVE
        # ---------------------------------------------------------------------

        chave = (
            curso_unificado,
            email,
        )

        existente = registros.get(
            chave
        )

        # ---------------------------------------------------------------------
        # PRIMEIRO REGISTRO
        # ---------------------------------------------------------------------

        if existente is None:

            registros[
                chave
            ] = {

                "codigoCurso":
                    curso_unificado,

                "emailUsuario":
                    email,

                "papelUsuario":
                    papel,
            }

            logger.debug(
                "➕ %s | %s | %s | origem=%s",
                curso_unificado,
                email,
                papel,
                origem,
            )

            return

        # ---------------------------------------------------------------------
        # CONSOLIDAÇÃO
        # ---------------------------------------------------------------------

        papel_anterior = (
            existente[
                "papelUsuario"
            ]
        )

        melhor_papel = (
            self._melhor_papel(
                papel_anterior,
                papel,
            )
        )

        if melhor_papel != papel_anterior:

            logger.debug(
                "⬆️ Alterando papel: "
                "%s | %s | %s -> %s | origem=%s",
                curso_unificado,
                email,
                papel_anterior,
                melhor_papel,
                origem,
            )

            existente[
                "papelUsuario"
            ] = melhor_papel

    # =========================================================================
    # ADICIONA CURSO 999
    # =========================================================================

    def _adicionar_curso_compartilhado(
        self,
        registros: Dict[
            Tuple[str, str],
            Dict[str, str],
        ],
        email: Any,
        papel: str,
        origem: str,
    ) -> None:
        """
        Adiciona o usuário ao curso 999 preservando seu papel.

        Exemplo:

            curso 056 / C
                ↓
            curso 999 / C
        """

        self._adicionar_registro(
            registros=registros,
            curso=CURSO_COMPARTILHADO,
            email=email,
            papel=papel,
            origem=origem,
        )

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        docentes_turmas,
        coordenadores,
        membros_nde,
    ) -> List[
        Dict[str, str]
    ]:
        """
        Consolida todos os usuários.

        Ordem de processamento:

            1. professores/coordenadores das turmas;
            2. NDE;
            3. usuários especiais.

        A ordem NÃO altera a prioridade final porque
        _melhor_papel() utiliza explicitamente:

            G > C > A > P
        """

        registros: Dict[
            Tuple[str, str],
            Dict[str, str],
        ] = {}

        # =========================================================================
        # 1. DOCENTES DAS TURMAS
        # =========================================================================

        for (
            num_func,
            email,
            curso_original,
        ) in docentes_turmas:

            if num_func is None:
                continue

            if email is None:
                continue

            curso_unificado, _ = (
                self._curso_unificado(
                    curso_original
                )
            )

            chave_coordenador = (
                str(
                    num_func
                ).strip(),

                curso_unificado,
            )

            if (
                chave_coordenador
                in coordenadores
            ):

                papel = (
                    PAPEL_COORDENADOR
                )

                origem = (
                    "LY_COORDENACAO"
                )

            else:

                papel = (
                    PAPEL_PROFESSOR
                )

                origem = (
                    "LY_TURMA_DOCENTE"
                )

            # -----------------------------------------------------------------
            # CURSO PRINCIPAL
            # -----------------------------------------------------------------

            self._adicionar_registro(
                registros=registros,
                curso=curso_original,
                email=email,
                papel=papel,
                origem=origem,
            )

            # -----------------------------------------------------------------
            # CURSO 999
            # -----------------------------------------------------------------

            self._adicionar_curso_compartilhado(
                registros=registros,
                email=email,
                papel=papel,
                origem=(
                    f"{origem}:999"
                ),
            )

        # =========================================================================
        # 2. AVALIADORES NDE
        # =========================================================================

        for (
            curso,
            email,
        ) in membros_nde:

            self._adicionar_registro(
                registros=registros,
                curso=curso,
                email=email,
                papel=PAPEL_AVALIADOR,
                origem="NDE",
            )

            # -----------------------------------------------------------------
            # IMPORTANTE:
            #
            # NDE NÃO recebe automaticamente 999.
            # -----------------------------------------------------------------

        # =========================================================================
        # 3. USUÁRIO G - CAMILA
        # =========================================================================
        #
        # A usuária G deve prevalecer em qualquer curso em que já exista
        # um vínculo para ela.
        #
        # Para garantir o caráter global do papel G, primeiro identificamos
        # todos os cursos que já possuem Camila e elevamos para G.
        #
        # Se não houver nenhum curso para ela, ela receberá ao menos
        # o curso 999 como acesso global.
        # =========================================================================

        email_camila = converter_minusculas(
            USUARIO_GERAL
        )

        cursos_camila = [
            chave[0]
            for chave in registros
            if chave[1]
            == email_camila
        ]

        if cursos_camila:

            for curso in cursos_camila:

                self._adicionar_registro(
                    registros=registros,
                    curso=curso,
                    email=email_camila,
                    papel=PAPEL_GERAL,
                    origem="USUARIO_ESPECIAL_G",
                )

        else:

            self._adicionar_registro(
                registros=registros,
                curso=CURSO_COMPARTILHADO,
                email=email_camila,
                papel=PAPEL_GERAL,
                origem="USUARIO_ESPECIAL_G",
            )

        # =========================================================================
        # 4. USUÁRIO C - GILDO
        # =========================================================================
        #
        # Gildo recebe C em qualquer curso onde já possua vínculo.
        #
        # Se não existir nenhum vínculo, recebe ao menos o curso 999.
        # =========================================================================

        email_gildo = converter_minusculas(
            USUARIO_COORDENADOR
        )

        cursos_gildo = [
            chave[0]
            for chave in registros
            if chave[1]
            == email_gildo
        ]

        if cursos_gildo:

            for curso in cursos_gildo:

                self._adicionar_registro(
                    registros=registros,
                    curso=curso,
                    email=email_gildo,
                    papel=PAPEL_COORDENADOR,
                    origem="USUARIO_ESPECIAL_C",
                )

        else:

            self._adicionar_registro(
                registros=registros,
                curso=CURSO_COMPARTILHADO,
                email=email_gildo,
                papel=PAPEL_COORDENADOR,
                origem="USUARIO_ESPECIAL_C",
            )

        # =========================================================================
        # RESULTADO
        # =========================================================================

        resultado = list(
            registros.values()
        )

        # ---------------------------------------------------------------------
        # ORDENAÇÃO SOMENTE PARA SAÍDA.
        #
        # Não participa da regra de prioridade.
        # ---------------------------------------------------------------------

        resultado.sort(
            key=lambda registro: (
                registro[
                    "codigoCurso"
                ],

                registro[
                    "emailUsuario"
                ],
            )
        )

        # =========================================================================
        # ESTATÍSTICAS
        # =========================================================================

        quantidade_g = sum(
            1
            for registro in resultado
            if registro[
                "papelUsuario"
            ] == PAPEL_GERAL
        )

        quantidade_c = sum(
            1
            for registro in resultado
            if registro[
                "papelUsuario"
            ] == PAPEL_COORDENADOR
        )

        quantidade_a = sum(
            1
            for registro in resultado
            if registro[
                "papelUsuario"
            ] == PAPEL_AVALIADOR
        )

        quantidade_p = sum(
            1
            for registro in resultado
            if registro[
                "papelUsuario"
            ] == PAPEL_PROFESSOR
        )

        logger.info(
            "=" * 80
        )

        logger.info(
            "📊 RESULTADO DA CONSOLIDAÇÃO"
        )

        logger.info(
            "   G = %d",
            quantidade_g,
        )

        logger.info(
            "   C = %d",
            quantidade_c,
        )

        logger.info(
            "   A = %d",
            quantidade_a,
        )

        logger.info(
            "   P = %d",
            quantidade_p,
        )

        logger.info(
            "   TOTAL = %d",
            len(resultado),
        )

        logger.info(
            "=" * 80
        )

        return resultado

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ) -> Dict[str, int]:
        """
        Reconstrói a tabela destino.

        Não utiliza UPDATE porque a tabela é uma fotografia
        completa das regras de negócio no momento da execução.

        Fluxo:

            DELETE
              ↓
            INSERT
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                # -------------------------------------------------------------
                # LIMPA A TABELA
                # -------------------------------------------------------------

                logger.info(
                    "🧹 Limpando tabela %s...",
                    "imp_007_usuarios_cursos",
                )

                conn.execute(
                    """
                    DELETE
                    FROM imp_007_usuarios_cursos
                    """
                )

                cursor = conn.cursor()

                # -------------------------------------------------------------
                # INSERT
                # -------------------------------------------------------------

                for registro in (
                    dados_transformados
                ):

                    try:

                        cursor.execute(
                            """
                            INSERT INTO
                                imp_007_usuarios_cursos
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
                                registro[
                                    "codigoCurso"
                                ],

                                registro[
                                    "emailUsuario"
                                ],

                                registro[
                                    "papelUsuario"
                                ],
                            ),
                        )

                        inseridos += 1

                    except Exception as exc:

                        erros += 1

                        logger.error(
                            "❌ Erro ao inserir: "
                            "curso=%s | email=%s | papel=%s | erro=%s",
                            registro[
                                "codigoCurso"
                            ],
                            registro[
                                "emailUsuario"
                            ],
                            registro[
                                "papelUsuario"
                            ],
                            exc,
                        )

                # -------------------------------------------------------------
                # COMMIT
                # -------------------------------------------------------------

                conn.commit()

        except Exception:

            logger.exception(
                "❌ Erro durante a reconstrução "
                "da tabela imp_007_usuarios_cursos."
            )

            return {

                "total_inseridos":
                    0,

                "total_atualizados":
                    0,

                "total_erros":
                    len(
                        dados_transformados
                    ),

                "total_processados":
                    len(
                        dados_transformados
                    ),
            }

        logger.info(
            "✅ Importação concluída."
        )

        logger.info(
            "   Inseridos: %d",
            inseridos,
        )

        logger.info(
            "   Erros: %d",
            erros,
        )

        return {

            "total_inseridos":
                inseridos,

            "total_atualizados":
                0,

            "total_erros":
                erros,

            "total_processados":
                len(
                    dados_transformados
                ),
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(
        self
    ) -> List[
        Dict[str, str]
    ]:
        """
        Executa o processo completo.
        """

        logger.info(
            "=" * 100
        )

        logger.info(
            "🚀 INÍCIO DA IMPORTAÇÃO "
            "imp_007_usuarios_cursos"
        )

        logger.info(
            "=" * 100
        )

        # =====================================================================
        # 1. COORDENADORES
        # =====================================================================

        coordenadores = (
            self.obter_coordenadores()
        )

        # =====================================================================
        # 2. DOCENTES
        # =====================================================================

        docentes_turmas = (
            self.obter_docentes_turmas()
        )

        # =====================================================================
        # 3. NDE
        # =====================================================================

        membros_nde = (
            self.obter_membros_nde()
        )

        # =====================================================================
        # 4. TRANSFORMAÇÃO
        # =====================================================================

        dados_transformados = (
            self.transformar_dados(
                docentes_turmas=
                    docentes_turmas,

                coordenadores=
                    coordenadores,

                membros_nde=
                    membros_nde,
            )
        )

        # =====================================================================
        # 5. IMPORTAÇÃO
        # =====================================================================

        resultado = (
            self.importar_para_qstione(
                dados_transformados
            )
        )

        # =====================================================================
        # 6. RESUMO
        # =====================================================================

        logger.info(
            "=" * 100
        )

        logger.info(
            "📋 RESUMO FINAL"
        )

        logger.info(
            "   Docentes/turmas : %d",
            len(
                docentes_turmas
            ),
        )

        logger.info(
            "   Coordenadores   : %d",
            len(
                coordenadores
            ),
        )

        logger.info(
            "   NDE             : %d",
            len(
                membros_nde
            ),
        )

        logger.info(
            "   Processados     : %d",
            resultado[
                "total_processados"
            ],
        )

        logger.info(
            "   Inseridos       : %d",
            resultado[
                "total_inseridos"
            ],
        )

        logger.info(
            "   Erros           : %d",
            resultado[
                "total_erros"
            ],
        )

        logger.info(
            "=" * 100
        )

        return dados_transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    try:

        importador = (
            ImportadorUsuariosCursos()
        )

        importador.executar_importacao()

    except Exception:

        logger.exception(
            "❌ Falha fatal na execução "
            "do imp_007_usuarios_cursos."
        )

        raise
