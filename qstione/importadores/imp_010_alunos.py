"""
qstione/importadores/imp_010_alunos.py

Importador independente para a tabela imp_010_alunos.

POPULAÇÃO
---------
Somente alunos que possuem matrícula em:

    qstione.dbo.imp_011_alunos_ofertas

são importados.

REGRAS
------
1. O aluno precisa existir em LY_ALUNO.

2. O aluno precisa estar com:
       sit_aluno = 'Ativo'

3. O aluno precisa existir em:
       imp_011_alunos_ofertas

4. O código de curso utiliza EXATAMENTE o mesmo
   MAPEAMENTO_CURSOS utilizado pelo imp_002_disciplina.py.

5. A normalização do curso ocorre antes da validação:

       LY_ALUNO.curso
            ↓
       MAPEAMENTO_CURSOS
            ↓
       códigoCurso unificado
            ↓
       validação
            ↓
       imp_010_alunos.codigoCurso

6. Exemplos do mapeamento:

       062 → 064
       057 → 064
       023 → 009
       036 → 065
       037 → 065
       020 → 006
       132 → 017
       139 → 044
       142 → 059
       141 → 056
       130 → 007

7. Curso NULL ou vazio:
       999 / COMPARTILHADA

   Essa regra é aplicada pelo mesmo mecanismo central
   utilizado no imp_002.

8. O turno é obtido de LY_ALUNO.turno.

9. Depois do mapeamento do turno, somente:
       M
       T
       N
       I

   são aceitos.

10. Qualquer outro turno, incluindo NULL ou vazio,
    será convertido para:
       I = Integral

11. O e-mail do aluno é construído a partir da matrícula:

       unidade_ensino = 007
           → @etecfoa.com.br

       demais unidades
           → @unifoa.edu.br

12. A tabela destino é totalmente limpa antes de cada carga.

13. O arquivo pode ser executado diretamente pelo botão
    Play do VS Code.

Filtros opcionais:
    --ano
    --semestre
    --unidade
"""

import argparse
import os
import sys


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
    truncar_texto,
    converter_minusculas,
    mapear_turno,
)

from qstione.core.validacoes import (
    validar_matricula,
    validar_nome,
    validar_codigo_curso,
)

# IMPORTANTE:
# O mapeamento de cursos NÃO é duplicado neste arquivo.
# A fonte oficial é o imp_002_disciplina.py.
from qstione.importadores.imp_002_disciplina import (
    MAPEAMENTO_CURSOS,
)


# =============================================================================
# IMPORTADOR
# =============================================================================

class ImportadorAlunos:
    """
    Importador da tabela imp_010_alunos.

    A população é determinada pelos alunos presentes em
    imp_011_alunos_ofertas.

    O código do curso é sempre normalizado utilizando
    o mesmo MAPEAMENTO_CURSOS do imp_002_disciplina.py.
    """

    def __init__(
        self,
        ano=None,
        semestre=None,
        unidade=None,
    ):
        """
        Inicializa o importador.

        Parameters
        ----------
        ano:
            Ano de ingresso opcional.

        semestre:
            Semestre de ingresso opcional.

        unidade:
            Unidade de ensino opcional.
        """

        self.ano = ano
        self.semestre = semestre
        self.unidade = unidade

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela: str,
    ) -> bool:
        """
        Verifica se a tabela existe no banco Qstione.
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

            print(
                f"  ⚠️ Erro ao verificar existência "
                f"da tabela: {e}"
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

            print(
                f"  ⚠️ Erro ao verificar índice "
                f"{nome_indice}: {e}"
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela imp_010_alunos caso ela não exista.
        """

        if self._tabela_existe(
            "imp_010_alunos"
        ):

            self._criar_indices()
            return

        print(
            "🆕 Criando tabela imp_010_alunos..."
        )

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    CREATE TABLE imp_010_alunos (
                        matriculaAluno NVARCHAR(20) NOT NULL,
                        nomeAluno NVARCHAR(140) NOT NULL,
                        emailAluno NVARCHAR(100) NULL,
                        codigoCurso NVARCHAR(30) NOT NULL,
                        turno NVARCHAR(1) NULL,
                        codigoIdentificacaoAVA NVARCHAR(100) NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),

                        PRIMARY KEY (
                            matriculaAluno
                        )
                    )
                    """
                )

                conn.commit()

            print(
                "✅ Tabela criada."
            )

        except Exception as e:

            print(
                f"❌ Erro ao criar tabela: {e}"
            )

            return

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):
        """
        Cria os índices auxiliares.
        """

        indices = [
            (
                "idx_alunos_curso",
                """
                CREATE INDEX idx_alunos_curso
                ON imp_010_alunos(codigoCurso)
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

            except Exception as e:

                print(
                    f"⚠️ Índice {nome_indice} "
                    f"não pôde ser criado: {e}"
                )

    # =========================================================================
    # LIMPEZA
    # =========================================================================

    def _limpar_tabela(self):
        """
        Limpa completamente a tabela destino.

        Primeiro tenta TRUNCATE.
        Se não for permitido, utiliza DELETE.
        """

        try:

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    TRUNCATE TABLE imp_010_alunos
                    """
                )

                conn.commit()

            print(
                "🧹 Tabela imp_010_alunos "
                "esvaziada com sucesso."
            )

        except Exception as e:

            print(
                f"⚠️ TRUNCATE falhou ({e}), "
                f"tentando DELETE..."
            )

            with get_db_connection(
                database_name="qstione"
            ) as conn:

                conn.execute(
                    """
                    DELETE FROM imp_010_alunos
                    """
                )

                conn.commit()

            print(
                "🧹 Tabela imp_010_alunos "
                "esvaziada via DELETE."
            )

    # =========================================================================
    # NORMALIZAÇÃO DE CURSO
    # =========================================================================

    @staticmethod
    def _normalizar_curso(
        curso,
    ) -> str:
        """
        Normaliza o código de curso usando EXATAMENTE o
        MAPEAMENTO_CURSOS do imp_002_disciplina.py.

        Parameters
        ----------
        curso:
            Código original de LY_ALUNO.curso.

        Returns
        -------
        str
            Código de curso unificado.

        Regras
        ------
        NULL ou vazio:
            999

        Curso existente no MAPEAMENTO_CURSOS:
            utiliza MAPEAMENTO_CURSOS[curso][0]

        Curso não mapeado:
            mantém o código original.
        """

        # ---------------------------------------------------------------------
        # NULL
        # ---------------------------------------------------------------------

        if curso is None:

            return "999"

        # ---------------------------------------------------------------------
        # NORMALIZAÇÃO DO TEXTO
        # ---------------------------------------------------------------------

        curso = str(
            curso
        ).strip()

        # ---------------------------------------------------------------------
        # VAZIO
        # ---------------------------------------------------------------------

        if not curso:

            return "999"

        # ---------------------------------------------------------------------
        # MAPEAMENTO OFICIAL
        # ---------------------------------------------------------------------

        if curso in MAPEAMENTO_CURSOS:

            codigo_unificado = (
                MAPEAMENTO_CURSOS[curso][0]
            )

            return str(
                codigo_unificado
            ).strip()

        # ---------------------------------------------------------------------
        # CURSO NÃO MAPEADO
        # ---------------------------------------------------------------------

        return curso

    # =========================================================================
    # NORMALIZAÇÃO DO TURNO
    # =========================================================================

    @staticmethod
    def _normalizar_turno(
        turno,
    ) -> str:
        """
        Normaliza o turno do aluno.

        Valores válidos:
            M
            T
            N
            I

        Qualquer outro valor:
            I

        Portanto NULL, vazio ou código desconhecido
        são tratados como Integral.
        """

        turno_mapeado = mapear_turno(
            turno
        )

        if turno_mapeado not in (
            "M",
            "T",
            "N",
            "I",
        ):

            turno_mapeado = "I"

        return turno_mapeado

    # =========================================================================
    # OBTENÇÃO DOS DADOS
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Obtém somente alunos ativos presentes em
        imp_011_alunos_ofertas.
        """

        with get_db_connection() as conn:

            cursor = conn.cursor()

            query = """
                SELECT DISTINCT
                    a.aluno,
                    a.nome_compl,
                    a.unidade_ensino,
                    a.curso,
                    a.turno

                FROM LY_ALUNO a

                INNER JOIN qstione.dbo.imp_011_alunos_ofertas ao
                    ON ao.matriculaAluno = a.aluno

                WHERE a.sit_aluno = 'Ativo'
            """

            params = []

            # -----------------------------------------------------------------
            # ANO
            # -----------------------------------------------------------------

            if self.ano is not None:

                query += """
                    AND a.ano_ingresso = ?
                """

                params.append(
                    self.ano
                )

            # -----------------------------------------------------------------
            # SEMESTRE
            # -----------------------------------------------------------------

            if self.semestre is not None:

                query += """
                    AND a.sem_ingresso = ?
                """

                params.append(
                    self.semestre
                )

            # -----------------------------------------------------------------
            # UNIDADE
            # -----------------------------------------------------------------

            if self.unidade is not None:

                query += """
                    AND a.unidade_ensino = ?
                """

                params.append(
                    self.unidade
                )

            query += """
                ORDER BY a.aluno
            """

            cursor.execute(
                query,
                params,
            )

            return cursor.fetchall()

    # =========================================================================
    # TRANSFORMAÇÃO
    # =========================================================================

    def transformar_dados(
        self,
        dados_lyceum,
    ):
        """
        Valida e transforma os alunos.

        A ordem da transformação do curso é:

            LY_ALUNO.curso
                    ↓
            MAPEAMENTO_CURSOS
                    ↓
            código unificado
                    ↓
            validação
                    ↓
            gravação

        Isso garante que o imp_010 utilize exatamente os
        mesmos códigos utilizados pelo imp_002.
        """

        dados_transformados = []

        total_cursos_mapeados = 0
        total_cursos_nao_mapeados = 0
        total_cursos_999 = 0

        for (
            aluno,
            nome_compl,
            unidade_ensino,
            curso,
            turno,
        ) in dados_lyceum:

            # -----------------------------------------------------------------
            # MATRÍCULA
            # -----------------------------------------------------------------

            if not validar_matricula(
                aluno
            ):

                print(
                    f"  ⚠️ Matrícula inválida: "
                    f"{aluno}"
                )

                continue

            # -----------------------------------------------------------------
            # NOME
            # -----------------------------------------------------------------

            if not validar_nome(
                nome_compl
            ):

                print(
                    f"  ⚠️ Nome inválido para aluno "
                    f"{aluno}: {nome_compl}"
                )

                continue

            # -----------------------------------------------------------------
            # CURSO ORIGINAL
            # -----------------------------------------------------------------

            curso_original = curso

            curso_unificado = (
                self._normalizar_curso(
                    curso
                )
            )

            # -----------------------------------------------------------------
            # LOG DO MAPEAMENTO
            # -----------------------------------------------------------------

            curso_original_texto = (
                str(curso_original).strip()
                if curso_original is not None
                else ""
            )

            if curso_unificado == "999":

                total_cursos_999 += 1

            elif (
                curso_original_texto
                and curso_original_texto in MAPEAMENTO_CURSOS
            ):

                total_cursos_mapeados += 1

                if (
                    curso_original_texto
                    != curso_unificado
                ):

                    print(
                        f"  🔄 Curso "
                        f"{curso_original_texto} → "
                        f"{curso_unificado} "
                        f"(aluno {aluno})"
                    )

            else:

                total_cursos_nao_mapeados += 1

            # -----------------------------------------------------------------
            # VALIDAÇÃO DO CURSO UNIFICADO
            # -----------------------------------------------------------------

            if not validar_codigo_curso(
                curso_unificado
            ):

                print(
                    f"  ⚠️ Código de curso inválido "
                    f"após normalização: "
                    f"{curso_original} → "
                    f"{curso_unificado} "
                    f"para aluno {aluno}"
                )

                continue

            # -----------------------------------------------------------------
            # E-MAIL
            # -----------------------------------------------------------------

            dominio = (
                "@etecfoa.com.br"
                if unidade_ensino == "007"
                else "@unifoa.edu.br"
            )

            email_aluno = truncar_texto(
                converter_minusculas(
                    f"{aluno}{dominio}"
                ),
                100,
            )

            # -----------------------------------------------------------------
            # TURNO
            # -----------------------------------------------------------------

            turno_final = (
                self._normalizar_turno(
                    turno
                )
            )

            # -----------------------------------------------------------------
            # REGISTRO
            # -----------------------------------------------------------------

            dados_transformados.append(
                {
                    "matriculaAluno": str(
                        aluno
                    )[:20],

                    "nomeAluno": truncar_texto(
                        nome_compl,
                        140,
                    ),

                    "emailAluno": email_aluno,

                    "codigoCurso": truncar_texto(
                        curso_unificado,
                        30,
                    ),

                    "turno": turno_final,

                    "codigoIdentificacaoAVA": "",
                }
            )

        # ---------------------------------------------------------------------
        # RESUMO DO MAPEAMENTO
        # ---------------------------------------------------------------------

        print(
            "\n📚 NORMALIZAÇÃO DE CURSOS:"
        )

        print(
            f"  🔄 Cursos encontrados no "
            f"MAPEAMENTO_CURSOS: "
            f"{total_cursos_mapeados}"
        )

        print(
            f"  ➡️ Cursos sem alteração: "
            f"{total_cursos_nao_mapeados}"
        )

        print(
            f"  🔗 Cursos NULL/vazios → 999: "
            f"{total_cursos_999}"
        )

        return dados_transformados

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ):
        """
        Reconstrói integralmente a tabela imp_010_alunos.
        """

        self._criar_tabela()

        self._limpar_tabela()

        # ---------------------------------------------------------------------
        # SEM REGISTROS
        # ---------------------------------------------------------------------

        if not dados_transformados:

            print(
                "ℹ️ Nenhum aluno elegível "
                "para importar."
            )

            return {
                "total_inseridos": 0,
                "total_atualizados": 0,
                "total_erros": 0,
                "total_processados": 0,
            }

        # ---------------------------------------------------------------------
        # SQL
        # ---------------------------------------------------------------------

        insert_sql = """
            INSERT INTO imp_010_alunos (
                matriculaAluno,
                nomeAluno,
                emailAluno,
                codigoCurso,
                turno,
                codigoIdentificacaoAVA,
                data_criacao,
                data_atualizacao
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                GETDATE(),
                GETDATE()
            )
        """

        inseridos = 0
        erros = 0

        with get_db_connection(
            database_name="qstione"
        ) as conn:

            cursor = conn.cursor()

            for reg in dados_transformados:

                try:

                    cursor.execute(
                        insert_sql,
                        (
                            reg["matriculaAluno"],
                            reg["nomeAluno"],
                            reg["emailAluno"],
                            reg["codigoCurso"],
                            reg["turno"],
                            reg["codigoIdentificacaoAVA"],
                        ),
                    )

                    inseridos += 1

                except Exception as e:

                    erros += 1

                    print(
                        f"  ✗ Erro ao inserir "
                        f"{reg['matriculaAluno']}: "
                        f"{e}"
                    )

            conn.commit()

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
        Executa a importação completa.
        """

        print(
            "=" * 70
        )

        print(
            "IMPORTAÇÃO: imp_010_alunos"
        )

        print(
            "=" * 70
        )

        print(
            "🎓 População: somente alunos "
            "presentes em imp_011_alunos_ofertas"
        )

        print(
            "📚 Cursos: MAPEAMENTO_CURSOS "
            "do imp_002_disciplina"
        )

        print(
            "🕐 Turnos desconhecidos: I "
            "(Integral)"
        )

        # ---------------------------------------------------------------------
        # FILTROS
        # ---------------------------------------------------------------------

        filtros_aplicados = []

        if self.ano is not None:

            filtros_aplicados.append(
                f"ano_ingresso={self.ano}"
            )

        if self.semestre is not None:

            filtros_aplicados.append(
                f"sem_ingresso={self.semestre}"
            )

        if self.unidade is not None:

            filtros_aplicados.append(
                f"unidade_ensino='{self.unidade}'"
            )

        if filtros_aplicados:

            print(
                "🔍 Filtros adicionais: "
                + ", ".join(
                    filtros_aplicados
                )
            )

        # ---------------------------------------------------------------------
        # CONSULTA
        # ---------------------------------------------------------------------

        dados_lyceum = (
            self.obter_dados_lyceum()
        )

        print(
            f"📊 Alunos elegíveis encontrados: "
            f"{len(dados_lyceum)}"
        )

        # ---------------------------------------------------------------------
        # TRANSFORMAÇÃO
        # ---------------------------------------------------------------------

        dados_transformados = (
            self.transformar_dados(
                dados_lyceum
            )
        )

        print(
            f"✅ Registros válidos: "
            f"{len(dados_transformados)}"
        )

        # ---------------------------------------------------------------------
        # IMPORTAÇÃO
        # ---------------------------------------------------------------------

        resultado = (
            self.importar_para_qstione(
                dados_transformados
            )
        )

        # ---------------------------------------------------------------------
        # RESULTADO
        # ---------------------------------------------------------------------

        print(
            "\n📈 RESULTADO DA IMPORTAÇÃO:"
        )

        print(
            f"  ✓ Inseridos: "
            f"{resultado['total_inseridos']}"
        )

        print(
            f"  ✗ Erros: "
            f"{resultado['total_erros']}"
        )

        print(
            f"  📋 Total processados: "
            f"{resultado['total_processados']}"
        )

        return dados_transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    import logging

    logging.basicConfig(
        level=logging.INFO
    )

    parser = argparse.ArgumentParser(
        description=(
            "Importação de alunos presentes "
            "nas ofertas vigentes."
        )
    )

    parser.add_argument(
        "--ano",
        type=int,
        help=(
            "Filtro opcional de ano "
            "de ingresso."
        ),
    )

    parser.add_argument(
        "--semestre",
        type=int,
        help=(
            "Filtro opcional de semestre "
            "de ingresso."
        ),
    )

    parser.add_argument(
        "--unidade",
        type=str,
        help=(
            "Filtro opcional de unidade "
            "de ensino."
        ),
    )

    args = parser.parse_args()

    ImportadorAlunos(
        ano=args.ano,
        semestre=args.semestre,
        unidade=args.unidade,
    ).executar_importacao()