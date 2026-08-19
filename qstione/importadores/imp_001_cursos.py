# qstione/importadores/imp_001_cursos.py
import sys
import os

# Adiciona o diretório raiz do projeto (aluno-sync) ao sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.database import get_db_connection
from qstione.core.transformacoes import (
    valor_fixo_4000000001,
    truncar_texto
)
from qstione.core.validacoes import (
    validar_codigo_curso,
    validar_nome_curso,
    validar_quant_periodos
)

# =============================================================================
# MAPEAMENTO DE CURSOS – UNIFICAÇÃO DE CÓDIGOS (mesmo do importador de disciplinas)
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
    '999': ('999', 'COMPARTILHADA'),  # (não usado aqui, mas mantido por consistência)
}


class ImportadorCursos:

    def __init__(self):
        pass

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
            print(f"  ⚠️  Erro ao verificar existência da tabela: {e}")
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,))
                return cursor.fetchone() is not None
        except Exception as e:
            print(f"  ⚠️  Erro ao verificar índice: {e}")
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_001_cursos'):
            print("✅ Tabela imp_001_cursos já existe.")
            return

        print("🆕 Criando tabela imp_001_cursos...")
        create_sql = """
            CREATE TABLE imp_001_cursos (
                codigoCurso NVARCHAR(30) NOT NULL,
                nomeCurso NVARCHAR(64) NOT NULL,
                quantPeriodos INTEGER NOT NULL,
                codigoUnidadeOrganizacional NVARCHAR(30) NOT NULL,
                data_criacao DATETIME2 DEFAULT GETDATE(),
                data_atualizacao DATETIME2 DEFAULT GETDATE(),
                PRIMARY KEY (codigoCurso)
            )
        """
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute(create_sql)
                conn.commit()
            print("✅ Tabela criada.")
        except Exception as e:
            print(f"❌ Erro ao criar tabela: {e}")
            return

        if not self._indice_existe('idx_cursos_nome'):
            try:
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute("CREATE INDEX idx_cursos_nome ON imp_001_cursos(nomeCurso)")
                    conn.commit()
                print("✅ Índice criado.")
            except Exception as e:
                print(f"⚠️ Índice não pôde ser criado: {e}")

    def obter_dados_lyceum(self):
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT
                    c.curso,
                    c.nome,
                    cr.prazo_ideal
                FROM LY_CURSO c
                INNER JOIN (
                    SELECT
                        curso,
                        MAX(curriculo) AS curriculo
                    FROM LY_CURRICULO
                    GROUP BY curso
                ) mc
                    ON mc.curso = c.curso
                INNER JOIN LY_CURRICULO cr
                    ON cr.curso = mc.curso
                   AND cr.curriculo = mc.curriculo
                WHERE c.ativo = 'S'
                  AND c.faculdade IN ('001')
            """
            cursor.execute(query)
            return cursor.fetchall()

    def transformar_dados(self, dados_lyceum):
        # Dicionário para agrupar por código unificado
        cursos_agrupados = {}

        for registro in dados_lyceum:
            curso_original, nome_original, prazo_ideal = registro

            # Aplica mapeamento (de-para)
            if curso_original in MAPEAMENTO_CURSOS:
                curso_unificado, nome_unificado = MAPEAMENTO_CURSOS[curso_original]
            else:
                curso_unificado = curso_original
                nome_unificado = nome_original  # fallback (será truncado depois)

            # Agrupa pelo código unificado
            if curso_unificado not in cursos_agrupados:
                cursos_agrupados[curso_unificado] = {
                    'nome': nome_unificado,
                    'prazo_maximo': prazo_ideal,
                    'quantidade': 0
                }
            else:
                # Atualiza o nome para o nome do mapeamento (se houver)
                # Caso o mapeamento forneça nome, ele tem prioridade
                if curso_original in MAPEAMENTO_CURSOS:
                    cursos_agrupados[curso_unificado]['nome'] = nome_unificado
                # Atualiza o maior prazo (se o novo for maior)
                if prazo_ideal is not None:
                    if (cursos_agrupados[curso_unificado]['prazo_maximo'] is None or
                        prazo_ideal > cursos_agrupados[curso_unificado]['prazo_maximo']):
                        cursos_agrupados[curso_unificado]['prazo_maximo'] = prazo_ideal
            cursos_agrupados[curso_unificado]['quantidade'] += 1

        # Agora transforma cada grupo em um registro final
        dados_transformados = []
        for codigo, info in cursos_agrupados.items():
            nome_curso = info['nome']
            prazo = info['prazo_maximo']

            # Trunca nome para 64 caracteres
            nome_curso_truncado = truncar_texto(nome_curso, 64)

            if not validar_codigo_curso(codigo):
                print(f"  ⚠️  Código do curso inválido: {codigo}")
                continue

            if not validar_nome_curso(nome_curso_truncado):
                print(f"  ⚠️  Nome do curso inválido após truncagem: {nome_curso_truncado}")
                continue

            quant_periodos = validar_quant_periodos(prazo)
            if quant_periodos is None:
                print(f"  ⚠️  Quantidade de períodos inválida: {prazo} para o curso {codigo}")
                continue

            codigo_unidade = valor_fixo_4000000001(None)

            dados_transformados.append({
                'codigoCurso': str(codigo)[:30],
                'nomeCurso': nome_curso_truncado,
                'quantPeriodos': quant_periodos,
                'codigoUnidadeOrganizacional': codigo_unidade
            })

        return dados_transformados

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        merge_sql = """
            MERGE INTO imp_001_cursos AS target
            USING (VALUES (?, ?, ?, ?)) AS source (codigoCurso, nomeCurso, quantPeriodos, codigoUnidadeOrganizacional)
            ON target.codigoCurso = source.codigoCurso
            WHEN MATCHED THEN
                UPDATE SET
                    nomeCurso = source.nomeCurso,
                    quantPeriodos = source.quantPeriodos,
                    codigoUnidadeOrganizacional = source.codigoUnidadeOrganizacional,
                    data_atualizacao = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (codigoCurso, nomeCurso, quantPeriodos, codigoUnidadeOrganizacional, data_criacao, data_atualizacao)
                VALUES (source.codigoCurso, source.nomeCurso, source.quantPeriodos, source.codigoUnidadeOrganizacional, GETDATE(), GETDATE());
        """
        total_inseridos = 0
        total_atualizados = 0
        total_erros = 0

        with get_db_connection(database_name='qstione') as conn:
            cursor = conn.cursor()
            for reg in dados_transformados:
                try:
                    cursor.execute("SELECT codigoCurso FROM imp_001_cursos WHERE codigoCurso = ?", (reg['codigoCurso'],))
                    existe = cursor.fetchone()
                    cursor.execute(merge_sql, (
                        reg['codigoCurso'],
                        reg['nomeCurso'],
                        reg['quantPeriodos'],
                        reg['codigoUnidadeOrganizacional']
                    ))
                    if existe:
                        total_atualizados += 1
                    else:
                        total_inseridos += 1
                except Exception as e:
                    total_erros += 1
                    print(f"  ✗  Erro ao importar {reg['codigoCurso']}: {e}")
            conn.commit()

        return {
            'total_inseridos': total_inseridos,
            'total_atualizados': total_atualizados,
            'total_erros': total_erros,
            'total_processados': len(dados_transformados)
        }

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_001_cursos (com mapeamento unificado)")
        print("=" * 70)

        dados_lyceum = self.obter_dados_lyceum()
        print(f"📊 Registros encontrados no Lyceum: {len(dados_lyceum)}")

        print("🔄 Transformando dados (aplicando mapeamento de cursos)...")
        dados_transformados = self.transformar_dados(dados_lyceum)
        print(f"✅ Registros únicos (após unificação) para importação: {len(dados_transformados)}")

        print("💾 Importando para Qstione...")
        resultado = self.importar_para_qstione(dados_transformados)

        print(f"\n📈 RESULTADO DA IMPORTAÇÃO:")
        print(f"  ✓ Inseridos: {resultado['total_inseridos']}")
        print(f"  ↻ Atualizados: {resultado['total_atualizados']}")
        print(f"  ✗ Erros: {resultado['total_erros']}")
        print(f"  📋 Total processados: {resultado['total_processados']}")

        return dados_transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    importador = ImportadorCursos()
    importador.executar_importacao()