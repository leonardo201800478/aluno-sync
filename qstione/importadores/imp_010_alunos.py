"""
qstione/importadores/imp_010_alunos.py

Importador independente para a tabela imp_010_alunos.

===============================================================================
OBJETIVO
===============================================================================

Cadastrar os alunos efetivamente matriculados nas turmas do período vigente,
determinando os cursos através das próprias matrículas.

A fonte da relação aluno -> curso NÃO é LY_ALUNO.curso.

A relação correta é:

    LY_MATRICULA
        |
        | aluno
        | ano
        | semestre
        | disciplina
        | turma
        v
    LY_TURMA
        |
        | ano
        | semestre
        | disciplina
        | turma
        | curso
        v
    LY_CURSO
        |
        | faculdade
        v
    filtros configurados


===============================================================================
FILTROS
===============================================================================

Somente matrículas que atendam simultaneamente aos filtros configurados:

    ANO_VIGENTE
    PERIODOS_VIGENTES
    FACULDADES_INCLUIDAS

A faculdade é determinada pelo curso existente em LY_TURMA.curso,
através de LY_CURSO.faculdade.


===============================================================================
CURSOS
===============================================================================

O código do curso da turma é normalizado utilizando exatamente:

    MAPEAMENTO_CURSOS

proveniente de:

    imp_002_disciplina.py


Exemplo:

    020 -> 006
    062 -> 064
    057 -> 064
    etc.


===============================================================================
TURMAS COMPARTILHADAS
===============================================================================

Quando LY_TURMA.curso for:

    NULL
    vazio
    999

a matrícula será considerada pertencente ao curso:

    999

Esse registro é independente do curso normal do mesmo aluno.

Exemplo:

    aluno 6980
        turma T01 -> curso 020 -> 006
        turma T02 -> curso NULL -> 999

Resultado:

    6980 | 006
    6980 | 999


===============================================================================
CHAVE
===============================================================================

Como um mesmo aluno pode possuir mais de um curso, a chave da tabela é:

    (matriculaAluno, codigoCurso)


===============================================================================
TURNO
===============================================================================

Valores aceitos:

    M
    T
    N
    I

Qualquer outro valor, inclusive NULL ou vazio:

    I = Integral


===============================================================================
EXECUÇÃO
===============================================================================

O arquivo pode ser executado diretamente pelo botão Play do VS Code.

A tabela é completamente limpa antes de cada importação.
"""

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
# IMPORTADOR
# =============================================================================

class ImportadorAlunos:
    """
    Importador da tabela imp_010_alunos.

    Cada registro representa uma relação:

        aluno + curso

    O curso é determinado pelas turmas em que o aluno possui
    matrícula no período vigente.
    """

    def __init__(self):
        """
        Inicializa o importador.

        Os filtros são obtidos diretamente de qstione.config.filtros.
        """

        pass

    # =========================================================================
    # TABELA
    # =========================================================================

    def _tabela_existe(
        self,
        nome_tabela: str,
    ) -> bool:
        """
        Verifica se uma tabela existe no banco Qstione.

        Parameters
        ----------
        nome_tabela:
            Nome da tabela.

        Returns
        -------
        bool
            True quando a tabela existe.
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
                    (nome_tabela,),
                ).fetchone()

                return resultado is not None

        except Exception as e:

            print(
                f"⚠️ Erro ao verificar tabela "
                f"{nome_tabela}: {e}"
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
        Verifica se um índice existe no SQL Server.
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
                    (nome_indice,),
                ).fetchone()

                return resultado is not None

        except Exception as e:

            print(
                f"⚠️ Erro ao verificar índice "
                f"{nome_indice}: {e}"
            )

            return False

    # =========================================================================
    # CRIAÇÃO DA TABELA
    # =========================================================================

    def _criar_tabela(self):
        """
        Cria a tabela imp_010_alunos caso ela não exista.

        A chave primária é composta por:

            matriculaAluno
            codigoCurso

        Isso permite que o mesmo aluno possua mais de um curso.
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

                        data_criacao DATETIME2
                            DEFAULT GETDATE(),

                        data_atualizacao DATETIME2
                            DEFAULT GETDATE(),

                        PRIMARY KEY (
                            matriculaAluno,
                            codigoCurso
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

            raise

        self._criar_indices()

    # =========================================================================
    # ÍNDICES
    # =========================================================================

    def _criar_indices(self):
        """
        Cria os índices auxiliares da tabela.
        """

        indices = [

            (
                "idx_alunos_curso",
                """
                CREATE INDEX idx_alunos_curso
                ON imp_010_alunos(codigoCurso)
                """,
            ),

            (
                "idx_alunos_email",
                """
                CREATE INDEX idx_alunos_email
                ON imp_010_alunos(emailAluno)
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
        Remove todos os registros da tabela antes da carga.

        Primeiro tenta TRUNCATE.
        Se não for possível, utiliza DELETE.
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
                "esvaziada com TRUNCATE."
            )

        except Exception as e:

            print(
                f"⚠️ TRUNCATE falhou: {e}"
            )

            print(
                "🔄 Tentando DELETE..."
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
    # CURSO
    # =========================================================================

    @staticmethod
    def _normalizar_curso(
        curso,
    ) -> str:
        """
        Normaliza o curso da turma.

        Fonte:

            LY_TURMA.curso

        Regras:

            NULL  -> 999
            vazio -> 999
            999   -> 999

        Cursos presentes no MAPEAMENTO_CURSOS são convertidos
        para o código unificado.

        Cursos não mapeados permanecem com o código original.
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

            codigo = (
                MAPEAMENTO_CURSOS[curso][0]
            )

            return str(
                codigo
            ).strip()

        return curso

    # =========================================================================
    # TURNO
    # =========================================================================

    @staticmethod
    def _normalizar_turno(
        turno,
    ) -> str:
        """
        Normaliza o turno.

        Valores válidos:

            M
            T
            N
            I

        Qualquer outro valor:

            I
        """

        turno_final = mapear_turno(
            turno
        )

        if turno_final not in (
            "M",
            "T",
            "N",
            "I",
        ):

            turno_final = "I"

        return turno_final

    # =========================================================================
    # CONSULTA LYCEUM
    # =========================================================================

    def obter_dados_lyceum(self):
        """
        Busca as matrículas dentro dos filtros de:

            - ANO_VIGENTE
            - PERIODOS_VIGENTES
            - FACULDADES_INCLUIDAS

        A faculdade é determinada pelo curso da turma.

        Regra especial:
            curso NULL / vazio / 999
                -> curso 999
                -> faculdade 001
        """

        periodos_sql = ",".join(
            "?" for _ in PERIODOS_VIGENTES
        )

        faculdades_sql = ",".join(
            "?" for _ in FACULDADES_INCLUIDAS
        )

        query = f"""
            SELECT DISTINCT

                m.aluno,
                a.nome_compl,
                a.unidade_ensino,
                a.turno,

                m.ano,
                m.semestre,
                m.disciplina,
                m.turma,

                t.curso

            FROM LY_MATRICULA m

            INNER JOIN LY_TURMA t
                ON t.ano = m.ano
            AND t.semestre = m.semestre
            AND t.disciplina = m.disciplina
            AND t.turma = m.turma

            INNER JOIN LY_ALUNO a
                ON a.aluno = m.aluno

            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso

            WHERE a.sit_aluno = 'Ativo'

            AND m.ano = ?

            AND m.semestre IN (
                {periodos_sql}
            )

            AND t.sit_turma = ?

            AND (
                    c.faculdade IN (
                        {faculdades_sql}
                    )

                    OR

                    (
                        (
                            t.curso IS NULL
                            OR LTRIM(RTRIM(t.curso)) = ''
                            OR LTRIM(RTRIM(t.curso)) = '999'
                        )

                        AND '001' IN (
                            {faculdades_sql}
                        )
                    )
            )

            ORDER BY
                m.aluno,
                m.ano,
                m.semestre,
                m.disciplina,
                m.turma
        """

        params = [
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,

            *FACULDADES_INCLUIDAS,

            *FACULDADES_INCLUIDAS,
        ]

        with get_db_connection() as conn:

            cursor = conn.cursor()

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
        Transforma as matrículas em relações aluno/curso.

        Uma matrícula individual não gera necessariamente uma linha.

        Todas as matrículas do mesmo aluno são agrupadas pelo curso.

        Exemplo:

            6980 / T01 / curso 020
            6980 / T02 / curso NULL
            6980 / T03 / curso 062

        Após normalização:

            6980 / 006
            6980 / 999
            6980 / 064

        Cada relação aluno/curso é gravada apenas uma vez.
        """

        registros = {}

        total_matriculas = 0
        total_cursos = 0
        total_compartilhadas = 0
        total_mapeados = 0

        for (
            aluno,
            nome,
            unidade_ensino,
            turno,
            ano,
            semestre,
            disciplina,
            turma,
            curso_turma,
        ) in dados_lyceum:

            total_matriculas += 1

            # -----------------------------------------------------------------
            # MATRÍCULA
            # -----------------------------------------------------------------

            if not validar_matricula(
                aluno
            ):

                print(
                    f"⚠️ Matrícula inválida: "
                    f"{aluno}"
                )

                continue

            # -----------------------------------------------------------------
            # NOME
            # -----------------------------------------------------------------

            if not validar_nome(
                nome
            ):

                print(
                    f"⚠️ Nome inválido para "
                    f"aluno {aluno}: {nome}"
                )

                continue

            # -----------------------------------------------------------------
            # CURSO DA TURMA
            # -----------------------------------------------------------------

            curso_original = (
                str(curso_turma).strip()
                if curso_turma is not None
                else ""
            )

            curso_unificado = (
                self._normalizar_curso(
                    curso_turma
                )
            )

            # -----------------------------------------------------------------
            # CURSO COMPARTILHADO
            # -----------------------------------------------------------------

            if curso_unificado == "999":

                total_compartilhadas += 1

            # -----------------------------------------------------------------
            # CURSO MAPEADO
            # -----------------------------------------------------------------

            elif curso_original in MAPEAMENTO_CURSOS:

                total_mapeados += 1

                if (
                    curso_original
                    != curso_unificado
                ):

                    print(
                        f"  🔄 Curso "
                        f"{curso_original} → "
                        f"{curso_unificado} | "
                        f"aluno={aluno} | "
                        f"turma={turma} | "
                        f"disciplina={disciplina}"
                    )

            # -----------------------------------------------------------------
            # VALIDAÇÃO DO CURSO
            # -----------------------------------------------------------------

            if not validar_codigo_curso(
                curso_unificado
            ):

                print(
                    f"⚠️ Código de curso inválido: "
                    f"{curso_original} → "
                    f"{curso_unificado} | "
                    f"aluno={aluno} | "
                    f"turma={turma} | "
                    f"disciplina={disciplina}"
                )

                continue

            # -----------------------------------------------------------------
            # MATRÍCULA
            # -----------------------------------------------------------------

            matricula = truncar_texto(
                str(aluno),
                20,
            )

            # -----------------------------------------------------------------
            # E-MAIL
            # -----------------------------------------------------------------

            dominio = (
                "@etecfoa.com.br"
                if str(
                    unidade_ensino
                ).strip() == "007"
                else "@unifoa.edu.br"
            )

            email = truncar_texto(
                converter_minusculas(
                    f"{matricula}{dominio}"
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
            # CHAVE
            # -----------------------------------------------------------------

            chave = (
                matricula,
                curso_unificado,
            )

            # -----------------------------------------------------------------
            # REGISTRO
            # -----------------------------------------------------------------

            if chave not in registros:

                registros[chave] = {

                    "matriculaAluno":
                        matricula,

                    "nomeAluno":
                        truncar_texto(
                            nome,
                            140,
                        ),

                    "emailAluno":
                        email,

                    "codigoCurso":
                        truncar_texto(
                            curso_unificado,
                            30,
                        ),

                    "turno":
                        turno_final,

                    "codigoIdentificacaoAVA":
                        "",
                }

                total_cursos += 1

        # ---------------------------------------------------------------------
        # RESUMO
        # ---------------------------------------------------------------------

        print(
            "\n📚 RESUMO DA TRANSFORMAÇÃO"
        )

        print(
            f"  📋 Matrículas analisadas: "
            f"{total_matriculas}"
        )

        print(
            f"  👤 Relações aluno/curso: "
            f"{total_cursos}"
        )

        print(
            f"  🔄 Cursos normalizados: "
            f"{total_mapeados}"
        )

        print(
            f"  🔗 Relações com curso 999: "
            f"{total_compartilhadas}"
        )

        return list(
            registros.values()
        )

    # =========================================================================
    # IMPORTAÇÃO
    # =========================================================================

    def importar_para_qstione(
        self,
        dados_transformados,
    ):
        """
        Limpa completamente a tabela e insere os novos dados.
        """

        self._criar_tabela()

        self._limpar_tabela()

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

        insert_sql = """
            INSERT INTO imp_010_alunos
            (
                matriculaAluno,
                nomeAluno,
                emailAluno,
                codigoCurso,
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
                            reg[
                                "matriculaAluno"
                            ],

                            reg[
                                "nomeAluno"
                            ],

                            reg[
                                "emailAluno"
                            ],

                            reg[
                                "codigoCurso"
                            ],

                            reg[
                                "turno"
                            ],

                            reg[
                                "codigoIdentificacaoAVA"
                            ],
                        ),
                    )

                    inseridos += 1

                except Exception as e:

                    erros += 1

                    print(
                        f"  ✗ Erro ao inserir "
                        f"aluno="
                        f"{reg['matriculaAluno']} "
                        f"curso="
                        f"{reg['codigoCurso']}: "
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
            "=" * 78
        )

        print(
            "IMPORTAÇÃO: imp_010_alunos"
        )

        print(
            "=" * 78
        )

        print(
            f"📅 ANO: {ANO_VIGENTE}"
        )

        print(
            f"📅 PERÍODOS: {PERIODOS_VIGENTES}"
        )

        print(
            f"🏫 FACULDADES: {FACULDADES_INCLUIDAS}"
        )

        print(
            f"📚 SITUAÇÃO DA TURMA: "
            f"{SITUACAO_TURMA_VALIDA}"
        )

        print(
            "🔗 Fonte da matrícula: LY_MATRICULA"
        )

        print(
            "🏫 Fonte do curso: LY_TURMA.curso"
        )

        print(
            "🏛️ Fonte da faculdade: LY_CURSO.faculdade"
        )

        print(
            "🔄 Mapeamento de cursos: imp_002_disciplina"
        )

        print(
            "🔗 Curso NULL/999: 999"
        )

        # ---------------------------------------------------------------------
        # CONSULTA
        # ---------------------------------------------------------------------

        dados = (
            self.obter_dados_lyceum()
        )

        print(
            f"\n📊 Matrículas encontradas: "
            f"{len(dados)}"
        )

        # ---------------------------------------------------------------------
        # TRANSFORMAÇÃO
        # ---------------------------------------------------------------------

        transformados = (
            self.transformar_dados(
                dados
            )
        )

        print(
            f"✅ Relações aluno/curso "
            f"válidas: {len(transformados)}"
        )

        # ---------------------------------------------------------------------
        # IMPORTAÇÃO
        # ---------------------------------------------------------------------

        resultado = (
            self.importar_para_qstione(
                transformados
            )
        )

        # ---------------------------------------------------------------------
        # RESULTADO
        # ---------------------------------------------------------------------

        print(
            "\n" + "=" * 78
        )

        print(
            "📈 RESULTADO DA IMPORTAÇÃO"
        )

        print(
            "=" * 78
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
            f"  📋 Processados: "
            f"{resultado['total_processados']}"
        )

        print(
            "=" * 78
        )

        return transformados


# =============================================================================
# EXECUÇÃO DIRETA
# =============================================================================

if __name__ == "__main__":

    import logging

    logging.basicConfig(
        level=logging.INFO
    )

    ImportadorAlunos().executar_importacao()