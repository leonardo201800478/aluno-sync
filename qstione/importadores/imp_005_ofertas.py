
"""
qstione/importadores/imp_005_ofertas.py

Importador independente de ofertas.

REGRAS DE NEGÓCIO
-----------------

1. A turma é a fonte de verdade para a oferta.

2. O curso é SEMPRE obtido de:
       LY_TURMA.curso

3. A faculdade é obtida através de:
       LY_TURMA.curso
            ↓
       LY_CURSO.faculdade

4. Somente cursos pertencentes às FACULDADES_INCLUIDAS
   são considerados.

5. Turmas sem curso:
       LY_TURMA.curso IS NULL
            ↓
       curso = 999
            ↓
       COMPARTILHADA

6. O código da disciplina segue exatamente a regra do
   imp_002_disciplina.py.

7. O código da oferta segue:
       gerar_codigo_oferta(
           disciplina,
           turma,
           ano,
           semestre
       )

8. A área de conhecimento é utilizada somente como
   filtro da disciplina.

9. Área NULL ou vazia é aceita.

10. REC/REP procuram uma turma regular da mesma:
        disciplina
        ano
        semestre
        curso unificado

11. Se REC/REP não possuir uma turma regular de origem,
    o tipo passa para REG.

12. Cada execução reconstrói integralmente a tabela.

13. A reconstrução da tabela é ATÔMICA:
        DELETE + INSERTs + COMMIT
    ocorrem na mesma transação.

    Se qualquer INSERT falhar:
        ROLLBACK
    e a tabela permanece com os dados anteriores.

14. semestreOferta é derivado dinamicamente da própria turma:

        ano + "." + semestre

    Exemplo:
        2026 + 2 -> "2026.2"
        2027 + 1 -> "2027.1"

15. O arquivo pode ser executado diretamente pelo
    botão Play do VS Code.
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

from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    AREAS_CONHECIMENTO_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)

from qstione.core.transformacoes import (
    gerar_codigo_oferta,
    gerar_codigo_tipo_oferta,
    gerar_codigo_disciplina_curso,
    mapear_turno,
    valor_fixo_vazio,
    truncar_texto,
)

from qstione.core.validacoes import (
    validar_codigo_disciplina,
    validar_nome_disciplina,
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
    "imp_005_ofertas.log"
)

logger = logging.getLogger(
    "imp_005_ofertas"
)

logger.setLevel(
    logging.DEBUG
)

logger.handlers.clear()

file_handler = logging.FileHandler(
    LOG_FILE,
    encoding="utf-8"
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

class ImportadorOfertas:
    """
    Importa ofertas preservando a mesma identificação de
    cursos e disciplinas do imp_002_disciplina.py.
    """

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
            if area not in (None, "")
        ]

        self.areas_placeholders = ",".join(
            "?"
            for _ in self.areas
        )

        logger.info(
            "=" * 90
        )

        logger.info(
            "INÍCIO imp_005_ofertas"
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
            "SEMESTRE DA OFERTA: derivado de ano.semestre da turma"
        )

        logger.info(
            "LOG_FILE=%s",
            LOG_FILE
        )

    # =========================================================================
    # CURSO
    # =========================================================================

    @staticmethod
    def _normalizar_curso(
        curso,
        nome_curso=None
    ):
        """
        Normaliza o curso utilizando exatamente o
        MAPEAMENTO_CURSOS do imp_002.

        NULL ou vazio:
            999 / COMPARTILHADA

        Curso mapeado:
            utiliza código e nome definidos no mapeamento.

        Curso não mapeado:
            mantém o código e o nome recebido.
        """

        if curso is None:
            return (
                "999",
                "COMPARTILHADA"
            )

        curso = str(
            curso
        ).strip()

        if not curso:
            return (
                "999",
                "COMPARTILHADA"
            )

        if curso == "999":
            return (
                "999",
                "COMPARTILHADA"
            )

        if curso in MAPEAMENTO_CURSOS:

            return (
                str(
                    MAPEAMENTO_CURSOS[curso][0]
                ),
                str(
                    MAPEAMENTO_CURSOS[curso][1]
                ),
            )

        nome = (
            str(nome_curso).strip()
            if nome_curso
            else curso
        )

        return (
            curso,
            nome
        )

    # =========================================================================
    # SEMESTRE DA OFERTA
    # =========================================================================

    @staticmethod
    def _gerar_semestre_oferta(
        ano,
        semestre
    ):
        """
        Gera o semestre da oferta a partir da própria turma.

        Exemplos:

            2026 / 1 -> 2026.1
            2026 / 2 -> 2026.2
            2027 / 1 -> 2027.1

        O valor é limitado a 6 caracteres, conforme o
        tamanho da coluna semestreOferta.
        """

        if ano is None or semestre is None:
            return ""

        ano_texto = str(
            ano
        ).strip()

        semestre_texto = str(
            semestre
        ).strip()

        if not ano_texto or not semestre_texto:
            return ""

        valor = (
            f"{ano_texto}.{semestre_texto}"
        )

        return valor[:6]

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(self):

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
                        (
                            "imp_005_ofertas",
                        )
                    ).fetchone()
                    is not None
                )

        except Exception:

            logger.exception(
                "Erro verificando existência da tabela."
            )

            return False

    # =========================================================================
    # ÍNDICE
    # =========================================================================

    def _indice_existe(
        self,
        nome
    ):

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
                        (
                            nome,
                        )
                    ).fetchone()
                    is not None
                )

        except Exception:

            logger.exception(
                "Erro verificando índice %s.",
                nome
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):

        if not self._tabela_existe():

            logger.info(
                "Criando tabela imp_005_ofertas..."
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_005_ofertas (

                        codigoOferta NVARCHAR(30) NOT NULL,

                        nomeOferta NVARCHAR(100) NOT NULL,

                        codigoDisciplina NVARCHAR(30) NOT NULL,

                        semestreOferta NVARCHAR(6) NOT NULL,

                        codigoTipoOferta NVARCHAR(3) NOT NULL,

                        codigoOfertaOrigem NVARCHAR(30) NULL,

                        turno NVARCHAR(1) NULL,

                        codigoIdentificacaoAVA NVARCHAR(100) NULL,

                        data_criacao DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            codigoOferta
                        )
                    )
                    """
                )

                conn.commit()

            print(
                "🆕 Tabela imp_005_ofertas criada."
            )

            logger.info(
                "Tabela imp_005_ofertas criada."
            )

        indices = [

            (
                "idx_ofertas_disciplina",

                """
                CREATE INDEX idx_ofertas_disciplina
                ON imp_005_ofertas(
                    codigoDisciplina
                )
                """
            ),

            (
                "idx_ofertas_tipo",

                """
                CREATE INDEX idx_ofertas_tipo
                ON imp_005_ofertas(
                    codigoTipoOferta
                )
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

                    conn.execute(
                        sql
                    )

                    conn.commit()

                logger.info(
                    "Índice %s criado.",
                    nome
                )

            except Exception as e:

                print(
                    f"⚠️ Índice {nome}: {e}"
                )

                logger.warning(
                    "Não foi possível criar índice %s: %s",
                    nome,
                    e
                )

    # =========================================================================
    # OBTENÇÃO DAS TURMAS
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém as ofertas diretamente das turmas.

        A faculdade é determinada por:

            LY_TURMA.curso
                ↓
            LY_CURSO.faculdade

        Nunca por LY_DISCIPLINA.faculdade.

        Turma sem curso é tratada como compartilhada.
        """

        query = f"""
            SELECT DISTINCT

                t.disciplina,

                t.turma,

                t.ano,

                t.semestre,

                t.turno,

                d.nome_compl,

                t.curso,

                c.nome AS nome_curso,

                d.area_conhecimento

            FROM LY_TURMA t

            INNER JOIN LY_DISCIPLINA d
                ON d.disciplina = t.disciplina

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

              AND (
                    d.area_conhecimento IN (
                        {self.areas_placeholders}
                    )

                    OR d.area_conhecimento IS NULL

                    OR d.area_conhecimento = ''
                  )

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
            "Consultando turmas para ofertas..."
        )

        with get_db_connection() as conn:

            rows = conn.execute(
                query,
                params
            ).fetchall()

        logger.info(
            "Turmas encontradas: %d",
            len(rows)
        )

        return rows

    # =========================================================================
    # TURMAS REGULARES
    # =========================================================================

    def obter_turmas_regulares(self):
        """
        Obtém turmas regulares T0* para localizar a oferta
        de origem de REC/REP.

        Utiliza exatamente os mesmos filtros da consulta
        principal.
        """

        query = f"""
            SELECT DISTINCT

                t.disciplina,

                t.turma,

                t.ano,

                t.semestre,

                t.curso

            FROM LY_TURMA t

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            INNER JOIN LY_DISCIPLINA d
                ON d.disciplina = t.disciplina

            WHERE t.ano = ?

              AND t.semestre IN (
                  {self.periodos_placeholders}
              )

              AND t.sit_turma = ?

              AND t.turma LIKE 'T0%'

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

              AND (
                    d.area_conhecimento IN (
                        {self.areas_placeholders}
                    )

                    OR d.area_conhecimento IS NULL

                    OR d.area_conhecimento = ''
                  )

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
            "Consultando turmas regulares T0..."
        )

        with get_db_connection() as conn:

            rows = conn.execute(
                query,
                params
            ).fetchall()

        resultado = {}

        for (
            disciplina,
            turma,
            ano,
            semestre,
            curso_original,
        ) in rows:

            curso_unificado, _ = (
                self._normalizar_curso(
                    curso_original
                )
            )

            chave = (
                disciplina,
                ano,
                semestre,
                curso_unificado,
            )

            resultado.setdefault(
                chave,
                []
            ).append(
                turma
            )

        logger.info(
            "Combinações de turmas regulares: %d",
            len(resultado)
        )

        return resultado

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum
    ):
        """
        Transforma os dados do Lyceum para o layout
        da imp_005_ofertas.
        """

        turmas_regulares = (
            self.obter_turmas_regulares()
        )

        dados = []

        for registro in dados_lyceum:

            (
                disciplina,
                turma,
                ano,
                semestre,
                turno,
                nome_compl,
                curso,
                nome_curso,
                area_conhecimento,
            ) = registro

            # =================================================================
            # DISCIPLINA
            # =================================================================

            if not validar_codigo_disciplina(
                disciplina
            ):
                logger.warning(
                    "Disciplina inválida ignorada: %s",
                    disciplina
                )

                continue

            nome_disciplina = (
                validar_nome_disciplina(
                    nome_compl
                )
            )

            if nome_disciplina is None:

                nome_disciplina = truncar_texto(
                    nome_compl,
                    100
                )

            if not nome_disciplina:

                logger.warning(
                    "Disciplina sem nome ignorada: %s",
                    disciplina
                )

                continue

            # =================================================================
            # CURSO
            # =================================================================

            (
                curso_unificado,
                nome_curso_unificado,
            ) = self._normalizar_curso(
                curso,
                nome_curso
            )

            # =================================================================
            # CÓDIGO DA DISCIPLINA
            # =================================================================

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

            # =================================================================
            # CÓDIGO DA OFERTA
            # =================================================================

            codigo_oferta = (
                gerar_codigo_oferta(
                    disciplina,
                    turma,
                    ano,
                    semestre
                )
            )

            codigo_oferta = truncar_texto(
                codigo_oferta,
                30
            )

            if not codigo_oferta:

                logger.warning(
                    "Oferta sem código ignorada: "
                    "disciplina=%s turma=%s ano=%s semestre=%s",
                    disciplina,
                    turma,
                    ano,
                    semestre
                )

                continue

            # =================================================================
            # TIPO DA OFERTA
            # =================================================================

            tipo = truncar_texto(
                gerar_codigo_tipo_oferta(
                    turma
                ),
                3
            )

            origem = ""

            # =================================================================
            # REC / REP
            # =================================================================

            if tipo in (
                "REC",
                "REP"
            ):

                chave = (
                    disciplina,
                    ano,
                    semestre,
                    curso_unificado,
                )

                turmas_origem = (
                    turmas_regulares.get(
                        chave,
                        []
                    )
                )

                for turma_regular in turmas_origem:

                    origem = (
                        gerar_codigo_oferta(
                            disciplina,
                            turma_regular,
                            ano,
                            semestre
                        )
                    )

                    origem = truncar_texto(
                        origem,
                        30
                    )

                    break

                # -------------------------------------------------------------
                # Sem turma regular de origem:
                # REC/REP passa para REG.
                # -------------------------------------------------------------

                if not origem:

                    tipo = "REG"

            # =================================================================
            # TURNO
            # =================================================================

            turno_mapeado = mapear_turno(
                turno
            )

            turnos_validos = (
                "M",
                "T",
                "N",
                "I",
            )

            if turno_mapeado not in turnos_validos:

                turno_mapeado = "M"

            # =================================================================
            # SEMESTRE DA OFERTA
            # =================================================================

            semestre_oferta = (
                self._gerar_semestre_oferta(
                    ano,
                    semestre
                )
            )

            if not semestre_oferta:

                logger.warning(
                    "Semestre da oferta inválido: "
                    "ano=%s semestre=%s | oferta=%s",
                    ano,
                    semestre,
                    codigo_oferta
                )

                continue

            # =================================================================
            # REGISTRO
            # =================================================================

            dados.append(
                {
                    "codigoOferta": codigo_oferta,

                    "nomeOferta": truncar_texto(
                        turma,
                        100
                    ),

                    "codigoDisciplina": codigo_disciplina,

                    "semestreOferta": semestre_oferta,

                    "codigoTipoOferta": tipo,

                    "codigoOfertaOrigem": (
                        truncar_texto(
                            origem,
                            30
                        )
                        or ""
                    ),

                    "turno": (
                        truncar_texto(
                            turno_mapeado,
                            1
                        )
                        or ""
                    ),

                    "codigoIdentificacaoAVA": (
                        truncar_texto(
                            valor_fixo_vazio(None),
                            100
                        )
                        or ""
                    ),
                }
            )

        # =====================================================================
        # DEDUPLICAÇÃO
        # =====================================================================

        unicos = {}

        duplicados = 0

        for reg in dados:

            codigo = reg[
                "codigoOferta"
            ]

            if codigo not in unicos:

                unicos[codigo] = reg

            else:

                duplicados += 1

                logger.warning(
                    "Oferta duplicada removida: %s",
                    codigo
                )

        resultado = list(
            unicos.values()
        )

        logger.info(
            "Registros transformados: %d",
            len(dados)
        )

        logger.info(
            "Duplicidades removidas: %d",
            duplicados
        )

        logger.info(
            "Registros únicos por codigoOferta: %d",
            len(resultado)
        )

        return resultado

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados
    ):
        """
        Reconstrói a tabela imp_005_ofertas de forma ATÔMICA.

        IMPORTANTE:

        O DELETE e todos os INSERTs ocorrem na mesma transação.

        Se qualquer operação falhar:

            ROLLBACK

        Assim, os dados anteriores continuam preservados.

        Somente quando TODOS os registros forem inseridos
        com sucesso ocorre:

            COMMIT
        """

        self._criar_tabela()

        total_processados = len(
            dados_transformados
        )

        if not dados_transformados:

            logger.warning(
                "Nenhum registro transformado. "
                "A tabela NÃO será limpa."
            )

            print(
                "⚠️ Nenhuma oferta válida encontrada."
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 0,
                "total_processados": 0,
                "rollback": False,
            }

        inseridos = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                cursor = conn.cursor()

                try:

                    # =========================================================
                    # INÍCIO DA RECONSTRUÇÃO
                    # =========================================================

                    logger.info(
                        "Iniciando reconstrução transacional "
                        "da imp_005_ofertas."
                    )

                    # ---------------------------------------------------------
                    # LIMPA A TABELA
                    # ---------------------------------------------------------

                    cursor.execute(
                        """
                        DELETE FROM imp_005_ofertas
                        """
                    )

                    logger.info(
                        "Tabela imp_005_ofertas limpa "
                        "dentro da transação."
                    )

                    # ---------------------------------------------------------
                    # INSERT
                    # ---------------------------------------------------------

                    for indice, reg in enumerate(
                        dados_transformados,
                        start=1
                    ):

                        try:

                            cursor.execute(
                                """
                                INSERT INTO imp_005_ofertas
                                (
                                    codigoOferta,
                                    nomeOferta,
                                    codigoDisciplina,
                                    semestreOferta,
                                    codigoTipoOferta,
                                    codigoOfertaOrigem,
                                    turno,
                                    codigoIdentificacaoAVA,
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
                                        "nomeOferta"
                                    ],

                                    reg[
                                        "codigoDisciplina"
                                    ],

                                    reg[
                                        "semestreOferta"
                                    ],

                                    reg[
                                        "codigoTipoOferta"
                                    ],

                                    reg[
                                        "codigoOfertaOrigem"
                                    ] or "",

                                    reg[
                                        "turno"
                                    ] or "",

                                    reg[
                                        "codigoIdentificacaoAVA"
                                    ] or "",
                                )
                            )

                            inseridos += 1

                        except Exception as e:

                            logger.exception(
                                "Erro inserindo oferta "
                                "%s | registro %d/%d",
                                reg[
                                    "codigoOferta"
                                ],
                                indice,
                                total_processados
                            )

                            print(
                                f"✗ Erro na oferta "
                                f"{reg['codigoOferta']}: {e}"
                            )

                            # =================================================
                            # IMPORTANTE:
                            # Qualquer erro cancela toda a reconstrução.
                            # =================================================

                            raise

                    # =========================================================
                    # COMMIT SOMENTE SE TODOS OS INSERTS FUNCIONARAM
                    # =========================================================

                    conn.commit()

                    logger.info(
                        "COMMIT realizado com sucesso."
                    )

                    logger.info(
                        "Reconstrução concluída: %d ofertas.",
                        inseridos
                    )

                except Exception:

                    # =========================================================
                    # ROLLBACK
                    # =========================================================

                    try:

                        conn.rollback()

                        logger.error(
                            "ROLLBACK executado. "
                            "A reconstrução da imp_005_ofertas "
                            "foi cancelada integralmente."
                        )

                        print(
                            "↩️ ROLLBACK executado. "
                            "Os dados anteriores foram preservados."
                        )

                    except Exception as rollback_error:

                        logger.exception(
                            "Falha ao executar ROLLBACK: %s",
                            rollback_error
                        )

                    raise

        except Exception as e:

            logger.exception(
                "Erro durante reconstrução da tabela."
            )

            print(
                f"❌ Falha na reconstrução: {e}"
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 1,
                "total_processados": total_processados,
                "rollback": True,
            }

        return {
            "total_inseridos": inseridos,
            "total_atualizados": 0,
            "total_erros": 0,
            "total_processados": total_processados,
            "rollback": False,
        }

    # =========================================================================
    # EXECUÇÃO
    # =========================================================================

    def executar_importacao(self):

        print(
            "=" * 70
        )

        print(
            "IMPORTAÇÃO: imp_005_ofertas"
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
            f"📚 Situação: {SITUACAO_TURMA_VALIDA}"
        )

        print(
            "📅 semestreOferta: ano.semestre da turma"
        )

        print(
            f"📄 Log: {LOG_FILE}"
        )

        # =====================================================================
        # 1. CONSULTA
        # =====================================================================

        try:

            dados = (
                self.obter_dados_lyceum()
            )

        except Exception as e:

            logger.exception(
                "Falha na consulta ao Lyceum."
            )

            print(
                f"❌ Erro consultando Lyceum: {e}"
            )

            return []

        print(
            f"📊 Turmas encontradas: "
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
                "Falha durante transformação dos dados."
            )

            print(
                f"❌ Erro durante transformação: {e}"
            )

            return []

        print(
            f"✅ Ofertas únicas: "
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

        if resultado.get(
            "rollback",
            False
        ):

            print(
                "\n❌ IMPORTAÇÃO CANCELADA"
            )

            print(
                "↩️ Nenhuma alteração parcial foi mantida."
            )

        else:

            print(
                f"\n📈 Inseridos: "
                f"{resultado['total_inseridos']}"
            )

            print(
                f"✗ Erros: "
                f"{resultado['total_erros']}"
            )

            print(
                "✅ Reconstrução concluída com sucesso."
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
            )
        )

        logger.info(
            "FIM imp_005_ofertas"
        )

        return transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    ImportadorOfertas().executar_importacao()
