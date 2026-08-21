"""
qstione/importadores/imp_006_usuarios.py
Importador para tabela imp_006_usuarios.

A população de docentes é determinada diretamente por LY_TURMA_DOCENTE.
Inclui diagnóstico detalhado para identificar por que um NUM_FUNC não chega
à relação final de usuários.
"""

import os
import sys
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.database import get_db_connection
from qstione.core.transformacoes import extrair_usuario_email, converter_minusculas, truncar_texto
from qstione.core.validacoes import validar_email, validar_matricula, validar_nome
from qstione.config.filtros import (
    ANO_VIGENTE,
    PERIODOS_VIGENTES,
    FACULDADES_INCLUIDAS,
    SITUACAO_TURMA_VALIDA,
)
from qstione.importadores.imp_002_disciplina import MAPEAMENTO_CURSOS


LOG_DIR = os.path.join(ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "imp_006_usuarios.log")

logger = logging.getLogger("imp_006_usuarios")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(file_handler)
logger.propagate = False

DEBUG_NUM_FUNC = "6980"


class ImportadorUsuarios:
    """Importa docentes elegíveis e registra detalhadamente os motivos de exclusão."""

    def __init__(self):
        self.periodos_placeholders = ','.join(['?'] * len(PERIODOS_VIGENTES))
        self.faculdades_placeholders = ','.join(['?'] * len(FACULDADES_INCLUIDAS))
        logger.info("=" * 90)
        logger.info("INÍCIO imp_006_usuarios | ANO=%s | PERIODOS=%s | FACULDADES=%s | DEBUG_NUM_FUNC=%s",
                    ANO_VIGENTE, PERIODOS_VIGENTES, FACULDADES_INCLUIDAS, DEBUG_NUM_FUNC)
        logger.info("LOG_FILE=%s", LOG_FILE)

    def _tabela_existe(self, nome_tabela: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("""
                    SELECT 1 FROM INFORMATION_SCHEMA.TABLES
                    WHERE TABLE_NAME = ? AND TABLE_TYPE = 'BASE TABLE'
                """, (nome_tabela,)).fetchone() is not None
        except Exception as e:
            logger.exception("Erro ao verificar existência da tabela %s", nome_tabela)
            return False

    def _indice_existe(self, nome_indice: str) -> bool:
        try:
            with get_db_connection(database_name='qstione') as conn:
                return conn.execute("SELECT 1 FROM sys.indexes WHERE name = ?", (nome_indice,)).fetchone() is not None
        except Exception:
            logger.exception("Erro ao verificar índice %s", nome_indice)
            return False

    def _criar_tabela(self):
        if self._tabela_existe('imp_006_usuarios'):
            return
        logger.info("Criando tabela imp_006_usuarios")
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("""
                    CREATE TABLE imp_006_usuarios (
                        matriculaUsuario NVARCHAR(20) NOT NULL,
                        codigoUsuario NVARCHAR(24) NULL,
                        emailUsuario NVARCHAR(100) NOT NULL,
                        nomeUsuario NVARCHAR(64) NOT NULL,
                        data_criacao DATETIME2 DEFAULT GETDATE(),
                        data_atualizacao DATETIME2 DEFAULT GETDATE(),
                        PRIMARY KEY (matriculaUsuario)
                    )
                """)
                conn.commit()
            if not self._indice_existe('idx_usuarios_email'):
                with get_db_connection(database_name='qstione') as conn:
                    conn.execute("CREATE INDEX idx_usuarios_email ON imp_006_usuarios(emailUsuario)")
                    conn.commit()
        except Exception:
            logger.exception("Erro ao criar tabela/índice")

    @staticmethod
    def _curso_unificado(curso):
        if curso is None or str(curso).strip() == '':
            return '999'
        curso = str(curso).strip()
        return MAPEAMENTO_CURSOS.get(curso, (curso, curso))[0]

    def _diagnosticar_num_func(self, conn):
        """Executa uma investigação completa do NUM_FUNC configurado."""
        nf = DEBUG_NUM_FUNC
        logger.info("===== DIAGNÓSTICO ESPECÍFICO NUM_FUNC=%s =====", nf)

        queries = {
            "1_td_ano_periodo": ("""
                SELECT td.ano, td.periodo, td.turma, td.disciplina, td.num_func
                FROM LY_TURMA_DOCENTE td
                WHERE td.num_func = ?
                ORDER BY td.ano, td.periodo, td.turma, td.disciplina
            """, (nf,)),
            "2_td_periodo_vigente": (f"""
                SELECT td.ano, td.periodo, td.turma, td.disciplina, td.num_func
                FROM LY_TURMA_DOCENTE td
                WHERE td.num_func = ?
                  AND td.ano = ?
                  AND td.periodo IN ({self.periodos_placeholders})
                ORDER BY td.ano, td.periodo, td.turma, td.disciplina
            """, (nf, ANO_VIGENTE, *PERIODOS_VIGENTES)),
            "3_td_com_turma": (f"""
                SELECT td.ano, td.periodo, td.turma, td.disciplina, td.num_func,
                       t.curso, t.sit_turma
                FROM LY_TURMA_DOCENTE td
                LEFT JOIN LY_TURMA t
                  ON t.ano = td.ano
                 AND t.semestre = td.periodo
                 AND t.turma = td.turma
                 AND t.disciplina = td.disciplina
                WHERE td.num_func = ?
                  AND td.ano = ?
                  AND td.periodo IN ({self.periodos_placeholders})
                ORDER BY td.ano, td.periodo, td.turma, td.disciplina
            """, (nf, ANO_VIGENTE, *PERIODOS_VIGENTES)),
            "4_turma_com_faculdade": (f"""
                SELECT td.ano, td.periodo, td.turma, td.disciplina, td.num_func,
                       t.curso, t.sit_turma, c.faculdade
                FROM LY_TURMA_DOCENTE td
                LEFT JOIN LY_TURMA t
                  ON t.ano = td.ano
                 AND t.semestre = td.periodo
                 AND t.turma = td.turma
                 AND t.disciplina = td.disciplina
                LEFT JOIN LY_CURSO c ON c.curso = t.curso
                WHERE td.num_func = ?
                  AND td.ano = ?
                  AND td.periodo IN ({self.periodos_placeholders})
                ORDER BY td.ano, td.periodo, td.turma, td.disciplina
            """, (nf, ANO_VIGENTE, *PERIODOS_VIGENTES)),
            "5_docente": ("""
                SELECT d.num_func, d.matricula, d.mailbox, d.nome_social, d.nome_compl, d.ativo
                FROM LY_DOCENTE d
                WHERE d.num_func = ?
            """, (nf,)),
        }

        for nome, (sql, params) in queries.items():
            try:
                rows = conn.execute(sql, params).fetchall()
                logger.info("[%s] quantidade=%d", nome, len(rows))
                for row in rows:
                    logger.info("[%s] %s", nome, row)
            except Exception:
                logger.exception("[%s] ERRO", nome)

        logger.info("===== FIM DIAGNÓSTICO NUM_FUNC=%s =====", nf)

    def obter_dados_lyceum(self):
        query = f"""
            SELECT DISTINCT
                td.num_func, d.matricula, d.mailbox,
                COALESCE(d.nome_social, d.nome_compl) AS nome_completo,
                d.cpf, t.curso
            FROM LY_TURMA_DOCENTE td
            INNER JOIN LY_TURMA t
                ON t.ano = td.ano
               AND t.semestre = td.periodo
               AND t.turma = td.turma
               AND t.disciplina = td.disciplina
            LEFT JOIN LY_CURSO c ON c.curso = t.curso
            INNER JOIN LY_DOCENTE d ON d.num_func = td.num_func
            WHERE td.ano = ?
              AND td.periodo IN ({self.periodos_placeholders})
              AND t.sit_turma = ?
              AND (t.curso IS NULL OR c.faculdade IN ({self.faculdades_placeholders}))
              AND d.ativo = 'S'
              AND d.mailbox IS NOT NULL
              AND LTRIM(RTRIM(d.mailbox)) <> ''
            ORDER BY td.num_func, d.matricula
        """
        params = (ANO_VIGENTE, *PERIODOS_VIGENTES, SITUACAO_TURMA_VALIDA, *FACULDADES_INCLUIDAS)
        with get_db_connection() as conn:
            self._diagnosticar_num_func(conn)
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            logger.info("CONSULTA FINAL: %d linhas retornadas", len(rows))
            debug_rows = [r for r in rows if str(r[0]).strip() == DEBUG_NUM_FUNC]
            logger.info("CONSULTA FINAL NUM_FUNC=%s: %d linhas", DEBUG_NUM_FUNC, len(debug_rows))
            for row in debug_rows:
                logger.info("CONSULTA FINAL NUM_FUNC=%s ROW=%s", DEBUG_NUM_FUNC, row)
            return rows

    def transformar_dados(self, dados_lyceum):
        registros = {}
        for num_func, matricula, email, nome, cpf, curso in dados_lyceum:
            nf = str(num_func).strip()
            if nf == DEBUG_NUM_FUNC:
                logger.info("TRANSFORMANDO NUM_FUNC=%s | matricula=%s | email=%s | nome=%s | curso=%s",
                            nf, matricula, email, nome, curso)
            if not validar_matricula(matricula):
                if nf == DEBUG_NUM_FUNC: logger.warning("EXCLUIDO NUM_FUNC=%s: matrícula inválida (%r)", nf, matricula)
                continue
            if not validar_email(email):
                if nf == DEBUG_NUM_FUNC: logger.warning("EXCLUIDO NUM_FUNC=%s: email inválido (%r)", nf, email)
                continue
            if not validar_nome(nome):
                if nf == DEBUG_NUM_FUNC: logger.warning("EXCLUIDO NUM_FUNC=%s: nome inválido (%r)", nf, nome)
                continue
            email_final = converter_minusculas(email)[:100]
            codigo_usuario = extrair_usuario_email(email)
            matricula_final = str(matricula)[:20]
            if matricula_final not in registros:
                registros[matricula_final] = {
                    'matriculaUsuario': matricula_final,
                    'codigoUsuario': codigo_usuario[:24] if codigo_usuario else None,
                    'emailUsuario': email_final,
                    'nomeUsuario': truncar_texto(nome, 64),
                }
                if nf == DEBUG_NUM_FUNC:
                    logger.info("INCLUÍDO NUM_FUNC=%s como matrícula=%s", nf, matricula_final)
            elif nf == DEBUG_NUM_FUNC:
                logger.info("NUM_FUNC=%s já representado pela matrícula=%s", nf, matricula_final)
        logger.info("TRANSFORMAÇÃO FINAL: %d usuários únicos", len(registros))
        return list(registros.values())

    def importar_para_qstione(self, dados_transformados):
        self._criar_tabela()
        inseridos = erros = 0
        try:
            with get_db_connection(database_name='qstione') as conn:
                conn.execute("DELETE FROM imp_006_usuarios")
                cursor = conn.cursor()
                for reg in dados_transformados:
                    try:
                        cursor.execute("""
                            INSERT INTO imp_006_usuarios
                            (matriculaUsuario, codigoUsuario, emailUsuario, nomeUsuario, data_criacao, data_atualizacao)
                            VALUES (?, ?, ?, ?, GETDATE(), GETDATE())
                        """, (reg['matriculaUsuario'], reg['codigoUsuario'], reg['emailUsuario'], reg['nomeUsuario']))
                        inseridos += 1
                    except Exception as e:
                        erros += 1
                        logger.exception("Erro ao importar matrícula=%s", reg['matriculaUsuario'])
                conn.commit()
        except Exception:
            logger.exception("Erro durante reconstrução da tabela")
            return {'total_inseridos': 0, 'total_atualizados': 0, 'total_erros': len(dados_transformados), 'total_processados': len(dados_transformados)}
        return {'total_inseridos': inseridos, 'total_atualizados': 0, 'total_erros': erros, 'total_processados': len(dados_transformados)}

    def executar_importacao(self):
        print("=" * 70)
        print("IMPORTAÇÃO: imp_006_usuarios")
        print("=" * 70)
        print(f"🎓 Docentes por LY_TURMA_DOCENTE: ano={ANO_VIGENTE}, períodos={PERIODOS_VIGENTES}, faculdades={FACULDADES_INCLUIDAS}")
        print(f"🔎 Log detalhado: {LOG_FILE}")
        dados = self.obter_dados_lyceum()
        num_funcs = {str(row[0]).strip() for row in dados if row[0] is not None}
        print(f"📊 Registros de vínculos encontrados: {len(dados)}")
        print(f"👨‍🏫 NUM_FUNC únicos elegíveis: {len(num_funcs)}")
        print(f"🔎 NUM_FUNC {DEBUG_NUM_FUNC} na consulta final: {'SIM' if DEBUG_NUM_FUNC in num_funcs else 'NÃO'}")
        transformados = self.transformar_dados(dados)
        print(f"✅ Usuários únicos válidos: {len(transformados)}")
        resultado = self.importar_para_qstione(transformados)
        print(f"📈 Inseridos: {resultado['total_inseridos']} | Erros: {resultado['total_erros']}")
        logger.info("FIM imp_006_usuarios")
        return transformados


if __name__ == "__main__":
    ImportadorUsuarios().executar_importacao()
