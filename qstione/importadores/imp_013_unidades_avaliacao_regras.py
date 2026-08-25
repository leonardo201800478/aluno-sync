
"""
qstione/importadores/imp_013_unidades_avaliacao_regras.py

Gerador independente de unidades de avaliação para o Qstione.

IMPORTANTE
----------
Este arquivo é uma alternativa ao:

    imp_013_unidades_avaliacao.py

O importador original NÃO deve ser alterado.

Este processo não utiliza LY_PROVA.

As avaliações são geradas diretamente em Python com base nos dados
acadêmicos atuais do Lyceum.

FILTROS
-------
Os filtros são definidos diretamente neste arquivo para permitir execução
pelo botão PLAY do VS Code:

    ANO
    PERIODOS
    FACULDADES

A faculdade é obtida de LY_CURSO.

CURRÍCULO
---------
O currículo é obtido através de LY_GRADE.

LY_GRADE possui:

    curriculo
    curso
    disciplina
    turno

O identificador lógico do currículo é construído como:

    curriculo-curso-turno

Exemplo:

    curriculo = 20152
    curso     = 014
    turno     = MV

    ID_CURRICULO = 20152-014-MV


REGRAS DE CURSO
---------------
O código do curso utilizado pelo Qstione é determinado por
MAPEAMENTO_CURSOS, proveniente do imp_002_disciplina.

Curso NULL ou vazio:

    999 - COMPARTILHADA

IMPORTANTE:
-----------
Cursos que não pertencem à faculdade filtrada não entram no processo,
pois o filtro de faculdade é aplicado em LY_CURSO.

Um curso não encontrado no MAPEAMENTO_CURSOS, mas que efetivamente
pertença à faculdade filtrada, é tratado como 999.


REGRAS DE AVALIAÇÃO
-------------------

GERAL
    AVD1
    AVD2
    SUBS

ENGENHARIAS
    S1P1
    S1P2
    S2P1
    S2P2

MEDICINA - CURRÍCULOS NOVOS
    PV1
    PV2
    PV3
    PV4
    SUBS
    PV1-D/A
    PV2-D/A
    PV3-D/A
    PV4-D/A
    SUBS-D/A
    SI

MEDICINA - CURRÍCULO ANTIGO
    F1
    F2
    F3
    S1
    S2
    SC
    PF
    PE
    SI

MEDICINA
--------
Currículos novos:

    20261-014-MV
    20251-014-MV
    20231-014-MV

Currículo antigo:

    20152-014-MV

Não existe mais regra baseada em categoria da disciplina.


EXECUÇÃO
--------
Executar diretamente pelo botão PLAY do VS Code.

Não são necessários argumentos de linha de comando.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ============================================================================
# PATH DO PROJETO
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
# IMPORTS DO PROJETO
# ============================================================================

from core.database import get_db_connection

from qstione.core.transformacoes import (
    converter_inteiro,
    gerar_codigo_disciplina_curso,
    truncar_texto,
)

from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


# ============================================================================
# LOG
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE EXECUÇÃO
# ============================================================================
#
# Estes valores são alterados diretamente no arquivo.
#
# O programa é executado pelo botão PLAY do VS Code.
#
# ============================================================================

ANO = 2026

PERIODOS = [
    "2",
]

FACULDADES = [
    "001",
]


# ============================================================================
# CURSOS DE ENGENHARIA
# ============================================================================
#
# Estes são os códigos UNIFICADOS do MAPEAMENTO_CURSOS.
#
# Portanto:
#
# 006 -> Engenharia Civil
# 020 -> Engenharia Civil
#
# ambos acabam em:
#
# 006
#
# ============================================================================

CURSOS_ENGENHARIA = {
    "006",  # Engenharia Civil
    "059",  # Engenharia de Produção
    "044",  # Engenharia Elétrica
    "017",  # Engenharia Mecânica
    "097",  # Engenharia da Computação
    "079",  # Engenharia
}


# ============================================================================
# MEDICINA
# ============================================================================

CODIGO_CURSO_MEDICINA = "014"


# ============================================================================
# CURRÍCULOS DE MEDICINA
# ============================================================================
#
# O identificador usado aqui é o ID lógico:
#
#     curriculo-curso-turno
#
# Exemplo:
#
#     20261-014-MV
#
# Não são utilizados os antigos IDs numéricos da consulta anterior.
#
# ============================================================================

CURRICULOS_MEDICINA_NOVOS = {
    "20261-014-MV",
    "20251-014-MV",
    "20231-014-MV",
}


CURRICULOS_MEDICINA_ANTIGOS = {
    "20152-014-MV",
}


# ============================================================================
# AVALIAÇÕES
# ============================================================================
#
# Estrutura:
#
#     (ordem, sufixo, nome)
#
# ============================================================================

AVALIACOES_GERAIS: Tuple[Tuple[int, str, str], ...] = (
    (1, "-AVD1", "Avaliação 1"),
    (2, "-AVD2", "Avaliação 2"),
    (3, "-SUBS", "Substitutiva"),
)


AVALIACOES_ENGENHARIA: Tuple[Tuple[int, str, str], ...] = (
    (1, "-S1P1", "Somativa 1 Parte 1"),
    (2, "-S1P2", "Somativa 1 Parte 2"),
    (3, "-S2P1", "Somativa 2 Parte 1"),
    (4, "-S2P2", "Somativa 2 Parte 2"),
)


AVALIACOES_MEDICINA_NOVO: Tuple[Tuple[int, str, str], ...] = (
    (1, "-PV1", "Prova 1"),
    (2, "-PV2", "Prova 2"),
    (3, "-PV3", "Prova 3"),
    (4, "-PV4", "Prova 4"),
    (5, "-SUBS", "Substitutiva"),
    (6, "-PV1-D/A", "Prova 1 Adap-Dep"),
    (7, "-PV2-D/A", "Prova 2 Adap-Dep"),
    (8, "-PV3-D/A", "Prova 3 Adap-Dep"),
    (9, "-PV4-D/A", "Prova 4 Adap-Dep"),
    (10, "-SUBS-D/A", "Substitutiva"),
    (11, "-SI", "Simulado"),
)


AVALIACOES_MEDICINA_ANTIGO: Tuple[Tuple[int, str, str], ...] = (
    (1, "-F1", "Formativa 1"),
    (2, "-F2", "Formativa 2"),
    (3, "-F3", "Formativa 3"),
    (4, "-S1", "Somativa 1"),
    (5, "-S2", "Somativa 2"),
    (6, "-SC", "Segunda Chamada"),
    (7, "-PF", "Prova Final"),
    (8, "-PE", "Prova Especial"),
    (9, "-SI", "Simulado"),
)


# ============================================================================
# IMPORTADOR
# ============================================================================


class ImportadorUnidadesAvaliacaoRegras:
    """
    Gera unidades de avaliação para o Qstione.

    O processo possui quatro etapas:

        1. Buscar turmas/disciplina.
        2. Resolver o currículo através da LY_GRADE.
        3. Aplicar as regras de avaliação.
        4. Reconstruir a tabela do Qstione.
    """

    NOME_TABELA = "imp_013_unidades_avaliacao"

    # ========================================================================
    # TABELA
    # ========================================================================

    def _tabela_existe(self) -> bool:
        """
        Verifica se a tabela de destino existe.

        Returns
        -------
        bool
            True se a tabela existir.
        """

        with get_db_connection(database_name="qstione") as conn:
            resultado = conn.execute(
                """
                SELECT 1
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = ?
                """,
                (self.NOME_TABELA,),
            ).fetchone()

        return resultado is not None

    # ========================================================================

    def _criar_tabela(self) -> None:
        """
        Cria a tabela de destino caso ela não exista.
        """

        if self._tabela_existe():
            return

        with get_db_connection(database_name="qstione") as conn:
            conn.execute(
                f"""
                CREATE TABLE {self.NOME_TABELA} (
                    codigoUnidade NVARCHAR(200) NOT NULL,
                    nomeUnidade NVARCHAR(64) NOT NULL,
                    codigoCurso NVARCHAR(30) NULL,
                    codigoDisciplina NVARCHAR(30) NULL,
                    ordemExibicao INT NOT NULL,
                    codigoAgrupamento NVARCHAR(200) NOT NULL,
                    data_criacao DATETIME2 DEFAULT GETDATE(),
                    data_atualizacao DATETIME2 DEFAULT GETDATE(),
                    PRIMARY KEY (codigoUnidade)
                )
                """
            )

            conn.commit()

        logger.info(
            "🆕 Tabela %s criada.",
            self.NOME_TABELA,
        )

    # ========================================================================
    # FILTROS
    # ========================================================================

    @staticmethod
    def _normalizar_lista_filtro(
        valores: Iterable[Any],
    ) -> List[str]:
        """
        Normaliza uma lista utilizada nos filtros.

        Parameters
        ----------
        valores:
            Lista de valores.

        Returns
        -------
        list[str]
            Valores convertidos para strings.
        """

        resultado: List[str] = []

        for valor in valores:
            if valor is None:
                continue

            valor = str(valor).strip()

            if valor:
                resultado.append(valor)

        return resultado

    # ========================================================================
    # BUSCA DE TURMAS
    # ========================================================================

    def obter_turmas(self) -> List[Dict[str, Any]]:
        """
        Busca as turmas/disciplina do período solicitado.

        A faculdade é obtida exclusivamente de LY_CURSO.

        Isso evita trazer cursos de outras faculdades que possuem códigos
        que não fazem parte do MAPEAMENTO_CURSOS utilizado neste projeto.

        Returns
        -------
        list[dict]
            Turmas encontradas.
        """

        ano = str(ANO).strip()

        periodos = self._normalizar_lista_filtro(
            PERIODOS
        )

        faculdades = self._normalizar_lista_filtro(
            FACULDADES
        )

        if not periodos:
            raise ValueError(
                "PERIODOS não pode estar vazio."
            )

        if not faculdades:
            raise ValueError(
                "FACULDADES não pode estar vazio."
            )

        placeholders_periodos = ",".join(
            "?" for _ in periodos
        )

        placeholders_faculdades = ",".join(
            "?" for _ in faculdades
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
            INNER JOIN LY_CURSO c
                ON c.curso = t.curso
            WHERE t.ano = ?
              AND t.semestre IN ({placeholders_periodos})
              AND c.faculdade IN ({placeholders_faculdades})
              AND t.disciplina IS NOT NULL
        """

        parametros = [
            ano,
            *periodos,
            *faculdades,
        ]

        logger.info(
            "🔎 Buscando turmas no Lyceum..."
        )

        logger.info(
            "   ANO=%s | PERIODOS=%s | FACULDADES=%s",
            ano,
            periodos,
            faculdades,
        )

        try:
            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                rows = conn.execute(
                    sql,
                    parametros,
                ).fetchall()

        except Exception as exc:
            logger.error(
                "❌ Erro ao consultar LY_TURMA/LY_CURSO: %s",
                exc,
            )
            raise

        colunas = [
            "ano",
            "semestre",
            "turma",
            "disciplina",
            "curso",
            "nome_curso",
            "faculdade",
        ]

        dados = [
            dict(zip(colunas, row))
            for row in rows
        ]

        logger.info(
            "📊 Turmas encontradas: %d",
            len(dados),
        )

        return dados

    # ========================================================================
    # BUSCA DA GRADE
    # ========================================================================

    def obter_grade(self) -> List[Dict[str, Any]]:
        """
        Busca a estrutura curricular da LY_GRADE.

        A LY_GRADE fornece:

            curriculo
            curso
            disciplina
            turno

        O identificador lógico do currículo será construído posteriormente
        como:

            curriculo-curso-turno

        Returns
        -------
        list[dict]
            Registros da grade curricular.
        """

        sql = """
            SELECT
                curriculo,
                curso,
                disciplina,
                turno
            FROM LY_GRADE
            WHERE curriculo IS NOT NULL
              AND curso IS NOT NULL
              AND disciplina IS NOT NULL
              AND turno IS NOT NULL
        """

        logger.info(
            "🔎 Carregando LY_GRADE..."
        )

        try:
            with get_db_connection(
                database_name="lyceum"
            ) as conn:

                rows = conn.execute(
                    sql
                ).fetchall()

        except Exception as exc:
            logger.error(
                "❌ Erro ao consultar LY_GRADE: %s",
                exc,
            )
            raise

        colunas = [
            "curriculo",
            "curso",
            "disciplina",
            "turno",
        ]

        dados = [
            dict(zip(colunas, row))
            for row in rows
        ]

        logger.info(
            "📊 Registros de LY_GRADE carregados: %d",
            len(dados),
        )

        return dados

    # ========================================================================
    # ID DO CURRÍCULO
    # ========================================================================

    @staticmethod
    def gerar_id_curriculo(
        curriculo: Any,
        curso: Any,
        turno: Any,
    ) -> str:
        """
        Gera o identificador lógico do currículo.

        Formato:

            curriculo-curso-turno

        Exemplo:

            20152-014-MV

        Parameters
        ----------
        curriculo:
            Código do currículo.

        curso:
            Código do curso.

        turno:
            Turno.

        Returns
        -------
        str
            Identificador lógico do currículo.
        """

        curriculo = str(
            curriculo or ""
        ).strip()

        curso = str(
            curso or ""
        ).strip()

        turno = str(
            turno or ""
        ).strip()

        if not curriculo or not curso or not turno:
            return ""

        return (
            f"{curriculo}-{curso}-{turno}"
        )

    # ========================================================================
    # ÍNDICE DA GRADE
    # ========================================================================

    def construir_indice_grade(
        self,
        grade: List[Dict[str, Any]],
    ) -> Dict[Tuple[str, str], Set[str]]:
        """
        Constrói um índice da LY_GRADE.

        A chave do índice é:

            (curso, disciplina)

        O valor é o conjunto de IDs de currículo encontrados.

        Exemplo:

            (
                "014",
                "DISC001"
            )
            ->
            {
                "20261-014-MV",
                "20251-014-MV"
            }

        Parameters
        ----------
        grade:
            Registros da LY_GRADE.

        Returns
        -------
        dict
            Índice de currículo por curso/disciplina.
        """

        indice: Dict[
            Tuple[str, str],
            Set[str]
        ] = {}

        for registro in grade:

            curso = str(
                registro.get("curso") or ""
            ).strip()

            disciplina = str(
                registro.get("disciplina") or ""
            ).strip()

            curriculo = str(
                registro.get("curriculo") or ""
            ).strip()

            turno = str(
                registro.get("turno") or ""
            ).strip()

            if not curso:
                continue

            if not disciplina:
                continue

            id_curriculo = self.gerar_id_curriculo(
                curriculo,
                curso,
                turno,
            )

            if not id_curriculo:
                continue

            chave = (
                curso,
                disciplina,
            )

            indice.setdefault(
                chave,
                set(),
            ).add(
                id_curriculo
            )

        logger.info(
            "📚 Combinações curso/disciplina indexadas: %d",
            len(indice),
        )

        return indice

    # ========================================================================
    # CURSO
    # ========================================================================

    @staticmethod
    def normalizar_curso(
        curso: Any,
    ) -> Tuple[str, str]:
        """
        Converte o curso original para o curso unificado.

        Regras:

            NULL/vazio
                -> 999 / COMPARTILHADA

            curso encontrado no mapeamento
                -> código/nome do mapeamento

            curso não encontrado
                -> 999 / COMPARTILHADA

        Parameters
        ----------
        curso:
            Código original.

        Returns
        -------
        tuple[str, str]
            Código e nome do curso unificado.
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

        mapeamento = MAPEAMENTO_CURSOS.get(
            curso
        )

        if mapeamento is None:

            logger.warning(
                "⚠️ Curso %s pertence à faculdade filtrada, "
                "mas não está no MAPEAMENTO_CURSOS. "
                "Usando 999 - COMPARTILHADA.",
                curso,
            )

            return (
                "999",
                "COMPARTILHADA",
            )

        codigo, nome = mapeamento

        return (
            str(codigo).strip(),
            str(nome).strip(),
        )

    # ========================================================================
    # RESOLUÇÃO DO CURRÍCULO
    # ========================================================================

    @staticmethod
    def resolver_curriculos(
        curso_original: Any,
        disciplina: Any,
        indice_grade: Dict[Tuple[str, str], Set[str]],
    ) -> Set[str]:
        """
        Localiza os currículos da disciplina através da LY_GRADE.

        Parameters
        ----------
        curso_original:
            Código original do curso.

        disciplina:
            Código da disciplina.

        indice_grade:
            Índice construído a partir da LY_GRADE.

        Returns
        -------
        set[str]
            IDs lógicos dos currículos.
        """

        curso = str(
            curso_original or ""
        ).strip()

        disciplina = str(
            disciplina or ""
        ).strip()

        if not curso or not disciplina:
            return set()

        return indice_grade.get(
            (
                curso,
                disciplina,
            ),
            set(),
        )

    # ========================================================================
    # REGRA DE AVALIAÇÃO
    # ========================================================================

    @staticmethod
    def obter_avaliacoes(
        codigo_curso: str,
        id_curriculo: str,
    ) -> Tuple[
        str,
        Tuple[Tuple[int, str, str], ...]
    ]:
        """
        Determina a regra de avaliação.

        Parameters
        ----------
        codigo_curso:
            Código unificado do curso.

        id_curriculo:
            Identificador lógico do currículo.

        Returns
        -------
        tuple
            Nome da regra e avaliações correspondentes.
        """

        codigo_curso = str(
            codigo_curso or ""
        ).strip()

        id_curriculo = str(
            id_curriculo or ""
        ).strip()

        # --------------------------------------------------------------------
        # MEDICINA
        # --------------------------------------------------------------------

        if codigo_curso == CODIGO_CURSO_MEDICINA:

            if id_curriculo in CURRICULOS_MEDICINA_NOVOS:
                return (
                    "MEDICINA_NOVO",
                    AVALIACOES_MEDICINA_NOVO,
                )

            if id_curriculo in CURRICULOS_MEDICINA_ANTIGOS:
                return (
                    "MEDICINA_ANTIGO",
                    AVALIACOES_MEDICINA_ANTIGO,
                )

            # Um currículo de Medicina que não esteja cadastrado não deve
            # receber silenciosamente a regra de Medicina nova ou antiga.
            #
            # Neste caso usamos a regra geral e registramos o problema.
            logger.warning(
                "⚠️ Currículo de Medicina não cadastrado: %s",
                id_curriculo or "<NULL>",
            )

            return (
                "GERAL_MEDICINA_CURRICULO_NAO_MAPEADO",
                AVALIACOES_GERAIS,
            )

        # --------------------------------------------------------------------
        # ENGENHARIA
        # --------------------------------------------------------------------

        if codigo_curso in CURSOS_ENGENHARIA:

            return (
                "ENGENHARIA",
                AVALIACOES_ENGENHARIA,
            )

        # --------------------------------------------------------------------
        # GERAL
        # --------------------------------------------------------------------

        return (
            "GERAL",
            AVALIACOES_GERAIS,
        )

    # ========================================================================
    # CÓDIGO DA DISCIPLINA
    # ========================================================================

    @staticmethod
    def gerar_codigo_disciplina(
        disciplina: Any,
        codigo_curso: str,
        nome_curso: str,
    ) -> str:
        """
        Gera o código da disciplina utilizando exatamente a função usada
        pelo imp_002_disciplina.

        Parameters
        ----------
        disciplina:
            Código original da disciplina.

        codigo_curso:
            Curso unificado.

        nome_curso:
            Nome unificado.

        Returns
        -------
        str
            Código da disciplina.
        """

        disciplina = str(
            disciplina or ""
        ).strip()

        if not disciplina:
            return ""

        codigo = gerar_codigo_disciplina_curso(
            disciplina,
            nome_curso,
            codigo_curso,
        )

        return truncar_texto(
            codigo,
            30,
        )

    # ========================================================================
    # TRANSFORMAÇÃO
    # ========================================================================

    def transformar_dados(
        self,
        turmas: List[Dict[str, Any]],
        indice_grade: Dict[
            Tuple[str, str],
            Set[str]
        ],
    ) -> List[Dict[str, Any]]:
        """
        Gera as unidades de avaliação.

        Uma disciplina pode estar associada a mais de um currículo na
        LY_GRADE. Cada currículo é avaliado separadamente.

        A duplicidade final é controlada por codigoUnidade, pois este é
        o campo que possui PRIMARY KEY no Qstione.

        Parameters
        ----------
        turmas:
            Turmas encontradas no período/faculdade.

        indice_grade:
            Índice curricular.

        Returns
        -------
        list[dict]
            Registros prontos para gravação.
        """

        dados: List[Dict[str, Any]] = []

        codigos_unidade: Set[str] = set()

        contador_regras = Counter()
        contador_cursos = Counter()
        contador_curriculos = Counter()

        disciplinas_sem_grade = Counter()

        # --------------------------------------------------------------------
        # PROCESSAMENTO
        # --------------------------------------------------------------------

        for item in turmas:

            disciplina = str(
                item.get("disciplina") or ""
            ).strip()

            if not disciplina:
                continue

            curso_original = item.get(
                "curso"
            )

            codigo_curso, nome_curso = (
                self.normalizar_curso(
                    curso_original
                )
            )

            curriculos = self.resolver_curriculos(
                curso_original,
                disciplina,
                indice_grade,
            )

            # ----------------------------------------------------------------
            # Não encontramos currículo.
            #
            # Para cursos diferentes de Medicina, a ausência de currículo
            # não impede a regra geral/engenharia, porque essas regras não
            # dependem do currículo.
            #
            # Para Medicina, sem currículo não é possível decidir entre
            # antigo e novo.
            # ----------------------------------------------------------------

            if not curriculos:

                if codigo_curso == CODIGO_CURSO_MEDICINA:

                    logger.warning(
                        "⚠️ Medicina sem currículo na LY_GRADE: "
                        "disciplina=%s | curso=%s",
                        disciplina,
                        curso_original,
                    )

                    # Não gerar avaliação de Medicina sem saber qual
                    # currículo deve ser aplicado.
                    disciplinas_sem_grade[
                        (
                            codigo_curso,
                            disciplina,
                        )
                    ] += 1

                    continue

                # ------------------------------------------------------------
                # Cursos não-Medicina.
                #
                # Criamos um identificador vazio somente para a decisão da
                # regra. O ID não é gravado na tabela.
                # ------------------------------------------------------------

                curriculos = {""}

            # ----------------------------------------------------------------
            # PROCESSA CADA CURRÍCULO
            # ----------------------------------------------------------------

            for id_curriculo in sorted(
                curriculos
            ):

                codigo_disciplina = (
                    self.gerar_codigo_disciplina(
                        disciplina,
                        codigo_curso,
                        nome_curso,
                    )
                )

                if not codigo_disciplina:
                    continue

                nome_regra, avaliacoes = (
                    self.obter_avaliacoes(
                        codigo_curso,
                        id_curriculo,
                    )
                )

                contador_regras[
                    nome_regra
                ] += 1

                contador_cursos[
                    codigo_curso
                ] += 1

                contador_curriculos[
                    id_curriculo or "<SEM_CURRICULO>"
                ] += 1

                # ------------------------------------------------------------
                # GERA CADA AVALIAÇÃO
                # ------------------------------------------------------------

                for (
                    ordem,
                    sufixo,
                    nome_unidade,
                ) in avaliacoes:

                    codigo_unidade = truncar_texto(
                        f"{codigo_disciplina}{sufixo}",
                        200,
                    )

                    # --------------------------------------------------------
                    # DEDUPLICAÇÃO FINAL
                    # --------------------------------------------------------
                    #
                    # A tabela possui PRIMARY KEY em codigoUnidade.
                    #
                    # Portanto, mesmo que a mesma disciplina apareça em
                    # mais de uma turma ou mais de uma associação curricular,
                    # não gravaremos a mesma unidade duas vezes.
                    #
                    # --------------------------------------------------------

                    if codigo_unidade in codigos_unidade:
                        continue

                    codigos_unidade.add(
                        codigo_unidade
                    )

                    dados.append(
                        {
                            "codigoUnidade": codigo_unidade,
                            "nomeUnidade": truncar_texto(
                                nome_unidade,
                                64,
                            ),
                            "codigoCurso": truncar_texto(
                                codigo_curso,
                                30,
                            ),
                            "codigoDisciplina": truncar_texto(
                                codigo_disciplina,
                                30,
                            ),
                            "ordemExibicao": (
                                converter_inteiro(
                                    ordem
                                ) or 0
                            ),
                            "codigoAgrupamento": (
                                codigo_unidade
                            ),
                            "regra": nome_regra,
                            "id_curriculo": (
                                id_curriculo
                            ),
                        }
                    )

        # --------------------------------------------------------------------
        # LOGS
        # --------------------------------------------------------------------

        logger.info(
            "✅ Unidades de avaliação geradas: %d",
            len(dados),
        )

        logger.info(
            "📋 Distribuição por regra:"
        )

        for regra, quantidade in sorted(
            contador_regras.items()
        ):
            logger.info(
                "   %-45s %d disciplinas",
                regra,
                quantidade,
            )

        logger.info(
            "📚 Distribuição por curso:"
        )

        for curso, quantidade in sorted(
            contador_cursos.items()
        ):
            logger.info(
                "   curso=%s -> %d ocorrências",
                curso,
                quantidade,
            )

        if disciplinas_sem_grade:

            logger.warning(
                "⚠️ Disciplinas de Medicina sem currículo: %d",
                len(disciplinas_sem_grade),
            )

            for (
                codigo_curso,
                disciplina,
            ), quantidade in sorted(
                disciplinas_sem_grade.items()
            ):
                logger.warning(
                    "   curso=%s | disciplina=%s | ocorrências=%d",
                    codigo_curso,
                    disciplina,
                    quantidade,
                )

        return dados

    # ========================================================================
    # VALIDAÇÃO
    # ========================================================================

    @staticmethod
    def validar_dados(
        dados: List[Dict[str, Any]],
    ) -> None:
        """
        Valida os registros antes da gravação.

        Verifica:

            codigoUnidade
            codigoDisciplina
            codigoCurso
            duplicidade de codigoUnidade

        Parameters
        ----------
        dados:
            Registros transformados.

        Raises
        ------
        ValueError
            Quando algum registro inválido for encontrado.
        """

        erros: List[str] = []

        codigos_unidade: Set[str] = set()

        for indice, registro in enumerate(
            dados,
            start=1,
        ):

            codigo_unidade = registro.get(
                "codigoUnidade"
            )

            codigo_disciplina = registro.get(
                "codigoDisciplina"
            )

            codigo_curso = registro.get(
                "codigoCurso"
            )

            if not codigo_unidade:
                erros.append(
                    f"Registro {indice}: "
                    f"codigoUnidade vazio"
                )

            if not codigo_disciplina:
                erros.append(
                    f"Registro {indice}: "
                    f"codigoDisciplina vazio"
                )

            if not codigo_curso:
                erros.append(
                    f"Registro {indice}: "
                    f"codigoCurso vazio"
                )

            if (
                codigo_unidade
                and codigo_unidade in codigos_unidade
            ):
                erros.append(
                    f"codigoUnidade duplicado: "
                    f"{codigo_unidade}"
                )

            if codigo_unidade:
                codigos_unidade.add(
                    codigo_unidade
                )

        if erros:

            logger.error(
                "❌ Validação encontrou %d erro(s).",
                len(erros),
            )

            for erro in erros[:30]:
                logger.error(
                    "   %s",
                    erro,
                )

            if len(erros) > 30:
                logger.error(
                    "   ... e mais %d erro(s).",
                    len(erros) - 30,
                )

            raise ValueError(
                "Os dados transformados falharam na validação."
            )

        logger.info(
            "✅ Validação concluída sem erros."
        )

    # ========================================================================
    # IMPORTAÇÃO
    # ========================================================================

    def importar_para_qstione(
        self,
        dados_transformados: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Reconstrói a tabela de unidades de avaliação.

        A tabela é limpa antes da carga.

        Parameters
        ----------
        dados_transformados:
            Registros prontos para inserção.

        Returns
        -------
        dict
            Resultado da carga.
        """

        self._criar_tabela()

        inseridos = 0
        erros = 0

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                logger.info(
                    "🧹 Limpando tabela %s...",
                    self.NOME_TABELA,
                )

                conn.execute(
                    f"""
                    DELETE FROM {self.NOME_TABELA}
                    """
                )

                cursor = conn.cursor()

                for registro in dados_transformados:

                    try:

                        cursor.execute(
                            f"""
                            INSERT INTO {self.NOME_TABELA}
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
                            "❌ Erro ao inserir %s: %s",
                            registro.get(
                                "codigoUnidade"
                            ),
                            exc,
                        )

                conn.commit()

        except Exception as exc:

            logger.error(
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

    # ========================================================================
    # EXECUÇÃO
    # ========================================================================

    def executar_importacao(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Executa todo o processo.

        Returns
        -------
        list[dict]
            Registros gerados.
        """

        logger.info(
            "=" * 100
        )

        logger.info(
            "INÍCIO imp_013_unidades_avaliacao_regras"
        )

        logger.info(
            "ANO=%s | PERIODOS=%s | FACULDADES=%s",
            ANO,
            PERIODOS,
            FACULDADES,
        )

        logger.info(
            "=" * 100
        )

        # --------------------------------------------------------------------
        # 1. TURMAS
        # --------------------------------------------------------------------

        turmas = self.obter_turmas()

        # --------------------------------------------------------------------
        # 2. GRADE CURRICULAR
        # --------------------------------------------------------------------

        grade = self.obter_grade()

        # --------------------------------------------------------------------
        # 3. ÍNDICE DA GRADE
        # --------------------------------------------------------------------

        indice_grade = (
            self.construir_indice_grade(
                grade
            )
        )

        # --------------------------------------------------------------------
        # 4. GERAÇÃO
        # --------------------------------------------------------------------

        transformados = (
            self.transformar_dados(
                turmas,
                indice_grade,
            )
        )

        # --------------------------------------------------------------------
        # 5. VALIDAÇÃO
        # --------------------------------------------------------------------

        self.validar_dados(
            transformados
        )

        # --------------------------------------------------------------------
        # 6. GRAVAÇÃO
        # --------------------------------------------------------------------

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        # --------------------------------------------------------------------
        # 7. RESUMO
        # --------------------------------------------------------------------

        logger.info(
            "=" * 100
        )

        logger.info(
            "FIM imp_013_unidades_avaliacao_regras"
        )

        logger.info(
            "Processados : %d",
            resultado[
                "total_processados"
            ],
        )

        logger.info(
            "Inseridos   : %d",
            resultado[
                "total_inseridos"
            ],
        )

        logger.info(
            "Atualizados : %d",
            resultado[
                "total_atualizados"
            ],
        )

        logger.info(
            "Erros       : %d",
            resultado[
                "total_erros"
            ],
        )

        logger.info(
            "=" * 100
        )

        return transformados


# ============================================================================
# EXECUÇÃO DIRETA PELO PLAY DO VS CODE
# ============================================================================

if __name__ == "__main__":
    ImportadorUnidadesAvaliacaoRegras().executar_importacao()