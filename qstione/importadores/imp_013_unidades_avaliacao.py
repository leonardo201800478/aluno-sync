"""
qstione/importadores/imp_013_unidades_avaliacao.py
Importador para tabela imp_013_unidades_avaliacao (Unidades de Avaliação)
Baseado na tabela LY_PROVA do Lyceum.
Regras atualizadas e ajuste de tamanho de colunas.
"""

from core.database import get_db_connection, fetch_all
from qstione.core.transformacoes import truncar_texto, converter_inteiro, gerar_codigo_disciplina_curso
import logging

logger = logging.getLogger(__name__)


class ImportadorUnidadesAvaliacao:
    def __init__(self):
        pass

    MAPEAMENTO_PROVA = {
        'AVF': 'Avaliação Formativa',
        'AVS': 'Avaliação Somativa',
        'AVSB': 'Avaliação Substitutiva',
        'AVD1': 'Avaliação 1',
        'AVD2': 'Avaliação 2',
        'SUBST': 'Avaliação Substitutiva',
        'AV': 'Avaliação',
    }

    def _criar_tabela(self):
        """Cria a tabela com tamanhos adequados ou ajusta colunas existentes."""
        # Verifica se a tabela existe
        with get_db_connection(database_name='qstione') as conn:
            result = conn.execute("""
                SELECT 1 FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'imp_013_unidades_avaliacao'
            """).fetchone()

        if not result:
            # Criar tabela do zero
            create_sql = """
                CREATE TABLE imp_013_unidades_avaliacao (
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
            try:
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute(create_sql)
                    conn.commit()
                logger.info("✅ Tabela imp_013_unidades_avaliacao criada com tamanho NVARCHAR(200).")
            except Exception as e:
                logger.error(f"❌ Erro ao criar tabela: {e}")
                return
        else:
            # Tabela existe: ajustar tamanho das colunas se necessário
            self._ajustar_coluna('codigoUnidade', 'NVARCHAR(200)')
            self._ajustar_coluna('codigoAgrupamento', 'NVARCHAR(200)')
            # Garantir colunas de data
            self._adicionar_coluna_se_necessario('data_criacao', 'DATETIME2 DEFAULT GETDATE()')
            self._adicionar_coluna_se_necessario('data_atualizacao', 'DATETIME2 DEFAULT GETDATE()')

    def _ajustar_coluna(self, coluna, novo_tipo):
        """Ajusta o tipo da coluna se o tamanho atual for menor que o desejado."""
        check_sql = """
            SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = 'imp_013_unidades_avaliacao' AND COLUMN_NAME = ?
        """
        with get_db_connection(database_name='qstione') as conn:
            row = conn.execute(check_sql, (coluna,)).fetchone()
            if row:
                data_type, max_length = row
                # Se for NVARCHAR e o tamanho for menor que 200, alterar
                if data_type.upper() == 'NVARCHAR' and (max_length is None or max_length < 200):
                    alter_sql = f"ALTER TABLE imp_013_unidades_avaliacao ALTER COLUMN {coluna} {novo_tipo}"
                    try:
                        conn.execute(alter_sql)
                        conn.commit()
                        logger.info(f"✅ Coluna '{coluna}' alterada para {novo_tipo}.")
                    except Exception as e:
                        logger.error(f"❌ Erro ao alterar coluna '{coluna}': {e}")
                        # Se falhar, tentar recriar a tabela
                        logger.warning("⚠️ Tentando recriar a tabela com tamanho correto...")
                        self._recriar_tabela()

    def _recriar_tabela(self):
        """Recria a tabela do zero (drop + create)."""
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("DROP TABLE IF EXISTS imp_013_unidades_avaliacao")
                conn.commit()
            # Recriar com tamanhos adequados
            create_sql = """
                CREATE TABLE imp_013_unidades_avaliacao (
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
            with get_db_connection(database_name='qstione') as conn:
                conn.execute(create_sql)
                conn.commit()
            logger.info("✅ Tabela recriada com sucesso com NVARCHAR(200).")
        except Exception as e:
            logger.error(f"❌ Erro ao recriar tabela: {e}")
            raise

    def _adicionar_coluna_se_necessario(self, coluna, tipo):
        """Adiciona coluna se não existir."""
        check_sql = """
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'imp_013_unidades_avaliacao' AND COLUMN_NAME = ?
        """
        with get_db_connection(database_name='qstione') as conn:
            result = conn.execute(check_sql, (coluna,)).fetchone()
            if result[0] == 0:
                alter_sql = f"ALTER TABLE imp_013_unidades_avaliacao ADD {coluna} {tipo}"
                try:
                    conn.execute(alter_sql)
                    conn.commit()
                    logger.info(f"✅ Coluna '{coluna}' adicionada à tabela.")
                except Exception as e:
                    logger.error(f"❌ Erro ao adicionar coluna '{coluna}': {e}")

    def obter_dados_lyceum(self):
        sql = """
            SELECT 
                p.ano,
                p.disciplina,
                p.prova,
                p.semestre,
                p.turma,
                p.nome,
                p.ordem,
                p.classificacao,
                t.curso,
                c.nome AS nome_curso
            FROM LY_PROVA p
            INNER JOIN LY_TURMA t 
                ON t.ano = p.ano 
                AND t.semestre = p.semestre 
                AND t.turma = p.turma 
                AND t.disciplina = p.disciplina
            INNER JOIN LY_CURSO c ON c.curso = t.curso
            WHERE p.prova IS NOT NULL AND p.nome IS NOT NULL
              AND t.curso IS NOT NULL
            ORDER BY p.ano, p.semestre, p.turma, p.disciplina, p.prova
        """
        try:
            with get_db_connection(database_name='lyceum') as conn:
                rows = conn.execute(sql).fetchall()
                colunas = ['ano', 'disciplina', 'prova', 'semestre', 'turma', 
                           'nome', 'ordem', 'classificacao', 'curso', 'nome_curso']
                resultados = []
                for row in rows:
                    registro = {}
                    for i, col in enumerate(colunas):
                        registro[col] = row[i]
                    resultados.append(registro)
                logger.info(f"📊 LY_PROVA: {len(resultados)} registros encontrados (com curso).")
                return resultados
        except Exception as e:
            logger.error(f"❌ Erro ao buscar LY_PROVA: {e}")
            return []

    def _obter_nome_unidade(self, codigo_prova: str) -> str:
        return self.MAPEAMENTO_PROVA.get(codigo_prova, codigo_prova)

    def transformar_dados(self, dados_lyceum):
        dados_transformados = []
        for item in dados_lyceum:
            codigo_prova = item.get('prova', '').strip()
            disciplina = item.get('disciplina', '').strip()
            curso = item.get('curso', '').strip()
            nome_curso = item.get('nome_curso', '').strip()

            if not codigo_prova or not disciplina or not curso:
                logger.warning(f"Registro incompleto: {item}")
                continue

            try:
                codigo_disciplina = gerar_codigo_disciplina_curso(
                    disciplina,
                    nome_curso,
                    curso
                )
                codigo_disciplina = truncar_texto(codigo_disciplina, 30)
            except Exception as e:
                logger.error(f"Erro ao gerar codigoDisciplina para {disciplina}: {e}")
                codigo_disciplina = disciplina

            codigo_unidade = f"{codigo_disciplina}-{codigo_prova}"
            codigo_unidade = truncar_texto(codigo_unidade, 200)  # truncar para 200

            nome_unidade = self._obter_nome_unidade(codigo_prova)
            nome_unidade = truncar_texto(nome_unidade, 64)

            codigo_curso = truncar_texto(curso, 30)

            ordem_raw = item.get('ordem')
            if ordem_raw is not None:
                try:
                    ordem_exibicao = converter_inteiro(ordem_raw)
                except:
                    ordem_exibicao = 0
            else:
                ordem_exibicao = 0

            codigo_agrupamento = codigo_unidade  # mesmo valor

            registro = {
                'codigoUnidade': codigo_unidade,
                'nomeUnidade': nome_unidade,
                'codigoCurso': codigo_curso,
                'codigoDisciplina': codigo_disciplina,
                'ordemExibicao': ordem_exibicao,
                'codigoAgrupamento': codigo_agrupamento,
            }
            dados_transformados.append(registro)

        logger.info(f"✅ Transformados: {len(dados_transformados)} registros.")
        return dados_transformados

    def importar_para_qstione(self, dados_transformados):
        if not dados_transformados:
            logger.warning("Nenhum dado para importar.")
            return {
                'total_inseridos': 0,
                'total_atualizados': 0,
                'total_erros': 0,
                'total_processados': 0
            }

        self._criar_tabela()

        merge_sql = """
            MERGE INTO imp_013_unidades_avaliacao AS target
            USING (VALUES (?, ?, ?, ?, ?, ?)) AS source (
                codigoUnidade,
                nomeUnidade,
                codigoCurso,
                codigoDisciplina,
                ordemExibicao,
                codigoAgrupamento
            )
            ON target.codigoUnidade = source.codigoUnidade
            WHEN MATCHED THEN
                UPDATE SET
                    nomeUnidade = source.nomeUnidade,
                    codigoCurso = source.codigoCurso,
                    codigoDisciplina = source.codigoDisciplina,
                    ordemExibicao = source.ordemExibicao,
                    codigoAgrupamento = source.codigoAgrupamento,
                    data_atualizacao = GETDATE()
            WHEN NOT MATCHED THEN
                INSERT (
                    codigoUnidade,
                    nomeUnidade,
                    codigoCurso,
                    codigoDisciplina,
                    ordemExibicao,
                    codigoAgrupamento,
                    data_criacao,
                    data_atualizacao
                )
                VALUES (
                    source.codigoUnidade,
                    source.nomeUnidade,
                    source.codigoCurso,
                    source.codigoDisciplina,
                    source.ordemExibicao,
                    source.codigoAgrupamento,
                    GETDATE(),
                    GETDATE()
                );
        """

        inseridos = 0
        erros = 0

        try:
            with get_db_connection(database_name='qstione') as conn:
                for reg in dados_transformados:
                    try:
                        cursor = conn.cursor()
                        cursor.execute(merge_sql, (
                            reg['codigoUnidade'],
                            reg['nomeUnidade'],
                            reg['codigoCurso'],
                            reg['codigoDisciplina'],
                            reg['ordemExibicao'],
                            reg['codigoAgrupamento']
                        ))
                        inseridos += 1
                    except Exception as e:
                        logger.error(f"Erro ao importar registro {reg['codigoUnidade']}: {e}")
                        erros += 1
                conn.commit()
        except Exception as e:
            logger.error(f"Erro durante importação: {e}")
            erros += 1

        total_processados = len(dados_transformados)
        total_sucesso = total_processados - erros
        logger.info(f"📈 Importação concluída: {total_sucesso} sucessos, {erros} erros.")
        return {
            'total_inseridos': total_sucesso,
            'total_atualizados': 0,
            'total_erros': erros,
            'total_processados': total_processados
        }

    def executar_importacao(self):
        logger.info("=" * 70)
        logger.info("IMPORTAÇÃO: imp_013_unidades_avaliacao (LY_PROVA com regras atualizadas)")
        logger.info("=" * 70)

        dados_brutos = self.obter_dados_lyceum()
        logger.info(f"📊 Registros encontrados no Lyceum: {len(dados_brutos)}")

        dados_transformados = self.transformar_dados(dados_brutos)
        logger.info(f"✅ Registros transformados: {len(dados_transformados)}")

        resultado = self.importar_para_qstione(dados_transformados)

        logger.info(f"\n📈 RESULTADO DA IMPORTAÇÃO:")
        logger.info(f"  ✓ Inseridos (aprox.): {resultado['total_inseridos']}")
        logger.info(f"  ↻ Atualizados (aprox.): {resultado['total_atualizados']}")
        logger.info(f"  ✗ Erros: {resultado['total_erros']}")
        logger.info(f"  📋 Total processados: {resultado['total_processados']}")

        return dados_transformados


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    importador = ImportadorUnidadesAvaliacao()
    importador.executar_importacao()