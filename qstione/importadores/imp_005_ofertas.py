"""
qstione/importadores/imp_005_ofertas.py
Importador independente de ofertas.

A regra de curso e de codigoDisciplina é a mesma do imp_002_disciplina.py:
MAPEAMENTO_CURSOS -> curso unificado + nome do curso unificado ->
gerar_codigo_disciplina_curso().
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.config.filtros import ANO_VIGENTE, PERIODOS_VIGENTES, FACULDADES_INCLUIDAS, AREAS_CONHECIMENTO_INCLUIDAS, SITUACAO_TURMA_VALIDA
from qstione.core.transformacoes import gerar_codigo_oferta, gerar_codigo_tipo_oferta, gerar_codigo_disciplina_curso, mapear_turno, valor_fixo_2026_2, valor_fixo_vazio, truncar_texto
from qstione.core.validacoes import validar_codigo_disciplina, validar_nome_disciplina
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


class ImportadorOfertas:
    """Importa ofertas preservando a mesma identificação de disciplinas do imp_002."""

    @staticmethod
    def _normalizar_curso(curso, nome_curso=None):
        curso = str(curso).strip() if curso is not None else ''
        if curso in MAPEAMENTO_CURSOS:
            return MAPEAMENTO_CURSOS[curso][0], MAPEAMENTO_CURSOS[curso][1]
        return curso, (str(nome_curso).strip() if nome_curso else curso)

    def _tabela_existe(self):
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = 'imp_005_ofertas' AND TABLE_TYPE = 'BASE TABLE'
                """).fetchone() is not None
        except Exception:
            return False

    def _indice_existe(self, nome):
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute('SELECT 1 FROM sys.indexes WHERE name = ?', (nome,)).fetchone() is not None
        except Exception:
            return False

    def _criar_tabela(self):
        if not self._tabela_existe():
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_005_ofertas (
                        codigoOferta NVARCHAR(30) NOT NULL,
                        nomeOferta NVARCHAR(100) NOT NULL,
                        codigoDisciplina NVARCHAR(30) NOT NULL,
                        semestreOferta NVARCHAR(6) NOT NULL,
                        codigoTipoOferta NVARCHAR(3) NOT NULL,
                        codigoOfertaOrigem NVARCHAR(30) NULL,
                        turno NVARCHAR(1) NULL,
                        codigoIdentificacaoAVA NVARCHAR(100) NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (codigoOferta)
                    )
                """)
                conn.commit()
                print('🆕 Tabela imp_005_ofertas criada.')

        for nome, sql in [
            ('idx_ofertas_disciplina', 'CREATE INDEX idx_ofertas_disciplina ON imp_005_ofertas(codigoDisciplina)'),
            ('idx_ofertas_tipo', 'CREATE INDEX idx_ofertas_tipo ON imp_005_ofertas(codigoTipoOferta)'),
        ]:
            if not self._indice_existe(nome):
                try:
                    with get_db_connection(database_name='qstione') as conn:
                        conn.execute(sql)
                        conn.commit()
                except Exception as e:
                    print(f'⚠️ Índice {nome}: {e}')

    def _coluna_existe(self, tabela, coluna):
        try:
            with get_db_connection() as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
                """, (tabela, coluna)).fetchone() is not None
        except Exception:
            return False

    def obter_dados_lyceum(self):
        areas = [a for a in AREAS_CONHECIMENTO_INCLUIDAS if a is not None]
        areas_sql = ','.join('?' for _ in areas)
        periodos_sql = ','.join('?' for _ in PERIODOS_VIGENTES)
        faculdades_sql = ','.join('?' for _ in FACULDADES_INCLUIDAS)

        with get_db_connection() as conn:
            if self._coluna_existe('LY_TURMA', 'curso'):
                curso_select = 't.curso'
                curso_join = 'c.curso = t.curso'
            elif self._coluna_existe('LY_DISCIPLINA', 'curso'):
                curso_select = 'd.curso'
                curso_join = 'c.curso = d.curso'
            else:
                curso_select = 'g.curso'
                curso_join = 'c.curso = g.curso'

            join_grade = '' if self._coluna_existe('LY_TURMA', 'curso') or self._coluna_existe('LY_DISCIPLINA', 'curso') else 'INNER JOIN LY_GRADE g ON g.disciplina = t.disciplina'
            query = f"""
                SELECT t.disciplina, t.turma, t.ano, t.semestre, t.turno,
                       d.nome_compl, {curso_select} AS codigo_curso, c.nome AS nome_curso,
                       d.area_conhecimento
                FROM LY_TURMA t
                INNER JOIN LY_DISCIPLINA d ON d.disciplina = t.disciplina
                {join_grade}
                INNER JOIN LY_CURSO c ON {curso_join}
                WHERE t.ano = ?
                  AND t.semestre IN ({periodos_sql})
                  AND t.sit_turma = ?
                  AND d.faculdade IN ({faculdades_sql})
                  AND (d.area_conhecimento IN ({areas_sql}) OR d.area_conhecimento IS NULL)
                ORDER BY t.disciplina, t.turma
            """
            params = [ANO_VIGENTE, *PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA, *FACULDADES_INCLUIDAS, *areas]
            return conn.execute(query, params).fetchall()

    def obter_turmas_regulares(self):
        """
        Retorna um dicionário com chave (disciplina, ano, semestre, curso_unificado)
        e valor = lista de códigos de turmas T0* (regulares) para aquela combinação.
        O curso é normalizado para o unificado, garantindo a correspondência correta.
        """
        periodos_sql = ','.join('?' for _ in PERIODOS_VIGENTES)
        faculdades_sql = ','.join('?' for _ in FACULDADES_INCLUIDAS)
        with get_db_connection() as conn:
            if self._coluna_existe('LY_TURMA', 'curso'):
                curso = 't.curso'
                join_curso = 'c.curso = t.curso'
            else:
                curso = 'g.curso'
                join_curso = 'c.curso = g.curso'
            grade = '' if self._coluna_existe('LY_TURMA', 'curso') else 'INNER JOIN LY_GRADE g ON g.disciplina = t.disciplina'
            rows = conn.execute(f"""
                SELECT t.disciplina, t.turma, t.ano, t.semestre, {curso}
                FROM LY_TURMA t
                INNER JOIN LY_DISCIPLINA d ON d.disciplina = t.disciplina
                {grade}
                INNER JOIN LY_CURSO c ON {join_curso}
                WHERE t.ano = ? AND t.semestre IN ({periodos_sql})
                  AND t.sit_turma = ? AND t.turma LIKE 'T0%'
                  AND d.faculdade IN ({faculdades_sql})
            """, [ANO_VIGENTE, *PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA, *FACULDADES_INCLUIDAS]).fetchall()
        result = {}
        for disciplina, turma, ano, semestre, curso_original in rows:
            # Normaliza o curso da turma regular
            curso_unificado, _ = self._normalizar_curso(curso_original)
            chave = (disciplina, ano, semestre, curso_unificado)
            result.setdefault(chave, []).append(turma)
        return result

    def obter_curso_para_disciplina(self, disciplina):
        try:
            with get_db_connection() as conn:
                row = conn.execute("""
                    SELECT TOP 1 g.curso, c.nome
                    FROM LY_GRADE g INNER JOIN LY_CURSO c ON c.curso = g.curso
                    WHERE g.disciplina = ?
                """, (disciplina,)).fetchone()
                return row if row else (None, None)
        except Exception:
            return None, None

    def transformar_dados(self, dados_lyceum):
        turmas_regulares = self.obter_turmas_regulares()
        dados = []
        for registro in dados_lyceum:
            disciplina, turma, ano, semestre, turno, nome_compl, curso, nome_curso, _ = registro
            if not validar_codigo_disciplina(disciplina):
                continue
            nome_disciplina = validar_nome_disciplina(nome_compl)
            if nome_disciplina is None:
                nome_disciplina = truncar_texto(nome_compl, 100)
            if not nome_disciplina:
                continue

            curso_unificado, nome_curso_unificado = self._normalizar_curso(curso, nome_curso)
            # Mesma composição do imp_002: disciplina original + nome do curso unificado + ID unificado.
            codigo_disciplina = truncar_texto(
                gerar_codigo_disciplina_curso(disciplina, nome_curso_unificado, curso_unificado), 30
            )

            codigo_oferta = truncar_texto(gerar_codigo_oferta(disciplina, turma, ano, semestre), 30)
            tipo = truncar_texto(gerar_codigo_tipo_oferta(turma), 3)
            origem = ''

            # Se for REC ou REP, tenta encontrar uma turma regular de origem
            if tipo in ('REC', 'REP'):
                chave = (disciplina, ano, semestre, curso_unificado)
                for turma_regular in turmas_regulares.get(chave, []):
                    origem = gerar_codigo_oferta(disciplina, turma_regular, ano, semestre)
                    break
                # === NOVA REGRA: se não encontrou origem, o tipo passa a ser REG ===
                if not origem:
                    tipo = 'REG'

            # ========== CORREÇÃO DO TURNO ==========
            turno_mapeado = mapear_turno(turno)
            turnos_validos = ('M', 'T', 'N', 'I')
            if turno_mapeado not in turnos_validos:
                turno_mapeado = 'M'
            # ======================================

            dados.append({
                'codigoOferta': codigo_oferta,
                'nomeOferta': truncar_texto(turma, 100),
                'codigoDisciplina': codigo_disciplina,
                'semestreOferta': truncar_texto(valor_fixo_2026_2(None), 6),
                'codigoTipoOferta': tipo,
                'codigoOfertaOrigem': truncar_texto(origem, 30) or '',
                'turno': truncar_texto(turno_mapeado, 1) or '',
                'codigoIdentificacaoAVA': truncar_texto(valor_fixo_vazio(None), 100) or '',
            })
        # A PK é codigoOferta; em caso de duplicidade, conserva o primeiro registro.
        unicos = {}
        for reg in dados:
            unicos[reg['codigoOferta']] = reg
        return list(unicos.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute('DELETE FROM imp_005_ofertas')
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_005_ofertas
                            (codigoOferta, nomeOferta, codigoDisciplina, semestreOferta,
                             codigoTipoOferta, codigoOfertaOrigem, turno, codigoIdentificacaoAVA,
                             data_criacao, data_atualizacao)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), GETDATE())
                        """, (
                            reg['codigoOferta'],
                            reg['nomeOferta'],
                            reg['codigoDisciplina'],
                            reg['semestreOferta'],
                            reg['codigoTipoOferta'],
                            reg['codigoOfertaOrigem'] or '',
                            reg['turno'] or '',
                            reg['codigoIdentificacaoAVA'] or ''
                        ))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        print(f"✗ {reg['codigoOferta']}: {e}")
                conn.commit()
        except Exception as e:
            print(f'❌ Erro durante reconstrução: {e}')
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print('=' * 70)
        print('IMPORTAÇÃO: imp_005_ofertas')
        print('=' * 70)
        dados = self.obter_dados_lyceum()
        print(f'📊 Registros encontrados: {len(dados)}')
        transformados = self.transformar_dados(dados)
        print(f'✅ Registros únicos: {len(transformados)}')
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        return transformados


if __name__ == '__main__':
    ImportadorOfertas().executar_importacao()