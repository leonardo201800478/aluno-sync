"""
qstione/importadores/imp_013_unidades_avaliacao_regras.py

Gerador independente de unidades de avaliação.

IMPORTANTE
----------
Este arquivo é uma alternativa ao:

    imp_013_unidades_avaliacao.py

O importador original NÃO é alterado.

===============================================================================
FONTE DAS OFERTAS
===============================================================================

A fonte de verdade das disciplinas ofertadas é LY_TURMA.

Uma disciplina somente será processada quando existir uma turma que:

    - pertença ao ANO configurado;
    - pertença a um dos PERIODOS configurados;
    - esteja com situação válida;
    - pertença a uma faculdade configurada.

O curso da oferta é sempre LY_TURMA.curso ORIGINAL.

===============================================================================
CURSO
===============================================================================

Cursos reais são validados pela faculdade através de LY_CURSO.

Os seguintes valores representam curso compartilhado:

    NULL
    vazio
    999

Eles são convertidos para:

    999 - COMPARTILHADA

Cursos reais somente são unificados pelo MAPEAMENTO_CURSOS
depois que todas as informações dependentes do código original
foram resolvidas.

===============================================================================
CURRÍCULO
===============================================================================

LY_GRADE possui:

    curriculo
    curso
    disciplina
    turno

O campo curriculo sozinho NÃO é um identificador único.

O identificador lógico do currículo é:

    curriculo + curso ORIGINAL + turno ORIGINAL

Exemplo:

    20261 + 014 + MV

resulta em:

    20261-014-MV

Outro exemplo:

    20261 + 056 + MV
    20261 + 141 + MV

são DOIS contextos curriculares diferentes:

    20261-056-MV
    20261-141-MV

Mesmo que posteriormente:

    141 -> 056

pelo MAPEAMENTO_CURSOS.

===============================================================================
ORDEM DA RESOLUÇÃO
===============================================================================

1. LY_TURMA determina a oferta.
2. Preserva curso original.
3. Consulta LY_GRADE usando curso ORIGINAL.
4. Identifica curriculo + curso original + turno original.
5. Determina a menor série dentro do contexto curricular.
6. Somente então aplica MAPEAMENTO_CURSOS.
7. Determina o modelo de avaliações.
8. Gera as avaliações.

===============================================================================
MENOR SÉRIE
===============================================================================

Quando existirem várias ocorrências para o mesmo:

    curriculo
    curso original
    disciplina
    turno

será utilizada a MENOR serie_ideal.

Não será feito MIN() misturando currículos diferentes.

===============================================================================
ORDEM
===============================================================================

A ordem das disciplinas segue a ordem em que as ofertas são
obtidas de LY_TURMA.

Não utilizar sorted() para reordenar disciplinas ou currículos.

A ordem das avaliações é determinada exclusivamente pela regra
de cada curso/currículo.

===============================================================================
AVALIAÇÕES
===============================================================================

GERAL:

    1 - AVD1
    2 - AVD2
    3 - SUBS


ENGENHARIA:

    1 - S1P1
    2 - S1P2
    3 - S2P1
    4 - S2P2


MEDICINA - CURRÍCULO NOVO:

    1 - S1
    2 - S2
    3 - SUBS
    4 - S1-D/A
    5 - S2-D/A
    6 - SUBS-D/A
    7 - SI


MEDICINA - CURRÍCULO ANTIGO:

    1 - PM
    2 - SC
    3 - PF
    4 - PE
    5 - SI


MEDICINA:

    20152-014-MV
        -> currículo antigo

    20231-014-MV
        -> currículo novo

    20251-014-MV
        -> currículo novo

    20261-014-MV
        -> currículo novo

Currículos futuros de Medicina posteriores a 20231 também são
considerados novos.

===============================================================================
EXECUÇÃO
===============================================================================

O arquivo pode ser executado diretamente pelo botão PLAY do VS Code.
"""

from __future__ import annotations

import logging
import os
import sys

from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
# IMPORTS DO PROJETO
# =============================================================================

from core.database import get_db_connection

from qstione.core.transformacoes import (
    converter_inteiro,
    gerar_codigo_disciplina_curso,
    truncar_texto,
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
    "imp_013_unidades_avaliacao_regras"
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
# CONSTANTES
# =============================================================================

CURSO_COMPARTILHADO = "999"

CURSO_MEDICINA = "014"


# =============================================================================
# CURSOS DE ENGENHARIA
# =============================================================================

CURSOS_ENGENHARIA = {
    "006",
    "017",
    "044",
    "059",
    "079",
    "097",
}


# =============================================================================
# CURRÍCULOS DE MEDICINA
# =============================================================================

CURRICULOS_MEDICINA_ANTIGO = {
    "20152-014-MV",
}


CURRICULOS_MEDICINA_NOVOS = {
    "20231-014-MV",
    "20251-014-MV",
    "20261-014-MV",
}


# =============================================================================
# REGRA GERAL
# =============================================================================

AVALIACOES_GERAIS = (
    (
        1,
        "-AVD1",
        "Avaliação 1",
    ),
    (
        2,
        "-AVD2",
        "Avaliação 2",
    ),
    (
        3,
        "-SUBS",
        "Substitutiva",
    ),
)


# =============================================================================
# REGRA ENGENHARIA
# =============================================================================

AVALIACOES_ENGENHARIA = (
    (
        1,
        "-S1P1",
        "Somativa 1 Parte 1",
    ),
    (
        2,
        "-S1P2",
        "Somativa 1 Parte 2",
    ),
    (
        3,
        "-S2P1",
        "Somativa 2 Parte 1",
    ),
    (
        4,
        "-S2P2",
        "Somativa 2 Parte 2",
    ),
)


# =============================================================================
# REGRA MEDICINA - NOVA
# =============================================================================

AVALIACOES_MEDICINA_NOVO = (
    (
        1,
        "-S1",
        "Somativa 1",
    ),
    (
        2,
        "-S2",
        "Somativa 2",
    ),
    (
        3,
        "-SUBS",
        "Prova Substitutiva",
    ),
    (
        4,
        "-S1-D/A",
        "Prova 1 Adap-Dep",
    ),
    (
        5,
        "-S2-D/A",
        "Prova 2 Adap-Dep",
    ),
    (
        6,
        "-SUBS-D/A",
        "Prova Substitutiva Adap-Dep",
    ),
    (
        7,
        "-SI",
        "Simulado",
    ),
)


# =============================================================================
# REGRA MEDICINA - ANTIGA
# =============================================================================

AVALIACOES_MEDICINA_ANTIGO = (
    (
        1,
        "-PM",
        "Prova Módulo",
    ),
    (
        2,
        "-SC",
        "Segunda Chamada",
    ),
    (
        3,
        "-PF",
        "Prova Final",
    ),
    (
        4,
        "-PE",
        "Prova Especial",
    ),
    (
        5,
        "-SI",
        "Simulado",
    ),
)


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorUnidadesAvaliacaoRegras:
    """
    Gera unidades de avaliação para todas as disciplinas efetivamente
    ofertadas pelas turmas válidas.

    O processamento mantém separado:

        curso original
        currículo original
        turno original
        curso unificado

    durante as etapas em que essa distinção é necessária.
    """

    NOME_TABELA = (
        "imp_013_unidades_avaliacao"
    )

    # =========================================================================
    # INIT
    # =========================================================================

    def __init__(self):
        """
        Inicializa os placeholders utilizados nas consultas SQL.
        """

        self.periodos_placeholders = ",".join(
            "?"
            for _ in PERIODOS_VIGENTES
        )

        self.faculdades_placeholders = ",".join(
            "?"
            for _ in FACULDADES_INCLUIDAS
        )

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(self) -> bool:
        """
        Verifica se a tabela destino existe.
        """

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
                    self.NOME_TABELA,
                ),
            ).fetchone()

        return row is not None

    # =========================================================================

    def _criar_tabela(self) -> None:
        """
        Cria a tabela destino caso ela não exista.
        """

        if self._tabela_existe():
            return

        logger.info(
            "🆕 Criando tabela %s...",
            self.NOME_TABELA,
        )

        with get_db_connection(
            database_name="qstione"
        ) as conn:

            conn.execute(
                f"""
                CREATE TABLE {self.NOME_TABELA} (

                    codigoUnidade NVARCHAR(200) NOT NULL,

                    nomeUnidade NVARCHAR(64) NOT NULL,

                    codigoCurso NVARCHAR(30) NULL,

                    codigoDisciplina NVARCHAR(30) NULL,

                    ordemExibicao INT NOT NULL,

                    codigoAgrupamento NVARCHAR(200) NOT NULL,

                    data_criacao DATETIME2
                        DEFAULT GETDATE(),

                    data_atualizacao DATETIME2
                        DEFAULT GETDATE(),

                    PRIMARY KEY (
                        codigoUnidade
                    )
                )
                """
            )

            conn.commit()

        logger.info(
            "✅ Tabela criada."
        )

    # =========================================================================
    # NORMALIZAÇÃO
    # =========================================================================

    @staticmethod
    def _normalizar_valor(
        valor: Any
    ) -> str:
        """
        Converte um valor para string limpa.

        Parameters
        ----------
        valor:
            Valor original.

        Returns
        -------
        str
            Valor normalizado.
        """

        if valor is None:
            return ""

        return str(
            valor
        ).strip()

    # =========================================================================
    # CURSO
    # =========================================================================

    @staticmethod
    def normalizar_curso(
        curso: Any
    ) -> Tuple[str, str]:
        """
        Converte o curso ORIGINAL para o curso utilizado pelo Qstione.

        IMPORTANTE:
        Esta função deve ser chamada somente depois que informações
        dependentes do código original já tiverem sido resolvidas.

        Regras:

            NULL
            vazio
            999

        tornam-se:

            999 / COMPARTILHADA

        Cursos existentes no MAPEAMENTO_CURSOS são unificados.

        Um código não mapeado não é aceito como curso final e é tratado
        como compartilhado.
        """

        curso = (
            str(curso).strip()
            if curso is not None
            else ""
        )

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

        mapeamento = MAPEAMENTO_CURSOS.get(
            curso
        )

        if mapeamento is None:

            logger.warning(
                "⚠️ Curso %s não encontrado no MAPEAMENTO_CURSOS. "
                "Convertendo para 999.",
                curso,
            )

            return (
                CURSO_COMPARTILHADO,
                "COMPARTILHADA",
            )

        codigo, nome = mapeamento

        return (
            str(codigo).strip(),
            str(nome).strip(),
        )

    # =========================================================================
    # TURMAS
    # =========================================================================

    def obter_turmas(self) -> List[Dict[str, Any]]:
        """
        Obtém todas as turmas válidas para os filtros.

        LY_TURMA é a fonte de verdade da oferta.

        Uma tabela complementar não pode eliminar uma turma válida.

        Para curso real:
            LY_CURSO.faculdade deve estar em FACULDADES_INCLUIDAS.

        Para curso NULL/vazio/999:
            a turma é tratada como compartilhada.

        Returns
        -------
        list[dict]
            Turmas na ordem da consulta.
        """

        if not PERIODOS_VIGENTES:
            raise ValueError(
                "PERIODOS_VIGENTES não pode estar vazio."
            )

        if not FACULDADES_INCLUIDAS:
            raise ValueError(
                "FACULDADES_INCLUIDAS não pode estar vazio."
            )

        sql = f"""
            SELECT DISTINCT

                t.ano,

                t.semestre,

                t.turma,

                t.disciplina,

                t.curso,

                c.nome AS nome_curso,

                c.faculdade

            FROM LY_TURMA t

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

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

            ORDER BY

                t.ano,

                t.semestre,

                t.turma,

                t.disciplina
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        )

        logger.info(
            "🔎 Consultando LY_TURMA..."
        )

        with get_db_connection(
            database_name="lyceum"
        ) as conn:

            rows = conn.execute(
                sql,
                params
            ).fetchall()

        colunas = (
            "ano",
            "semestre",
            "turma",
            "disciplina",
            "curso",
            "nome_curso",
            "faculdade",
        )

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
            len(dados),
        )

        return dados

    # =========================================================================
    # GRADE
    # =========================================================================

    def obter_grade_das_ofertas(
        self,
        turmas: List[Dict[str, Any]]
    ) -> Dict[
        Tuple[str, str],
        List[Dict[str, Any]]
    ]:
        """
        Consulta LY_GRADE somente para as combinações de curso ORIGINAL
        e disciplina existentes nas ofertas.

        A chave utilizada é:

            (curso_original, disciplina)

        O curso não é unificado antes da consulta.

        Returns
        -------
        dict
            Índice:

                (curso_original, disciplina)
                    ->
                lista de registros de grade
        """

        pares = []

        vistos = set()

        for turma in turmas:

            disciplina = self._normalizar_valor(
                turma.get(
                    "disciplina"
                )
            )

            curso = self._normalizar_valor(
                turma.get(
                    "curso"
                )
            )

            if not disciplina:
                continue

            if not curso:
                continue

            if curso == CURSO_COMPARTILHADO:
                continue

            chave = (
                curso,
                disciplina,
            )

            if chave in vistos:
                continue

            vistos.add(
                chave
            )

            pares.append(
                chave
            )

        if not pares:

            logger.info(
                "📚 Nenhuma combinação curso/disciplina requer LY_GRADE."
            )

            return {}

        condicoes = []

        params = []

        for curso, disciplina in pares:

            condicoes.append(
                """
                (
                    LTRIM(RTRIM(
                        CAST(g.curso AS NVARCHAR(30))
                    )) = ?

                    AND LTRIM(RTRIM(
                        CAST(g.disciplina AS NVARCHAR(100))
                    )) = ?
                )
                """
            )

            params.extend(
                [
                    curso,
                    disciplina,
                ]
            )

        sql = f"""
            SELECT

                g.curriculo,

                g.curso,

                g.disciplina,

                g.turno,

                g.serie_ideal

            FROM LY_GRADE g

            WHERE
                {" OR ".join(condicoes)}

            ORDER BY

                g.curso,

                g.disciplina,

                g.curriculo,

                g.turno
        """

        logger.info(
            "🔎 Consultando LY_GRADE para %d combinações...",
            len(pares),
        )

        with get_db_connection(
            database_name="lyceum"
        ) as conn:

            rows = conn.execute(
                sql,
                params
            ).fetchall()

        indice = {}

        for (
            curriculo,
            curso,
            disciplina,
            turno,
            serie_ideal,
        ) in rows:

            curso = self._normalizar_valor(
                curso
            )

            disciplina = self._normalizar_valor(
                disciplina
            )

            curriculo = self._normalizar_valor(
                curriculo
            )

            turno = self._normalizar_valor(
                turno
            )

            if not curso or not disciplina:
                continue

            chave = (
                curso,
                disciplina,
            )

            indice.setdefault(
                chave,
                []
            ).append(
                {
                    "curriculo":
                        curriculo,

                    "curso":
                        curso,

                    "disciplina":
                        disciplina,

                    "turno":
                        turno,

                    "serie_ideal":
                        serie_ideal,
                }
            )

        logger.info(
            "📚 Combinações com grade encontradas: %d",
            len(indice),
        )

        return indice

    # =========================================================================
    # ID CURRÍCULO
    # =========================================================================

    @staticmethod
    def gerar_id_curriculo(
        curriculo: Any,
        curso_original: Any,
        turno_original: Any,
    ) -> str:
        """
        Gera o identificador único do currículo.

        A identidade é:

            curriculo + curso ORIGINAL + turno ORIGINAL

        Exemplo:

            20261 + 014 + MV

        resulta:

            20261-014-MV

        Nenhum mapeamento de curso é aplicado nesta função.
        """

        curriculo = str(
            curriculo or ""
        ).strip()

        curso_original = str(
            curso_original or ""
        ).strip()

        turno_original = str(
            turno_original or ""
        ).strip()

        if (
            not curriculo
            or not curso_original
            or not turno_original
        ):
            return ""

        return (
            f"{curriculo}-"
            f"{curso_original}-"
            f"{turno_original}"
        )

    # =========================================================================
    # RESOLVER CONTEXTOS CURRICULARES
    # =========================================================================

    def resolver_contextos_curriculares(
        self,
        curso_original: Any,
        disciplina: Any,
        indice_grade,
    ) -> List[Dict[str, Any]]:
        """
        Resolve os contextos curriculares de uma disciplina.

        A busca utiliza:

            curso ORIGINAL
            disciplina

        Depois agrupa por:

            curriculo
            curso original
            turno original

        Para cada contexto, a menor série é mantida.

        A ordem da primeira ocorrência na LY_GRADE é preservada.

        Returns
        -------
        list[dict]
            Contextos curriculares.
        """

        curso_original = self._normalizar_valor(
            curso_original
        )

        disciplina = self._normalizar_valor(
            disciplina
        )

        if (
            not curso_original
            or curso_original == CURSO_COMPARTILHADO
            or not disciplina
        ):
            return []

        registros = indice_grade.get(
            (
                curso_original,
                disciplina,
            ),
            []
        )

        if not registros:
            return []

        contextos = {}

        ordem_contextos = []

        for registro in registros:

            curriculo = self._normalizar_valor(
                registro.get(
                    "curriculo"
                )
            )

            curso_grade = self._normalizar_valor(
                registro.get(
                    "curso"
                )
            )

            turno = self._normalizar_valor(
                registro.get(
                    "turno"
                )
            )

            if not curriculo:
                continue

            if not curso_grade:
                continue

            if not turno:
                continue

            # ---------------------------------------------------------------
            # O curso da grade precisa ser exatamente o curso original
            # da oferta.
            # ---------------------------------------------------------------

            if curso_grade != curso_original:
                continue

            id_curriculo = (
                self.gerar_id_curriculo(
                    curriculo,
                    curso_grade,
                    turno,
                )
            )

            if not id_curriculo:
                continue

            chave = (
                curriculo,
                curso_grade,
                turno,
            )

            serie = registro.get(
                "serie_ideal"
            )

            serie = converter_inteiro(
                serie
            )

            if serie is not None and serie <= 0:
                serie = None

            # ---------------------------------------------------------------
            # PRIMEIRA OCORRÊNCIA
            # ---------------------------------------------------------------

            if chave not in contextos:

                contextos[chave] = {
                    "id_curriculo":
                        id_curriculo,

                    "curriculo":
                        curriculo,

                    "curso_original":
                        curso_grade,

                    "turno_original":
                        turno,

                    "serie_ideal":
                        serie,
                }

                ordem_contextos.append(
                    chave
                )

                continue

            # ---------------------------------------------------------------
            # MESMO CONTEXTO:
            # manter a menor série.
            # ---------------------------------------------------------------

            existente = contextos[
                chave
            ]

            serie_existente = (
                existente.get(
                    "serie_ideal"
                )
            )

            if serie is None:
                continue

            if (
                serie_existente is None
                or serie < serie_existente
            ):

                existente[
                    "serie_ideal"
                ] = serie

        return [
            contextos[chave]
            for chave in ordem_contextos
        ]

    # =========================================================================
    # MENOR SÉRIE
    # =========================================================================

    @staticmethod
    def resolver_periodo(
        serie_ideal: Optional[int]
    ) -> int:
        """
        Converte serie_ideal para o período utilizado pelo Qstione.

        Quando não existe uma série válida, utiliza 1.

        Quando a série é menor ou igual a zero, utiliza 1.
        """

        if serie_ideal is None:
            return 1

        serie_ideal = converter_inteiro(
            serie_ideal
        )

        if serie_ideal is None:
            return 1

        if serie_ideal <= 0:
            return 1

        return serie_ideal

    # =========================================================================
    # REGRA DE AVALIAÇÃO
    # =========================================================================

    @staticmethod
    def obter_avaliacoes(
        codigo_curso: str,
        id_curriculo: str,
    ) -> Tuple[
        str,
        Tuple[
            Tuple[int, str, str],
            ...
        ],
    ]:
        """
        Determina o modelo de avaliação.

        A decisão utiliza o curso UNIFICADO.

        Medicina utiliza o ID completo do currículo:

            curriculo-curso-original-turno

        Engenharia utiliza somente o curso unificado.

        Os demais cursos utilizam a regra geral.
        """

        codigo_curso = str(
            codigo_curso or ""
        ).strip()

        id_curriculo = str(
            id_curriculo or ""
        ).strip()

        # =====================================================================
        # MEDICINA
        # =====================================================================

        if codigo_curso == CURSO_MEDICINA:

            if (
                id_curriculo
                in CURRICULOS_MEDICINA_ANTIGO
            ):

                return (
                    "MEDICINA_ANTIGO",
                    AVALIACOES_MEDICINA_ANTIGO,
                )

            if (
                id_curriculo
                in CURRICULOS_MEDICINA_NOVOS
            ):

                return (
                    "MEDICINA_NOVO",
                    AVALIACOES_MEDICINA_NOVO,
                )

            # -------------------------------------------------------------
            # Currículos futuros de Medicina
            # -------------------------------------------------------------

            partes = id_curriculo.split(
                "-"
            )

            if partes:

                try:

                    codigo_curriculo = int(
                        partes[0]
                    )

                except ValueError:

                    codigo_curriculo = None

                if (
                    codigo_curriculo is not None
                    and codigo_curriculo > 20231
                ):

                    return (
                        "MEDICINA_NOVO",
                        AVALIACOES_MEDICINA_NOVO,
                    )

            return (
                "MEDICINA_NAO_MAPEADO",
                (),
            )

        # =====================================================================
        # ENGENHARIA
        # =====================================================================

        if (
            codigo_curso
            in CURSOS_ENGENHARIA
        ):

            return (
                "ENGENHARIA",
                AVALIACOES_ENGENHARIA,
            )

        # =====================================================================
        # GERAL
        # =====================================================================

        return (
            "GERAL",
            AVALIACOES_GERAIS,
        )

    # =========================================================================
    # CÓDIGO DISCIPLINA
    # =========================================================================

    @staticmethod
    def gerar_codigo_disciplina(
        disciplina: Any,
        codigo_curso: str,
        nome_curso: str,
    ) -> str:
        """
        Gera o código da disciplina utilizando a mesma função
        utilizada pelos demais importadores.
        """

        disciplina = str(
            disciplina or ""
        ).strip()

        if not disciplina:
            return ""

        codigo = (
            gerar_codigo_disciplina_curso(
                disciplina,
                nome_curso,
                codigo_curso,
            )
        )

        return truncar_texto(
            codigo,
            30,
        )

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        turmas: List[Dict[str, Any]],
        indice_grade,
    ) -> List[Dict[str, Any]]:
        """
        Transforma as ofertas em unidades de avaliação.

        A ordem da lista de turmas é preservada.

        Para cada oferta:

            curso original
                ↓
            grade do curso original
                ↓
            currículo original
                ↓
            menor série
                ↓
            curso unificado
                ↓
            regra de avaliação
                ↓
            unidades

        A mesma disciplina pode possuir vários contextos:

            DISC001 / 056
            DISC001 / 999

        e ambos são mantidos.
        """

        dados = []

        # ---------------------------------------------------------------------
        # Contextos processados.
        #
        # NÃO usamos set para ordenar.
        # Ele serve somente para impedir processamento duplicado.
        # ---------------------------------------------------------------------

        contextos_processados = set()

        # ---------------------------------------------------------------------
        # Evita duplicidade de codigoUnidade.
        # ---------------------------------------------------------------------

        codigos_unidade = set()

        # ---------------------------------------------------------------------
        # Estatísticas.
        # ---------------------------------------------------------------------

        estatisticas_cursos = Counter()
        estatisticas_regras = Counter()
        estatisticas_curriculos = Counter()

        for turma in turmas:

            disciplina = self._normalizar_valor(
                turma.get(
                    "disciplina"
                )
            )

            if not disciplina:
                continue

            curso_original = (
                turma.get(
                    "curso"
                )
            )

            curso_original_str = (
                self._normalizar_valor(
                    curso_original
                )
            )

            # =================================================================
            # CURSO UNIFICADO
            #
            # Esta operação ocorre APENAS depois da separação do curso original.
            # =================================================================

            codigo_curso, nome_curso = (
                self.normalizar_curso(
                    curso_original
                )
            )

            # =================================================================
            # CONTEXTO DA OFERTA
            # =================================================================
            #
            # Para cursos reais:
            #
            #     disciplina + curso original
            #
            # Para compartilhada:
            #
            #     disciplina + 999
            #
            # =================================================================

            contexto_oferta = (
                disciplina,
                curso_original_str,
            )

            if contexto_oferta in contextos_processados:
                continue

            contextos_processados.add(
                contexto_oferta
            )

            # =================================================================
            # CURSO COMPARTILHADO
            # =================================================================

            if (
                codigo_curso
                == CURSO_COMPARTILHADO
            ):

                contextos_curriculares = [
                    {
                        "id_curriculo": "",
                        "curriculo": "",
                        "curso_original":
                            curso_original_str,
                        "turno_original": "",
                        "serie_ideal": None,
                    }
                ]

            # =================================================================
            # CURSO REAL
            # =================================================================

            else:

                contextos_curriculares = (
                    self.resolver_contextos_curriculares(
                        curso_original_str,
                        disciplina,
                        indice_grade,
                    )
                )

                # -------------------------------------------------------------
                # Não existe currículo na grade.
                #
                # Para cursos que não precisam de currículo para definir
                # avaliação, ainda podemos gerar a regra geral.
                #
                # Medicina, entretanto, precisa de currículo.
                # -------------------------------------------------------------

                if not contextos_curriculares:

                    contextos_curriculares = [
                        {
                            "id_curriculo": "",
                            "curriculo": "",
                            "curso_original":
                                curso_original_str,
                            "turno_original": "",
                            "serie_ideal": None,
                        }
                    ]

            # =================================================================
            # PROCESSAMENTO DOS CONTEXTOS CURRICULARES
            # =================================================================

            for contexto in (
                contextos_curriculares
            ):

                id_curriculo = (
                    contexto.get(
                        "id_curriculo"
                    )
                    or ""
                )

                serie_ideal = (
                    contexto.get(
                        "serie_ideal"
                    )
                )

                # =============================================================
                # MEDICINA PRECISA DE CURRÍCULO
                # =============================================================

                if (
                    codigo_curso == CURSO_MEDICINA
                    and not id_curriculo
                ):

                    logger.warning(
                        "⚠️ Medicina ignorada por ausência de currículo: "
                        "disciplina=%s | curso_original=%s",
                        disciplina,
                        curso_original_str,
                    )

                    continue

                # =============================================================
                # REGRA DE AVALIAÇÃO
                # =============================================================

                nome_regra, avaliacoes = (
                    self.obter_avaliacoes(
                        codigo_curso,
                        id_curriculo,
                    )
                )

                # =============================================================
                # MEDICINA COM CURRÍCULO DESCONHECIDO
                # =============================================================

                if (
                    codigo_curso == CURSO_MEDICINA
                    and nome_regra
                    == "MEDICINA_NAO_MAPEADO"
                ):

                    logger.warning(
                        "⚠️ Currículo de Medicina não mapeado: "
                        "%s | disciplina=%s",
                        id_curriculo,
                        disciplina,
                    )

                    continue

                # =============================================================
                # CÓDIGO DA DISCIPLINA
                # =============================================================

                codigo_disciplina = (
                    self.gerar_codigo_disciplina(
                        disciplina,
                        codigo_curso,
                        nome_curso,
                    )
                )

                if not codigo_disciplina:
                    continue

                # =============================================================
                # PERÍODO
                # =============================================================

                periodo = (
                    self.resolver_periodo(
                        serie_ideal
                    )
                )

                estatisticas_cursos[
                    codigo_curso
                ] += 1

                estatisticas_regras[
                    nome_regra
                ] += 1

                estatisticas_curriculos[
                    id_curriculo
                    or "<SEM_CURRICULO>"
                ] += 1

                # =============================================================
                # AVALIAÇÕES
                # =============================================================

                for (
                    ordem,
                    sufixo,
                    nome_unidade,
                ) in avaliacoes:

                    codigo_unidade = truncar_texto(
                        f"{codigo_disciplina}{sufixo}",
                        200,
                    )

                    # ---------------------------------------------------------
                    # Não duplica uma unidade final.
                    #
                    # A primeira relação encontrada pela ordem das ofertas
                    # prevalece.
                    # ---------------------------------------------------------

                    if (
                        codigo_unidade
                        in codigos_unidade
                    ):
                        continue

                    codigos_unidade.add(
                        codigo_unidade
                    )

                    dados.append(
                        {
                            "codigoUnidade":
                                codigo_unidade,

                            "nomeUnidade":
                                truncar_texto(
                                    nome_unidade,
                                    64,
                                ),

                            "codigoCurso":
                                truncar_texto(
                                    codigo_curso,
                                    30,
                                ),

                            "codigoDisciplina":
                                truncar_texto(
                                    codigo_disciplina,
                                    30,
                                ),

                            "ordemExibicao":
                                converter_inteiro(
                                    ordem
                                ) or 0,

                            "codigoAgrupamento":
                                codigo_unidade,

                            "periodo":
                                periodo,

                            # -------------------------------------------------
                            # Informações auxiliares para diagnóstico.
                            # -------------------------------------------------

                            "_disciplina":
                                disciplina,

                            "_curso_original":
                                curso_original_str,

                            "_curso_unificado":
                                codigo_curso,

                            "_curriculo":
                                id_curriculo,

                            "_serie_ideal":
                                serie_ideal,

                            "_regra":
                                nome_regra,
                        }
                    )

        # =====================================================================
        # LOG FINAL DA TRANSFORMAÇÃO
        # =====================================================================

        logger.info(
            "✅ Unidades geradas: %d",
            len(dados),
        )

        logger.info(
            "📚 Contextos disciplina/curso processados: %d",
            len(contextos_processados),
        )

        logger.info(
            "📋 Regras utilizadas:"
        )

        for regra, quantidade in (
            estatisticas_regras.items()
        ):

            logger.info(
                "   %s -> %d",
                regra,
                quantidade,
            )

        logger.info(
            "📚 Cursos:"
        )

        for curso, quantidade in (
            estatisticas_cursos.items()
        ):

            logger.info(
                "   %s -> %d",
                curso,
                quantidade,
            )

        logger.info(
            "📋 Currículos:"
        )

        for curriculo, quantidade in (
            estatisticas_curriculos.items()
        ):

            logger.info(
                "   %s -> %d",
                curriculo,
                quantidade,
            )

        return dados

    # =========================================================================
    # VALIDAÇÃO
    # =========================================================================

    @staticmethod
    def validar_dados(
        dados: List[Dict[str, Any]]
    ) -> None:
        """
        Valida os dados antes da gravação.

        Verifica:

            - codigoUnidade;
            - codigoDisciplina;
            - codigoCurso;
            - duplicidade de codigoUnidade.
        """

        erros = []

        codigos = set()

        for indice, registro in enumerate(
            dados,
            start=1,
        ):

            codigo_unidade = (
                registro.get(
                    "codigoUnidade"
                )
            )

            codigo_disciplina = (
                registro.get(
                    "codigoDisciplina"
                )
            )

            codigo_curso = (
                registro.get(
                    "codigoCurso"
                )
            )

            if not codigo_unidade:

                erros.append(
                    f"Registro {indice}: "
                    "codigoUnidade vazio"
                )

            if not codigo_disciplina:

                erros.append(
                    f"Registro {indice}: "
                    "codigoDisciplina vazio"
                )

            if not codigo_curso:

                erros.append(
                    f"Registro {indice}: "
                    "codigoCurso vazio"
                )

            if (
                codigo_unidade
                and codigo_unidade in codigos
            ):

                erros.append(
                    "codigoUnidade duplicado: "
                    f"{codigo_unidade}"
                )

            if codigo_unidade:

                codigos.add(
                    codigo_unidade
                )

        if erros:

            for erro in erros[:100]:

                logger.error(
                    "❌ %s",
                    erro
                )

            raise ValueError(
                "Falha na validação dos dados."
            )

        logger.info(
            "✅ Validação concluída."
        )

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Reconstrói a tabela imp_013_unidades_avaliacao.
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                logger.info(
                    "🧹 Limpando %s...",
                    self.NOME_TABELA,
                )

                conn.execute(
                    f"""
                    DELETE FROM
                        {self.NOME_TABELA}
                    """
                )

                cursor = conn.cursor()

                for registro in (
                    dados_transformados
                ):

                    try:

                        cursor.execute(
                            f"""
                            INSERT INTO
                                {self.NOME_TABELA}
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
                            ),
                        )

                        inseridos += 1

                    except Exception as exc:

                        erros += 1

                        logger.error(
                            "❌ Erro inserindo %s: %s",
                            registro.get(
                                "codigoUnidade"
                            ),
                            exc,
                        )

                conn.commit()

        except Exception as exc:

            logger.exception(
                "❌ Erro durante reconstrução: %s",
                exc,
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
        Executa o importador completo pelo botão PLAY do VS Code.
        """

        logger.info(
            "=" * 100
        )

        logger.info(
            "INÍCIO imp_013_unidades_avaliacao_regras"
        )

        logger.info(
            "ANO=%s | PERIODOS=%s | FACULDADES=%s | SITUACAO=%s",
            ANO_VIGENTE,
            PERIODOS_VIGENTES,
            FACULDADES_INCLUIDAS,
            SITUACAO_TURMA_VALIDA,
        )

        logger.info(
            "=" * 100
        )

        # =====================================================================
        # 1. OBTÉM OFERTAS
        # =====================================================================

        turmas = (
            self.obter_turmas()
        )

        if not turmas:

            logger.warning(
                "⚠️ Nenhuma turma encontrada."
            )

            self._criar_tabela()

            return []

        # =====================================================================
        # 2. OBTÉM GRADES DAS OFERTAS
        # =====================================================================

        indice_grade = (
            self.obter_grade_das_ofertas(
                turmas
            )
        )

        # =====================================================================
        # 3. TRANSFORMA
        # =====================================================================

        dados = (
            self.transformar_dados(
                turmas,
                indice_grade,
            )
        )

        # =====================================================================
        # 4. VALIDA
        # =====================================================================

        self.validar_dados(
            dados
        )

        # =====================================================================
        # 5. GRAVA
        # =====================================================================

        resultado = (
            self.importar_para_qstione(
                dados
            )
        )

        # =====================================================================
        # RESUMO
        # =====================================================================

        logger.info(
            "=" * 100
        )

        logger.info(
            "RESUMO"
        )

        logger.info(
            "Turmas encontradas : %d",
            len(turmas),
        )

        logger.info(
            "Unidades geradas   : %d",
            len(dados),
        )

        logger.info(
            "Inseridos           : %d",
            resultado[
                "total_inseridos"
            ],
        )

        logger.info(
            "Erros               : %d",
            resultado[
                "total_erros"
            ],
        )

        logger.info(
            "=" * 100
        )

        return dados


# =============================================================================
# PLAY DO VS CODE
# =============================================================================

if __name__ == "__main__":

    ImportadorUnidadesAvaliacaoRegras().executar_importacao()