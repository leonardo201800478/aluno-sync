"""
qstione/importadores/imp_008_usuarios_disciplinas.py

Importador independente para imp_008_usuarios_disciplinas.

REGRAS DE NEGÓCIO
-----------------

1. A origem da disciplina/oferta é a TURMA REAL:
       LY_TURMA_DOCENTE
              ↓
       LY_TURMA
              ↓
       ano + semestre + turma + disciplina
              ↓
       LY_TURMA.curso

2. O curso NUNCA é obtido diretamente de LY_GRADE para determinar
   a disciplina da turma.

3. O curso da turma é validado através de:
       LY_TURMA.curso
              ↓
       LY_CURSO.faculdade
              ↓
       FACULDADES_INCLUIDAS

4. Turmas sem curso:
       LY_TURMA.curso IS NULL
              ↓
       curso = 999
              ↓
       COMPARTILHADA

5. O código da disciplina é gerado exatamente pela mesma regra
   utilizada em imp_002_disciplina.py:

       gerar_codigo_disciplina_curso(
           disciplina,
           nome_curso_unificado,
           curso_unificado
       )

6. O MAPEAMENTO_CURSOS é importado diretamente do imp_002_disciplina.py.

7. Docentes:
       LY_TURMA_DOCENTE.num_func
              ↓
       LY_DOCENTE.num_func
              ↓
       LY_DOCENTE.mailbox

8. NDE:
   O NDE é associado ao curso efetivamente encontrado na turma.
   Não é utilizada LY_GRADE para descobrir cursos da disciplina.

9. Cada execução:
       DELETE FROM imp_008_usuarios_disciplinas
       INSERT dos dados novos

   Portanto a tabela é reconstruída integralmente.

10. O arquivo pode ser executado diretamente pelo botão Play do VS Code.
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

LOG_DIR = os.path.join(ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    "imp_008_usuarios_disciplinas.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("imp_008_usuarios_disciplinas")


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorUsuariosDisciplinas:
    """
    Importa usuários associados às disciplinas reais das turmas.

    A disciplina é identificada pela combinação:

        disciplina + curso da turma

    utilizando exatamente a mesma regra do imp_002_disciplina.py.
    """

    def __init__(self):
        self.periodos_placeholders = ",".join(
            "?" for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?" for _ in FACULDADES_INCLUIDAS
        )

        logger.info("=" * 80)
        logger.info("INÍCIO imp_008_usuarios_disciplinas")
        logger.info("ANO_VIGENTE=%s", ANO_VIGENTE)
        logger.info("PERIODOS_VIGENTES=%s", PERIODOS_VIGENTES)
        logger.info("FACULDADES_INCLUIDAS=%s", FACULDADES_INCLUIDAS)
        logger.info(
            "SITUACAO_TURMA_VALIDA=%s",
            SITUACAO_TURMA_VALIDA
        )
        logger.info("LOG_FILE=%s", LOG_FILE)

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(self) -> bool:
        """
        Verifica se a tabela imp_008_usuarios_disciplinas existe.

        Returns
        -------
        bool
            True se a tabela existir, False caso contrário.
        """

        try:
            with get_db_connection(database_name="qstione") as conn:

                return conn.execute(
                    """
                    SELECT 1
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ?
                      AND TABLE_TYPE = 'BASE TABLE'
                    """,
                    ("imp_008_usuarios_disciplinas",)
                ).fetchone() is not None

        except Exception:
            logger.exception(
                "Erro ao verificar existência da tabela."
            )
            return False

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _indice_existe(self, nome_indice: str) -> bool:
        """
        Verifica se um índice existe.

        Parameters
        ----------
        nome_indice:
            Nome do índice.

        Returns
        -------
        bool
            True se existir.
        """

        try:
            with get_db_connection(database_name="qstione") as conn:

                return conn.execute(
                    """
                    SELECT 1
                    FROM sys.indexes
                    WHERE name = ?
                    """,
                    (nome_indice,)
                ).fetchone() is not None

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

        Também garante os índices utilizados nas consultas posteriores.
        """

        if not self._tabela_existe():

            logger.info(
                "Criando tabela imp_008_usuarios_disciplinas..."
            )

            with get_db_connection(database_name="qstione") as conn:

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
                "Tabela imp_008_usuarios_disciplinas criada."
            )

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):
        """
        Cria os índices auxiliares da tabela destino.
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

            if self._indice_existe(nome_indice):
                continue

            try:

                with get_db_connection(database_name="qstione") as conn:

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
        Aplica exatamente o MAPEAMENTO_CURSOS do imp_002.

        Parameters
        ----------
        curso:
            Código original do curso vindo de LY_TURMA.curso.

        Returns
        -------
        tuple[str, str]
            Código unificado e nome do curso unificado.

        Regras
        ------
        NULL/vazio:
            999 / COMPARTILHADA

        Curso conhecido:
            utiliza MAPEAMENTO_CURSOS.

        Curso não mapeado:
            mantém código original.
        """

        if curso is None:
            return "999", "COMPARTILHADA"

        curso = str(curso).strip()

        if not curso:
            return "999", "COMPARTILHADA"

        if curso in MAPEAMENTO_CURSOS:

            curso_unificado, nome_curso = (
                MAPEAMENTO_CURSOS[curso]
            )

            return (
                str(curso_unificado),
                str(nome_curso)
            )

        return curso, curso

    # =========================================================================
    # NDE
    # =========================================================================

    def _obter_emails_nde_por_curso(self):
        """
        Obtém os e-mails dos integrantes do NDE agrupados pelo curso.

        O código do curso utilizado aqui deve ser compatível com o
        código unificado utilizado pelo imp_002.

        Returns
        -------
        dict
            Estrutura:

                {
                    "031": {
                        "email1@...",
                        "email2@..."
                    }
                }
        """

        emails = {}

        try:

            with get_db_connection(database_name="qstione") as conn:

                # -------------------------------------------------------------
                # Coordenador NDE
                # -------------------------------------------------------------

                rows = conn.execute(
                    """
                    SELECT
                        codigoCurso,
                        emailCoordenador
                    FROM imp_nde_cursos
                    WHERE emailCoordenador IS NOT NULL
                      AND LTRIM(RTRIM(emailCoordenador)) <> ''
                      AND status = 'S'
                    """
                ).fetchall()

                for curso, email in rows:

                    curso_unificado, _ = (
                        self._normalizar_curso(curso)
                    )

                    email = converter_minusculas(
                        str(email).strip()
                    )

                    emails.setdefault(
                        curso_unificado,
                        set()
                    ).add(email)

                # -------------------------------------------------------------
                # Membros NDE
                # -------------------------------------------------------------

                rows = conn.execute(
                    """
                    SELECT
                        codigoCurso,
                        emailMembro
                    FROM imp_nde_membros
                    WHERE emailMembro IS NOT NULL
                      AND LTRIM(RTRIM(emailMembro)) <> ''
                      AND status = 'S'
                    """
                ).fetchall()

                for curso, email in rows:

                    curso_unificado, _ = (
                        self._normalizar_curso(curso)
                    )

                    email = converter_minusculas(
                        str(email).strip()
                    )

                    emails.setdefault(
                        curso_unificado,
                        set()
                    ).add(email)

        except Exception:

            logger.exception(
                "Erro ao buscar e-mails NDE."
            )

        logger.info(
            "Cursos com usuários NDE encontrados: %d",
            len(emails)
        )

        return emails

    # =========================================================================
    # CONSULTA PRINCIPAL
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém as disciplinas a partir das TURMAS reais.

        A relação principal é:

            LY_TURMA_DOCENTE
                ↓
            LY_TURMA
                ↓
            LY_CURSO
                ↓
            LY_DOCENTE

        A turma é validada pela chave completa:

            ano
            semestre
            turma
            disciplina

        O curso é SEMPRE LY_TURMA.curso.

        Uma turma sem curso recebe 999/COMPARTILHADA.

        Returns
        -------
        list
            Tuplas:

                (
                    disciplina,
                    curso,
                    email
                )
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
            "Consultando disciplinas/docentes através das turmas..."
        )

        with get_db_connection() as conn:

            rows = conn.execute(
                query,
                params
            ).fetchall()

        logger.info(
            "Combinações disciplina/curso/docente encontradas: %d",
            len(rows)
        )

        # ---------------------------------------------------------------------
        # NDE
        # ---------------------------------------------------------------------

        nde_por_curso = (
            self._obter_emails_nde_por_curso()
        )

        resultados = set()

        # ---------------------------------------------------------------------
        # DOCENTES
        # ---------------------------------------------------------------------

        for disciplina, curso, email in rows:

            if not disciplina:
                continue

            if not email:
                continue

            email = converter_minusculas(
                str(email).strip()
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
                    disciplina,
                    curso,
                    email
                )
            )

        # ---------------------------------------------------------------------
        # NDE
        #
        # IMPORTANTE:
        # O NDE é associado ao CURSO REAL DA TURMA.
        #
        # Para isso primeiro descobrimos quais combinações
        # disciplina/curso existem nas turmas elegíveis.
        # ---------------------------------------------------------------------

        combinacoes_disciplina_curso = {
            (
                disciplina,
                self._normalizar_curso(curso)[0]
            )

            for disciplina, curso, _ in rows

            if disciplina
        }

        for disciplina, curso_unificado in (
            combinacoes_disciplina_curso
        ):

            for email in nde_por_curso.get(
                curso_unificado,
                set()
            ):

                if not email:
                    continue

                email = converter_minusculas(
                    str(email).strip()
                )

                if not validar_email(email):
                    continue

                resultados.add(
                    (
                        disciplina,
                        curso_unificado,
                        email
                    )
                )

        logger.info(
            "Resultado final disciplina/curso/e-mail: %d",
            len(resultados)
        )

        return list(resultados)

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(self, dados_lyceum):
        """
        Gera o código final da disciplina utilizando a mesma regra do imp_002.

        Para cada registro:

            disciplina
            +
            curso real da turma
            ↓
            curso unificado
            ↓
            nome curso unificado
            ↓
            gerar_codigo_disciplina_curso()

        Returns
        -------
        list
            Registros prontos para inserção.
        """

        dados = []

        for disciplina, curso, email in dados_lyceum:

            if not disciplina:
                continue

            if not validar_email(email):
                continue

            # -----------------------------------------------------------------
            # CURSO
            # -----------------------------------------------------------------

            curso_unificado, nome_curso_unificado = (
                self._normalizar_curso(curso)
            )

            # -----------------------------------------------------------------
            # DISCIPLINA
            # -----------------------------------------------------------------

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

            email_final = truncar_texto(
                converter_minusculas(
                    str(email).strip()
                ),
                100
            )

            dados.append(
                {
                    "codigoDisciplina": codigo_disciplina,
                    "emailUsuario": email_final,
                }
            )

        # ---------------------------------------------------------------------
        # DEDUPLICAÇÃO
        # ---------------------------------------------------------------------

        unicos = {}

        for registro in dados:

            chave = (
                registro["codigoDisciplina"],
                registro["emailUsuario"],
            )

            unicos[chave] = registro

        dados_finais = list(
            unicos.values()
        )

        logger.info(
            "Registros após transformação/deduplicação: %d",
            len(dados_finais)
        )

        return dados_finais

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(self, dados_transformados):
        """
        Reconstrói integralmente a tabela destino.

        Primeiro:

            DELETE FROM imp_008_usuarios_disciplinas

        Depois insere somente os dados da execução atual.
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
                    "Limpando imp_008_usuarios_disciplinas..."
                )

                conn.execute(
                    """
                    DELETE FROM imp_008_usuarios_disciplinas
                    """
                )

                # -------------------------------------------------------------
                # INSERT
                # -------------------------------------------------------------

                cursor = conn.cursor()

                for registro in dados_transformados:

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
                                registro["codigoDisciplina"],
                                registro["emailUsuario"],
                            )
                        )

                        inseridos += 1

                    except Exception as e:

                        erros += 1

                        logger.error(
                            "Erro ao importar %s - %s: %s",
                            registro["codigoDisciplina"],
                            registro["emailUsuario"],
                            e
                        )

                conn.commit()

        except Exception as e:

            logger.exception(
                "Erro durante reconstrução da tabela."
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": len(dados_transformados),
                "total_processados": len(dados_transformados),
            }

        return {
            "total_inseridos": inseridos,
            "total_atualizados": 0,
            "total_erros": erros,
            "total_processados": len(dados_transformados),
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(self):
        """
        Executa o processo completo de importação.

        Pode ser executado diretamente pelo botão Play do VS Code.
        """

        print("=" * 70)
        print("IMPORTAÇÃO: imp_008_usuarios_disciplinas")
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
            f"📚 Situação da turma: {SITUACAO_TURMA_VALIDA}"
        )

        print(
            f"📄 Log: {LOG_FILE}"
        )

        # ---------------------------------------------------------------------
        # OBTÉM
        # ---------------------------------------------------------------------

        dados = self.obter_dados_lyceum()

        print(
            f"📊 Registros encontrados: {len(dados)}"
        )

        # ---------------------------------------------------------------------
        # TRANSFORMA
        # ---------------------------------------------------------------------

        transformados = self.transformar_dados(
            dados
        )

        print(
            f"✅ Registros únicos: {len(transformados)}"
        )

        # ---------------------------------------------------------------------
        # IMPORTA
        # ---------------------------------------------------------------------

        resultado = self.importar_para_qstione(
            transformados
        )

        print(
            f"📈 Inseridos: "
            f"{resultado['total_inseridos']} "
            f"| Erros: "
            f"{resultado['total_erros']}"
        )

        logger.info(
            "RESULTADO FINAL | Inseridos=%d | Erros=%d",
            resultado["total_inseridos"],
            resultado["total_erros"]
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