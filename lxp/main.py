# lxp/main.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import logger
from lxp.exportadores import exp_001_cursos, exp_002_curriculum, exp_003_enrollment, exp_004_desenturmar_alunos_cursos_livres_ead
import sync.sync_ly_alunos
from models.ly_aluno import AlunoModel

EXPORTADORES = [
    ("Cursos", exp_001_cursos),
    ("Currículos", exp_002_curriculum),
    ("Enturmações", exp_003_enrollment),
    ("Desenturmações (delete)", exp_004_desenturmar_alunos_cursos_livres_ead),
]

def run() -> bool:
    logger.info("=== INÍCIO DA EXPORTAÇÃO LXP ===")
    
    # Etapa 1: Sincronizar alunos via API Lyceum
    logger.info("Executando sincronização de alunos (sync_ly_alunos)...")
    try:
        if not sync.sync_ly_alunos.run():
            logger.error("Sincronização de alunos falhou. Abortando exportação LXP.")
            return False
        logger.info("Sincronização de alunos concluída com sucesso.")
    except Exception as e:
        logger.exception(f"Erro crítico ao executar sync_ly_alunos: {e}")
        return False

    # Verifica se a tabela tem registros
    logger.info("Verificando quantidade de registros na tabela LY_ALUNO...")
    try:
        total_alunos = len(AlunoModel.get_all_matriculas())
        logger.info(f"Total de registros na tabela LY_ALUNO: {total_alunos}")
        if total_alunos == 0:
            logger.error("Tabela LY_ALUNO está vazia. Abortando exportação para evitar arquivos vazios.")
            return False
    except Exception as e:
        logger.error(f"Erro ao contar registros: {e}")
        return False

    # Etapa 2: Executar os exportadores LXP
    sucesso = True
    for nome, modulo in EXPORTADORES:
        try:
            logger.info(f"Executando exportador: {nome}")
            if not modulo.run():
                logger.error(f"Exportador {nome} falhou.")
                sucesso = False
        except Exception as e:
            logger.exception(f"Erro crítico no exportador {nome}: {e}")
            sucesso = False

    if sucesso:
        logger.info("=== EXPORTAÇÃO LXP CONCLUÍDA ===")
    else:
        logger.error("=== EXPORTAÇÃO LXP FINALIZOU COM FALHAS ===")
    return sucesso

if __name__ == "__main__":
    sys.exit(0 if run() else 1)