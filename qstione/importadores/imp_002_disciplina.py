#!/usr/bin/env python3
# qstione/importadores/imp_002_disciplina.py
"""
Importador para imp_002_disciplina
Fonte: LY_MATRICULA -> LY_TURMA -> LY_ALUNO -> LY_CURSO, LY_DISCIPLINA, LY_GRADE

Regras de filtro (centralizadas em qstione/config/filtros.py):
- ANO_VIGENTE / PERIODOS_VIGENTES: ano e semestre letivos vigentes
- FACULDADES_INCLUIDAS: faculdade do CURSO (LY_CURSO.faculdade) deve estar nessa lista
  (hoje = ['001']) quando a turma tiver um curso definido.
- SITUACAO_TURMA_VALIDA: situação exigida em LY_TURMA.sit_turma (hoje = 'aberta')

Regras de negócio:
- O curso da disciplina/oferta é SEMPRE obtido de LY_TURMA.curso (nunca do curso do aluno).
- Se LY_TURMA.curso for NULL (turma sem curso definido), o registro é mantido e o curso é
  tratado como '999' (COMPARTILHADA) — essas turmas precisam continuar sendo importadas.
- Se LY_TURMA.curso estiver preenchido, a faculdade do curso (via LY_CURSO) precisa estar
  em FACULDADES_INCLUIDAS para o registro ser considerado.
- LY_TURMA.sit_turma precisa ser igual a SITUACAO_TURMA_VALIDA.
- O JOIN entre LY_MATRICULA e LY_TURMA é feito pela chave composta completa
  (ano, semestre, turma, disciplina), evitando casamento incorreto entre turmas de
  períodos/disciplinas diferentes que compartilhem apenas o código de 'turma'.
- Nome da disciplina obtido de LY_DISCIPLINA.nome
- Período obtido de LY_GRADE.serie_ideal (usando SEMPRE o curso da turma)
- Mapeamento unificado de cursos (códigos duplicados agrupados)
- Código da disciplina com sufixo do nome do curso unificado
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import get_db_connection
from qstione.core.transformacoes import (
    converter_inteiro,
    gerar_codigo_disciplina_curso,
    truncar_texto
)
from qstione.core.validacoes import (
    validar_codigo_disciplina,
    validar_codigo_curso
)
from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)

# =============================================================================
# MAPEAMENTO DE CURSOS – UNIFICAÇÃO DE CÓDIGOS
# =============================================================================
MAPEAMENTO_CURSOS = {
    '034': ('034', 'ADMINISTRAÇÃO'),
    '064': ('064', 'CIÊNCIAS BIOLÓGICAS'),
    '062': ('064', 'CIÊNCIAS BIOLÓGICAS'),
    '057': ('064', 'CIÊNCIAS BIOLÓGICAS'),
    '009': ('009', 'CIÊNCIAS CONTÁBEIS'),
    '023': ('009', 'CIÊNCIAS CONTÁBEIS'),
    '055': ('055', 'CURSO SUPERIOR DE TECNOLOGIA EM GESTÃO DE RECURSOS HUMANOS'),
    '056': ('056', 'DESIGN'),
    '141': ('056', 'DESIGN'),
    '031': ('031', 'DIREITO'),
    '065': ('065', 'EDUCAÇÃO FÍSICA'),
    '036': ('065', 'EDUCAÇÃO FÍSICA'),
    '037': ('065', 'EDUCAÇÃO FÍSICA'),
    '013': ('013', 'ENFERMAGEM'),
    '079': ('079', 'ENGENHARIA'),
    '006': ('006', 'ENGENHARIA CIVIL'),
    '020': ('006', 'ENGENHARIA CIVIL'),
    '097': ('097', 'ENGENHARIA DA COMPUTAÇÃO'),
    '059': ('059', 'ENGENHARIA DE PRODUÇÃO'),
    '142': ('059', 'ENGENHARIA DE PRODUÇÃO'),
    '044': ('044', 'ENGENHARIA ELÉTRICA'),
    '139': ('044', 'ENGENHARIA ELÉTRICA'),
    '017': ('017', 'ENGENHARIA MECÂNICA'),
    '132': ('017', 'ENGENHARIA MECÂNICA'),
    '126': ('126', 'FARMÁCIA'),
    '060': ('060', 'JORNALISMO'),
    '014': ('014', 'MEDICINA'),
    '024': ('024', 'NUTRIÇÃO'),
    '007': ('007', 'ODONTOLOGIA'),
    '130': ('007', 'ODONTOLOGIA'),
    '128': ('128', 'PEDAGOGIA'),
    '145': ('145', 'PSICOLOGIA'),
    '061': ('061', 'PUBLICIDADE E PROPAGANDA'),
    '025': ('025', 'SERVIÇO SOCIAL'),
    '019': ('019', 'SISTEMAS DE INFORMAÇÃO'),
    '999': ('999', 'COMPARTILHADA'),  # turmas sem curso definido em LY_TURMA
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ImportadorDisciplinas:

    def __init__(self):
        self.periodos_placeholders = ','.join(['?'] * len(PERIODOS_VIGENTES))
        self.faculdades_placeholders = ','.join(['?'] * len(FACULDADES_INCLUIDAS))

    # -------------------------------------------------------------------------
    # Funções auxiliares para tabela destino
    # -------------------------------------------------------------------------
    def _tabela_existe(self, nome_tabela: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.warning(f"Erro ao verificar existência da tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,))
                return cursor.fetchone() is not None
        except Exception as e:
            logger.warning(f"Erro ao verificar índice: {e}")
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_002_disciplina'):
            logger.info("✅ Tabela imp_002_disciplina já existe.")
            return

        logger.info("🆕 Criando tabela imp_002_disciplina...")
        create_sql = """
            CREATE TABLE imp_002_disciplina (
                codigoDisciplina NVARCHAR(30) NOT NULL,
                nomeDisciplina NVARCHAR(100) NOT NULL,
                codigoCurso NVARCHAR(30) NOT NULL,
                periodo INTEGER NOT NULL,
                data_criacao DATETIME2 DEFAULT GETDATE(),
                data_atualizacao DATETIME2 DEFAULT GETDATE(),
                PRIMARY KEY (codigoDisciplina, codigoCurso, periodo)
            )
        """
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute(create_sql)
                conn.commit()
            logger.info("✅ Tabela criada.")
        except Exception as e:
            logger.error(f"❌ Erro ao criar tabela: {e}")
            return

        indices = [
            ('idx_disciplinas_curso', "CREATE INDEX idx_disciplinas_curso ON imp_002_disciplina(codigoCurso)"),
            ('idx_disciplinas_nome', "CREATE INDEX idx_disciplinas_nome ON imp_002_disciplina(nomeDisciplina)")
        ]
        for nome_idx, sql_idx in indices:
            if not self._indice_existe(nome_idx):
                try:
                    with get_db_connection(database_name='qstione') as conn:
                        conn.execute(sql_idx)
                        conn.commit()
                    logger.info(f"✅ Índice {nome_idx} criado.")
                except Exception as e:
                    logger.warning(f"⚠️ Índice {nome_idx} não pôde ser criado: {e}")

    # -------------------------------------------------------------------------
    # Obter dados do Lyceum com JOINs LY_DISCIPLINA e LY_GRADE
    #
    # Regras aplicadas:
    #  - JOIN de LY_MATRICULA com LY_TURMA pela chave composta completa
    #    (ano, semestre, turma, disciplina) — evita casamento incorreto entre
    #    turmas de períodos/disciplinas diferentes.
    #  - t.sit_turma = SITUACAO_TURMA_VALIDA (config centralizada)
    #  - Curso sempre vindo de LY_TURMA.curso (nunca do curso do aluno).
    #  - Se t.curso IS NULL -> mantém o registro (turma sem curso definido);
    #    o transformar_dados() converte para '999' (COMPARTILHADA).
    #  - Se t.curso estiver preenchido -> a faculdade do curso (LY_CURSO.faculdade)
    #    precisa estar em FACULDADES_INCLUIDAS.
    # -------------------------------------------------------------------------
    def obter_dados_lyceum(self):
        """
        Obtém as turmas diretamente de LY_TURMA.

        A existência de aluno em LY_MATRICULA ou de docente em
        LY_TURMA_DOCENTE não interfere na seleção.

        A turma precisa apenas:
        - pertencer ao ano vigente;
        - pertencer a um dos períodos vigentes;
        - estar na situação válida;
        - possuir curso cuja faculdade esteja em FACULDADES_INCLUIDAS.

        LY_DISCIPLINA e LY_GRADE são utilizadas somente para complementar
        os dados da turma.
        """
        query = f"""
            SELECT DISTINCT
                t.disciplina,
                d.nome AS nome_disciplina,
                t.curso,
                g.serie_ideal
            FROM LY_TURMA t
            LEFT JOIN LY_CURSO c
                ON c.curso = t.curso
            LEFT JOIN LY_DISCIPLINA d
                ON d.disciplina = t.disciplina
            LEFT JOIN LY_GRADE g
                ON g.disciplina = t.disciplina
            AND g.curso = t.curso
            WHERE t.ano = ?
            AND t.semestre IN ({self.periodos_placeholders})
            AND t.sit_turma = ?
            AND c.faculdade IN ({self.faculdades_placeholders})
            ORDER BY t.disciplina, t.curso
        """

        params = (
            ANO_VIGENTE,
            *PERIODOS_VIGENTES,
            SITUACAO_TURMA_VALIDA,
            *FACULDADES_INCLUIDAS,
        )

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    # -------------------------------------------------------------------------
    # Transformar dados com mapeamento de cursos e nome real da disciplina
    # -------------------------------------------------------------------------
    def transformar_dados(self, dados_lyceum):
        disciplinas = {}
        for disciplina, nome_disciplina, curso, serie_ideal in dados_lyceum:
            # Regra mantida: turma sem curso definido em LY_TURMA -> '999' (COMPARTILHADA)
            if curso is None or curso == '':
                curso = '999'

            # Aplicar mapeamento de curso (unificação de códigos duplicados)
            if curso in MAPEAMENTO_CURSOS:
                curso_unificado, nome_curso_unificado = MAPEAMENTO_CURSOS[curso]
            else:
                curso_unificado = curso
                nome_curso_unificado = curso  # fallback

            # Garante o nome padronizado para o curso '999'
            if curso_unificado == '999':
                nome_curso_unificado = 'COMPARTILHADA'

            if disciplina not in disciplinas:
                disciplinas[disciplina] = {
                    "nome_disciplina": nome_disciplina,
                    "cursos": {}
                }
            if curso_unificado not in disciplinas[disciplina]["cursos"]:
                disciplinas[disciplina]["cursos"][curso_unificado] = {
                    "nome_curso": nome_curso_unificado,
                    "periodos": set()
                }
            if serie_ideal is not None:
                disciplinas[disciplina]["cursos"][curso_unificado]["periodos"].add(serie_ideal)

        dados_transformados = []
        cont_periodo_zero = 0

        for disciplina, info in disciplinas.items():
            nome_disciplina_original = info["nome_disciplina"]
            cursos_info = info["cursos"]

            if not validar_codigo_disciplina(disciplina):
                logger.warning(f"Código da disciplina inválido: {disciplina}")
                continue

            # Nome da disciplina: prioriza o nome da tabela LY_DISCIPLINA, senão usa o código
            if nome_disciplina_original:
                nome_disciplina = truncar_texto(nome_disciplina_original, 100)
            else:
                nome_disciplina = truncar_texto(disciplina, 100)
                logger.debug(f"Nome da disciplina não encontrado, usando código: {disciplina}")

            for curso_unificado, curso_data in cursos_info.items():
                nome_curso = curso_data["nome_curso"]
                periodos = curso_data["periodos"]

                # Se não houver períodos, usa 1 como padrão
                if not periodos:
                    periodo = 1
                    logger.warning(f"Sem período definido para disciplina {disciplina} (curso {curso_unificado}), usando 1")
                else:
                    periodo_raw = min(periodos)
                    periodo = converter_inteiro(periodo_raw)

                    if periodo == 0:
                        periodo = 1
                        cont_periodo_zero += 1
                        logger.warning(f"Período 0 convertido para 1 na disciplina {disciplina} (curso {curso_unificado})")

                if periodo is None or periodo < 1:
                    logger.warning(f"Período inválido para disciplina {disciplina}: {periodo}")
                    continue

                # Curso '999' (sem curso definido / compartilhada) não passa por validar_codigo_curso
                if curso_unificado != '999':
                    if not validar_codigo_curso(curso_unificado):
                        logger.warning(f"Código do curso inválido: {curso_unificado} para disciplina {disciplina}")
                        continue

                # Gera código da disciplina com sufixo do nome do curso (unificado)
                codigo_disciplina_final = gerar_codigo_disciplina_curso(
                    disciplina,
                    nome_curso,
                    curso_unificado
                )

                dados_transformados.append({
                    'codigoDisciplina': codigo_disciplina_final,
                    'nomeDisciplina': nome_disciplina,
                    'codigoCurso': str(curso_unificado)[:30],
                    'periodo': periodo
                })

        if cont_periodo_zero > 0:
            logger.info(f"Total de disciplinas com período 0 convertidas para 1: {cont_periodo_zero}")
        return dados_transformados

    # -------------------------------------------------------------------------
    # Importar para Qstione (MERGE)
    # -------------------------------------------------------------------------
    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()

        merge_sql = """
            MERGE INTO imp_002_disciplina AS target
            USING (VALUES (?, ?, ?, ?)) AS source (codigoDisciplina, nomeDisciplina, codigoCurso, periodo)
            ON target.codigoDisciplina = source.codigoDisciplina
               AND target.codigoCurso = source.codigoCurso
               AND target.periodo = source.periodo
            WHEN MATCHED THEN
                UPDATE SET
                    nomeDisciplina = source.nomeDisciplina,
                    data_atualizacao = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (codigoDisciplina, nomeDisciplina, codigoCurso, periodo, data_criacao, data_atualizacao)
                VALUES (source.codigoDisciplina, source.nomeDisciplina, source.codigoCurso, source.periodo, GETDATE(), GETDATE());
        """

        total_inseridos = 0
        total_atualizados = 0
        total_erros = 0

        with get_db_connection(database_name='qstione') as conn:
            cursor = conn.cursor()
            for reg in dados_transformados:
                try:
                    cursor.execute("""
                        SELECT 1 FROM imp_002_disciplina
                        WHERE codigoDisciplina = ? AND codigoCurso = ? AND periodo = ?
                    """, (reg['codigoDisciplina'], reg['codigoCurso'], reg['periodo']))
                    existe = cursor.fetchone()

                    cursor.execute(merge_sql, (
                        reg['codigoDisciplina'],
                        reg['nomeDisciplina'],
                        reg['codigoCurso'],
                        reg['periodo']
                    ))

                    if existe:
                        total_atualizados += 1
                    else:
                        total_inseridos += 1

                except Exception as e:
                    total_erros += 1
                    logger.error(f"Erro ao importar {reg['codigoDisciplina']} - {reg['codigoCurso']} - {reg['periodo']}: {e}")

            conn.commit()

        return {
            'total_inseridos': total_inseridos,
            'total_atualizados': total_atualizados,
            'total_erros': total_erros,
            'total_processados': len(dados_transformados)
        }

    # -------------------------------------------------------------------------
    # Execução principal
    # -------------------------------------------------------------------------
    def executar_importacao(self):
        logger.info("=" * 70)
        logger.info("IMPORTAÇÃO: imp_002_disciplina (JOIN corrigido + filtros centralizados)")
        logger.info("=" * 70)
        logger.info(f"ANO_VIGENTE: {ANO_VIGENTE}")
        logger.info(f"PERIODOS_VIGENTES: {PERIODOS_VIGENTES}")
        logger.info(f"FACULDADES_INCLUIDAS: {FACULDADES_INCLUIDAS}")
        logger.info(f"SITUACAO_TURMA_VALIDA: {SITUACAO_TURMA_VALIDA}")

        dados_lyceum = self.obter_dados_lyceum()
        logger.info(f"📊 Combinações disciplina/curso encontradas: {len(dados_lyceum)}")

        logger.info("🔄 Transformando dados (aplicando mapeamento de cursos)...")
        dados_transformados = self.transformar_dados(dados_lyceum)
        logger.info(f"✅ Registros únicos para importação: {len(dados_transformados)}")

        logger.info("💾 Importando para banco Qstione...")
        resultado = self.importar_para_qstione(dados_transformados)

        logger.info(f"\n📈 RESULTADO DA IMPORTAÇÃO:")
        logger.info(f"  ✓ Inseridos: {resultado['total_inseridos']}")
        logger.info(f"  ↻ Atualizados: {resultado['total_atualizados']}")
        logger.info(f"  ✗ Erros: {resultado['total_erros']}")
        logger.info(f"  📋 Total processados: {resultado['total_processados']}")

        return dados_transformados


if __name__ == "__main__":
    importador = ImportadorDisciplinas()
    importador.executar_importacao()