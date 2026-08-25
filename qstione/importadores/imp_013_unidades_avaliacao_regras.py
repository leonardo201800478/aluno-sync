"""
qstione/importadores/imp_013_unidades_avaliacao_regras.py

Gerador de unidades de avaliação para o Qstione.

IMPORTANTE
----------
Este importador é uma alternativa ao:

    imp_013_unidades_avaliacao.py

O importador original NÃO deve ser alterado.

Este novo processo NÃO utiliza LY_PROVA.
As avaliações são geradas diretamente em Python com base em:

    - ano;
    - período/semestre;
    - faculdade;
    - curso;
    - currículo;
    - disciplina.

Regras:

1. CURSO GERAL
   AVD1
   AVD2
   SUBS

2. ENGENHARIAS
   S1P1
   S1P2
   S2P1
   S2P2

3. MEDICINA - CURRÍCULOS NOVOS
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

4. MEDICINA - CURRÍCULO ANTIGO/MODULAR
   F1
   F2
   F3
   S1
   S2
   SC
   PF
   PE
   SI

5. CURSO NULL / VAZIO / NÃO MAPEADO
   -> 999 - COMPARTILHADA
   -> utiliza a regra geral.

Execução:
    Usar diretamente o botão PLAY do VS Code.

Não requer argumentos de linha de comando.
"""

from __future__ import annotations

import logging
import os
import sys
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
    truncar_texto,
    converter_inteiro,
    gerar_codigo_disciplina_curso,
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
# Ajuste estes valores antes de executar pelo PLAY do VS CODE.
#
# Exemplo:
#
# ANO = 2026
# PERIODOS = ["2"]
# FACULDADES = ["001"]
#
# Também é possível utilizar mais de um período/faculdade:
#
# PERIODOS = ["1", "2"]
# FACULDADES = ["001", "002"]
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
# CURSOS COM REGRAS ESPECIAIS
# ============================================================================

# Cursos unificados de Engenharia.
#
# O curso original NÃO deve ser utilizado aqui.
# Sempre trabalhamos com o código resultante do MAPEAMENTO_CURSOS.

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


# Currículos atuais de Medicina classificados como NOVOS.

CURRICULOS_MEDICINA_NOVOS = {
    "4000002649",  # 2026.1
    "4000002550",  # 2025.1
    "4000002232",  # 2023.1
}


# Currículo antigo/modular de Medicina.

CURRICULOS_MEDICINA_ANTIGOS = {
    "4000001885",  # 2015.2
}


# ============================================================================
# AVALIAÇÕES
# ============================================================================
#
# Estrutura:
#
#     (ordem, sufixo, nome)
#
# O sufixo será concatenado ao codigoDisciplina.
#
# Exemplo:
#
#     codigoDisciplina = MAT001-ADM
#     sufixo = -AVD1
#
#     codigoUnidade = MAT001-ADM-AVD1
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
    Gera as unidades de avaliação para o Qstione.

    O processo é dividido em quatro etapas principais:

    1. Busca dos dados acadêmicos atuais.
    2. Normalização de curso/currículo/disciplina.
    3. Aplicação das regras de avaliação.
    4. Reconstrução da tabela no banco Qstione.
    """

    # ----------------------------------------------------------------------
    # TABELA
    # ----------------------------------------------------------------------

    NOME_TABELA = "imp_013_unidades_avaliacao"

    # ----------------------------------------------------------------------
    # CONEXÃO / TABELA
    # ----------------------------------------------------------------------

    def _tabela_existe(self) -> bool:
        """
        Verifica se a tabela de unidades de avaliação existe.

        Returns
        -------
        bool
            True quando a tabela existe.
        """

        with get_db_connection(database_name="qstione") as conn:
            return (
                conn.execute(
                    """
                    SELECT 1
                    FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ?
                    """,
                    (self.NOME_TABELA,),
                ).fetchone()
                is not None
            )

    def _criar_tabela(self) -> None:
        """
        Cria a tabela de destino caso ela ainda não exista.
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

    # ----------------------------------------------------------------------
    # FILTROS
    # ----------------------------------------------------------------------

    @staticmethod
    def _normalizar_lista_filtro(
        valores: Iterable[Any],
    ) -> List[str]:
        """
        Normaliza uma lista de filtros.

        Parameters
        ----------
        valores:
            Valores de ano, período ou faculdade.

        Returns
        -------
        list[str]
            Valores convertidos para strings e sem espaços.
        """

        resultado = []

        for valor in valores:
            if valor is None:
                continue

            valor = str(valor).strip()

            if valor:
                resultado.append(valor)

        return resultado

    # ----------------------------------------------------------------------
    # BUSCA DOS DADOS
    # ----------------------------------------------------------------------

    def obter_dados_lyceum(self) -> List[Dict[str, Any]]:
        """
        Busca as disciplinas/turmas que participarão da geração.

        IMPORTANTE:
        Não consulta LY_PROVA.

        As avaliações serão geradas posteriormente pelo Python.

        Os filtros ANO, PERIODOS e FACULDADES são aplicados diretamente
        na consulta.

        Returns
        -------
        list[dict]
            Registros acadêmicos utilizados para geração.
        """

        ano = str(ANO).strip()

        periodos = self._normalizar_lista_filtro(PERIODOS)
        faculdades = self._normalizar_lista_filtro(FACULDADES)

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

        # ------------------------------------------------------------------
        # IMPORTANTE
        #
        # A estrutura abaixo utiliza LY_TURMA como origem.
        #
        # Caso a instalação atual possua um campo de currículo diferente
        # do utilizado abaixo, este é o único ponto que deverá ser ajustado.
        #
        # A regra do restante do importador permanece independente da
        # origem dos dados.
        # ------------------------------------------------------------------

        sql = f"""
            SELECT DISTINCT
                t.ano,
                t.semestre,
                t.turma,
                t.disciplina,
                t.curso,
                t.curriculo,
                t.faculdade,
                c.nome AS nome_curso
            FROM LY_TURMA t
            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso
            WHERE t.ano = ?
              AND t.semestre IN ({placeholders_periodos})
              AND t.faculdade IN ({placeholders_faculdades})
              AND t.disciplina IS NOT NULL
        """

        parametros = [
            ano,
            *periodos,
            *faculdades,
        ]

        logger.info(
            "🔎 Buscando dados acadêmicos..."
        )

        logger.info(
            "   ANO=%s | PERIODOS=%s | FACULDADES=%s",
            ano,
            periodos,
            faculdades,
        )

        try:
            with get_db_connection(database_name="lyceum") as conn:
                rows = conn.execute(
                    sql,
                    parametros,
                ).fetchall()

        except Exception as exc:
            logger.error(
                "❌ Erro ao consultar LY_TURMA: %s",
                exc,
            )
            raise

        colunas = [
            "ano",
            "semestre",
            "turma",
            "disciplina",
            "curso",
            "curriculo",
            "faculdade",
            "nome_curso",
        ]

        dados = [
            dict(zip(colunas, row))
            for row in rows
        ]

        logger.info(
            "📊 Registros acadêmicos encontrados: %d",
            len(dados),
        )

        return dados

    # ----------------------------------------------------------------------
    # CURSO
    # ----------------------------------------------------------------------

    @staticmethod
    def normalizar_curso(
        curso: Any,
    ) -> Tuple[str, str]:
        """
        Converte o código original do curso para o código unificado.

        Regras
        ------
        1. NULL -> 999 / COMPARTILHADA
        2. vazio -> 999 / COMPARTILHADA
        3. curso conhecido -> MAPEAMENTO_CURSOS
        4. curso desconhecido -> 999 / COMPARTILHADA

        Parameters
        ----------
        curso:
            Código original do curso.

        Returns
        -------
        tuple[str, str]
            (codigoCurso, nomeCurso)
        """

        if curso is None:
            return "999", "COMPARTILHADA"

        curso = str(curso).strip()

        if not curso:
            return "999", "COMPARTILHADA"

        mapeamento = MAPEAMENTO_CURSOS.get(curso)

        if mapeamento is None:
            logger.warning(
                "⚠️ Curso %s não encontrado em "
                "MAPEAMENTO_CURSOS. Usando 999 - COMPARTILHADA.",
                curso,
            )

            return "999", "COMPARTILHADA"

        codigo, nome = mapeamento

        return (
            str(codigo).strip(),
            str(nome).strip(),
        )

    # ----------------------------------------------------------------------
    # CURRÍCULO
    # ----------------------------------------------------------------------

    @staticmethod
    def normalizar_curriculo(
        curriculo: Any,
    ) -> str:
        """
        Normaliza o código do currículo.

        Parameters
        ----------
        curriculo:
            Código do currículo.

        Returns
        -------
        str
            Código do currículo normalizado.
        """

        if curriculo is None:
            return ""

        return str(curriculo).strip()

    # ----------------------------------------------------------------------
    # REGRA DE AVALIAÇÃO
    # ----------------------------------------------------------------------

    @staticmethod
    def obter_avaliacoes(
        codigo_curso: str,
        codigo_curriculo: str,
    ) -> Tuple[str, Tuple[Tuple[int, str, str], ...]]:
        """
        Determina qual conjunto de avaliações deve ser aplicado.

        Parameters
        ----------
        codigo_curso:
            Código unificado do curso.

        codigo_curriculo:
            Código atual do currículo.

        Returns
        -------
        tuple
            Nome da regra e conjunto de avaliações.

        Regras
        ------
        Medicina:
            currículo novo  -> AVALIACOES_MEDICINA_NOVO
            currículo antigo -> AVALIACOES_MEDICINA_ANTIGO

        Engenharia:
            AVALIACOES_ENGENHARIA

        Demais:
            AVALIACOES_GERAIS
        """

        codigo_curso = str(
            codigo_curso or ""
        ).strip()

        codigo_curriculo = str(
            codigo_curriculo or ""
        ).strip()

        # --------------------------------------------------------------
        # MEDICINA
        # --------------------------------------------------------------

        if codigo_curso == CODIGO_CURSO_MEDICINA:

            if codigo_curriculo in CURRICULOS_MEDICINA_NOVOS:
                return (
                    "MEDICINA_NOVO",
                    AVALIACOES_MEDICINA_NOVO,
                )

            if codigo_curriculo in CURRICULOS_MEDICINA_ANTIGOS:
                return (
                    "MEDICINA_ANTIGO",
                    AVALIACOES_MEDICINA_ANTIGO,
                )

            # ----------------------------------------------------------
            # Currículo de Medicina ainda não cadastrado.
            #
            # Não devemos silenciosamente classificá-lo como novo ou
            # antigo.
            # ----------------------------------------------------------

            logger.warning(
                "⚠️ Currículo de Medicina não mapeado: %s",
                codigo_curriculo or "<NULL>",
            )

            # Por segurança, usamos a regra geral.
            #
            # Isso evita criar automaticamente 11 avaliações de Medicina
            # para um currículo desconhecido.
            return (
                "GERAL_CURRICULO_MEDICINA_NAO_MAPEADO",
                AVALIACOES_GERAIS,
            )

        # --------------------------------------------------------------
        # ENGENHARIA
        # --------------------------------------------------------------

        if codigo_curso in CURSOS_ENGENHARIA:
            return (
                "ENGENHARIA",
                AVALIACOES_ENGENHARIA,
            )

        # --------------------------------------------------------------
        # GERAL
        # --------------------------------------------------------------

        return (
            "GERAL",
            AVALIACOES_GERAIS,
        )

    # ----------------------------------------------------------------------
    # CÓDIGO DA DISCIPLINA
    # ----------------------------------------------------------------------

    @staticmethod
    def gerar_codigo_disciplina(
        disciplina: Any,
        codigo_curso: str,
        nome_curso: str,
    ) -> str:
        """
        Gera o código da disciplina utilizando a mesma função utilizada
        pelo imp_002_disciplina.

        Parameters
        ----------
        disciplina:
            Código da disciplina.

        codigo_curso:
            Código unificado do curso.

        nome_curso:
            Nome do curso unificado.

        Returns
        -------
        str
            Código da disciplina compatível com o Qstione.
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

    # ----------------------------------------------------------------------
    # GERAÇÃO DAS UNIDADES
    # ----------------------------------------------------------------------

    def transformar_dados(
        self,
        dados_lyceum: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Transforma as disciplinas acadêmicas em unidades de avaliação.

        Cada disciplina gera uma quantidade de unidades determinada
        pela regra correspondente ao curso/currículo.

        Parameters
        ----------
        dados_lyceum:
            Registros acadêmicos.

        Returns
        -------
        list[dict]
            Unidades prontas para inserção no Qstione.
        """

        dados: List[Dict[str, Any]] = []

        contador_regras = Counter()
        contador_cursos = Counter()
        contador_curriculos = Counter()

        # ------------------------------------------------------------------
        # Evita que a mesma disciplina apareça várias vezes devido a
        # múltiplas turmas.
        #
        # A avaliação é da disciplina dentro do curso/currículo, não de
        # cada turma individualmente.
        # ------------------------------------------------------------------

        disciplinas_processadas = set()

        for item in dados_lyceum:

            # --------------------------------------------------------------
            # DADOS BÁSICOS
            # --------------------------------------------------------------

            disciplina = str(
                item.get("disciplina") or ""
            ).strip()

            if not disciplina:
                continue

            curso_original = item.get("curso")

            codigo_curso, nome_curso = (
                self.normalizar_curso(
                    curso_original
                )
            )

            codigo_curriculo = (
                self.normalizar_curriculo(
                    item.get("curriculo")
                )
            )

            # --------------------------------------------------------------
            # CHAVE DE DEDUPLICAÇÃO
            # --------------------------------------------------------------

            chave = (
                codigo_curso,
                codigo_curriculo,
                disciplina,
            )

            if chave in disciplinas_processadas:
                continue

            disciplinas_processadas.add(chave)

            # --------------------------------------------------------------
            # CÓDIGO DA DISCIPLINA
            # --------------------------------------------------------------

            codigo_disciplina = (
                self.gerar_codigo_disciplina(
                    disciplina,
                    codigo_curso,
                    nome_curso,
                )
            )

            if not codigo_disciplina:
                logger.warning(
                    "⚠️ Disciplina sem código gerado: "
                    "disciplina=%s | curso=%s | currículo=%s",
                    disciplina,
                    codigo_curso,
                    codigo_curriculo or "<NULL>",
                )
                continue

            # --------------------------------------------------------------
            # REGRA
            # --------------------------------------------------------------

            nome_regra, avaliacoes = (
                self.obter_avaliacoes(
                    codigo_curso,
                    codigo_curriculo,
                )
            )

            contador_regras[nome_regra] += 1
            contador_cursos[codigo_curso] += 1
            contador_curriculos[
                codigo_curriculo or "<NULL>"
            ] += 1

            # --------------------------------------------------------------
            # GERAÇÃO DAS AVALIAÇÕES
            # --------------------------------------------------------------

            for ordem, sufixo, nome_unidade in avaliacoes:

                codigo_unidade = truncar_texto(
                    f"{codigo_disciplina}{sufixo}",
                    200,
                )

                codigo_agrupamento = codigo_unidade

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
                        "ordemExibicao": converter_inteiro(
                            ordem
                        ) or 0,
                        "codigoAgrupamento": codigo_agrupamento,
                        "regra": nome_regra,
                    }
                )

        # ------------------------------------------------------------------
        # LOGS
        # ------------------------------------------------------------------

        logger.info(
            "✅ Disciplinas únicas processadas: %d",
            len(disciplinas_processadas),
        )

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
                "   %-40s %d disciplinas",
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
                "   curso=%s -> %d disciplinas",
                curso,
                quantidade,
            )

        return dados

    # ----------------------------------------------------------------------
    # VALIDAÇÃO
    # ----------------------------------------------------------------------

    @staticmethod
    def validar_dados(
        dados: List[Dict[str, Any]],
    ) -> None:
        """
        Executa validações básicas antes da gravação.

        A validação impede que registros com campos fundamentais vazios
        sejam enviados ao banco.

        Parameters
        ----------
        dados:
            Registros transformados.
        """

        erros = []

        codigos_unidade = set()

        for indice, registro in enumerate(dados, start=1):

            codigo_unidade = (
                registro.get("codigoUnidade")
            )

            codigo_disciplina = (
                registro.get("codigoDisciplina")
            )

            codigo_curso = (
                registro.get("codigoCurso")
            )

            if not codigo_unidade:
                erros.append(
                    f"Registro {indice}: codigoUnidade vazio"
                )

            if not codigo_disciplina:
                erros.append(
                    f"Registro {indice}: codigoDisciplina vazio"
                )

            if not codigo_curso:
                erros.append(
                    f"Registro {indice}: codigoCurso vazio"
                )

            if codigo_unidade in codigos_unidade:
                erros.append(
                    f"codigoUnidade duplicado: "
                    f"{codigo_unidade}"
                )

            codigos_unidade.add(codigo_unidade)

        if erros:
            logger.error(
                "❌ Validação encontrou %d erro(s).",
                len(erros),
            )

            for erro in erros[:20]:
                logger.error(
                    "   %s",
                    erro,
                )

            if len(erros) > 20:
                logger.error(
                    "   ... e mais %d erro(s).",
                    len(erros) - 20,
                )

            raise ValueError(
                "Os dados transformados falharam na validação."
            )

        logger.info(
            "✅ Validação concluída sem erros."
        )

    # ----------------------------------------------------------------------
    # IMPORTAÇÃO
    # ----------------------------------------------------------------------

    def importar_para_qstione(
        self,
        dados_transformados: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Reconstrói a tabela no banco Qstione.

        A tabela é limpa antes da inserção.

        Parameters
        ----------
        dados_transformados:
            Registros gerados pelo Python.

        Returns
        -------
        dict
            Resumo da operação.
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
                                registro["codigoUnidade"],
                                registro["nomeUnidade"],
                                registro["codigoCurso"],
                                registro["codigoDisciplina"],
                                registro["ordemExibicao"],
                                registro["codigoAgrupamento"],
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
                "❌ Erro durante reconstrução da tabela: %s",
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

    # ----------------------------------------------------------------------
    # EXECUÇÃO
    # ----------------------------------------------------------------------

    def executar_importacao(self) -> List[Dict[str, Any]]:
        """
        Executa todo o processo de geração das unidades de avaliação.

        Returns
        -------
        list[dict]
            Registros gerados.
        """

        logger.info("=" * 100)
        logger.info(
            "INÍCIO imp_013_unidades_avaliacao_regras"
        )
        logger.info(
            "ANO=%s | PERIODOS=%s | FACULDADES=%s",
            ANO,
            PERIODOS,
            FACULDADES,
        )
        logger.info("=" * 100)

        # --------------------------------------------------------------
        # 1. BUSCA
        # --------------------------------------------------------------

        dados = self.obter_dados_lyceum()

        # --------------------------------------------------------------
        # 2. TRANSFORMAÇÃO
        # --------------------------------------------------------------

        transformados = self.transformar_dados(
            dados
        )

        # --------------------------------------------------------------
        # 3. VALIDAÇÃO
        # --------------------------------------------------------------

        self.validar_dados(
            transformados
        )

        # --------------------------------------------------------------
        # 4. IMPORTAÇÃO
        # --------------------------------------------------------------

        resultado = self.importar_para_qstione(
            transformados
        )

        # --------------------------------------------------------------
        # 5. RESUMO
        # --------------------------------------------------------------

        logger.info("=" * 100)
        logger.info(
            "FIM imp_013_unidades_avaliacao_regras"
        )
        logger.info(
            "Processados : %d",
            resultado["total_processados"],
        )
        logger.info(
            "Inseridos   : %d",
            resultado["total_inseridos"],
        )
        logger.info(
            "Atualizados : %d",
            resultado["total_atualizados"],
        )
        logger.info(
            "Erros       : %d",
            resultado["total_erros"],
        )
        logger.info("=" * 100)

        return transformados


# ============================================================================
# EXECUÇÃO DIRETA PELO PLAY DO VS CODE
# ============================================================================

if __name__ == "__main__":
    ImportadorUnidadesAvaliacaoRegras().executar_importacao()