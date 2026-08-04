#!/usr/bin/env python3
"""
sync/sync_ly_pessoa_by_id.py

Sincronização de pessoas pendentes usando o novo endpoint específico:
/v2/pessoas/idPessoa/{idPessoa}/obterPessoa

Características:
- Busca IDs de alunos que não estão em LY_PESSOA (via LY_ALUNO)
- Consulta a API para cada ID individualmente
- Insere/atualiza a pessoa no banco local
- Opcionalmente busca alunos associados (endpoint antigo, mantido)
- Processamento em lotes de 100 com commit parcial
"""

import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.api_client import get_pessoa_client, get_aluno_client
from core.database import fetch_one, get_db_connection
from core.logger import logger
from models.ly_pessoa import LyPessoaModel
from models.ly_aluno import AlunoModel
from core.config import config


def pessoa_existe_no_banco(cod_pessoa: int) -> bool:
    """Verifica se a pessoa já existe na tabela LY_PESSOA pela chave 'pessoa'."""
    query = "SELECT 1 FROM LY_PESSOA WHERE pessoa = ?"
    result = fetch_one(query, (cod_pessoa,), database_name='lyceum')
    return result is not None


def buscar_e_salvar_pessoa_por_id(cod_pessoa: int, buscar_alunos: bool = True) -> Optional[Dict[str, Any]]:
    """
    1. Verifica se a pessoa já existe no banco local.
    2. Se não existir, consulta a API Lyceum via endpoint específico.
    3. Insere os dados na tabela LY_PESSOA usando LyPessoaModel.upsert().
    4. Opcionalmente, busca os alunos associados (endpoint /pessoas/{codPessoa}/alunos)
       e insere em LY_ALUNO usando AlunoModel.upsert().
    """
    # 1. Verificar existência local
    if pessoa_existe_no_banco(cod_pessoa):
        logger.info(f"Pessoa {cod_pessoa} já existe no banco local.")
        return {"status": "existente", "codPessoa": cod_pessoa}

    logger.info(f"Pessoa {cod_pessoa} não encontrada localmente. Consultando API Lyceum...")

    pessoa_client = get_pessoa_client()
    try:
        # 2. Buscar dados da pessoa pelo ID usando o novo endpoint
        dados_pessoa = pessoa_client.get_pessoa_detalhada(cod_pessoa)
        if not dados_pessoa:
            logger.error(f"Pessoa {cod_pessoa} não encontrada na API.")
            return None

        logger.info(f"Dados da pessoa {cod_pessoa} obtidos da API. Inserindo no banco...")

        # 3. Inserir/atualizar a pessoa usando o modelo
        if not LyPessoaModel.upsert(dados_pessoa):
            logger.error(f"Falha ao inserir/atualizar pessoa {cod_pessoa}.")
            return None

        logger.info(f"Pessoa {cod_pessoa} inserida/atualizada com sucesso.")

        # 4. (Opcional) Buscar alunos relacionados - mantido do código original
        alunos_inseridos = []
        if buscar_alunos:
            aluno_client = get_aluno_client()
            try:
                endpoint_alunos = f"/pessoas/{cod_pessoa}/alunos"
                alunos = aluno_client.get(endpoint_alunos)
                if alunos and isinstance(alunos, list):
                    logger.info(f"Encontrados {len(alunos)} alunos para a pessoa {cod_pessoa}. Inserindo/atualizando...")
                    for aluno_data in alunos:
                        aluno_adaptado = {
                            'aluno': aluno_data.get('codAluno'),
                            'pessoa': aluno_data.get('codPessoa'),
                            'nome_compl': aluno_data.get('nomeAluno'),
                            'nome_abrev': aluno_data.get('nomeAbrev'),
                            'nome_social': aluno_data.get('nomeSocial'),
                            'curso': aluno_data.get('codCurso'),
                            'turno': aluno_data.get('turno'),
                            'serie': aluno_data.get('serie'),
                            'unidade_fisica': aluno_data.get('unidadeFisica'),
                            'unidade_ensino': aluno_data.get('unidadeEnsino'),
                            'sit_aluno': aluno_data.get('situacaoAluno'),
                            'stamp_atualizacao': aluno_data.get('stampAtualizacao'),
                            'dt_ingresso': aluno_data.get('dtIngresso'),
                            'e_mail_interno': aluno_data.get('eMailInterno'),
                            'num_chamada': aluno_data.get('numChamada'),
                            'anoconcl2g': aluno_data.get('anoconcl2g'),
                            'tipo_ingresso': aluno_data.get('tipoIngresso'),
                            'ano_ingresso': aluno_data.get('anoIngresso'),
                            'sem_ingresso': aluno_data.get('semIngresso'),
                            'creditos': aluno_data.get('creditos'),
                            'obs_aluno_finan': aluno_data.get('obsAlunoFinan'),
                            'representante_turma': aluno_data.get('representanteTurma'),
                            'tipo_aluno': aluno_data.get('tipoAluno'),
                            'faculdade_conveniada': aluno_data.get('faculdadeConveniada'),
                            'instituicao': aluno_data.get('instituicao'),
                            'classif_aluno': aluno_data.get('classifAluno'),
                            'dist_aluno_unidade': aluno_data.get('distAlunoUnidade'),
                            'tipo_escola': aluno_data.get('tipoEscola'),
                            'cidade2g': aluno_data.get('cidade2g'),
                            'pais2g': aluno_data.get('pais2g'),
                            'concurso': aluno_data.get('concurso'),
                            'candidato': aluno_data.get('candidato'),
                            'curriculo': aluno_data.get('curriculo'),
                            'discipoutraserie': aluno_data.get('discipoutraserie'),
                            'ref_aluno_ant': aluno_data.get('refAlunoAnt'),
                            'sit_aprov': aluno_data.get('sitAprov'),
                            'cod_cartao': aluno_data.get('codCartao'),
                            'curso_ant': aluno_data.get('cursoAnt'),
                            'nome_conjuge': aluno_data.get('nomeConjuge'),
                            'obs_tel_res': aluno_data.get('obsTelRes'),
                            'obs_tel_com': aluno_data.get('obsTelCom'),
                            'outra_faculdade': aluno_data.get('outraFaculdade'),
                            'areacnpq': aluno_data.get('areacnpq'),
                            'grupo': aluno_data.get('grupo'),
                            'turma_pref': aluno_data.get('turmaPref') or aluno_data.get('turma'),
                            'cred_educativo': aluno_data.get('credEducativo'),
                        }
                        if aluno_adaptado['aluno'] is None:
                            logger.warning(f"Registro de aluno sem matrícula (codAluno) para pessoa {cod_pessoa}, ignorado.")
                            continue

                        if AlunoModel.upsert(aluno_adaptado):
                            alunos_inseridos.append(aluno_adaptado['aluno'])
                        else:
                            logger.warning(f"Falha ao upsert do aluno {aluno_adaptado.get('aluno')}")
                    logger.info(f"{len(alunos_inseridos)} alunos processados.")
                else:
                    logger.info(f"Nenhum aluno encontrado para a pessoa {cod_pessoa}.")
            except Exception as e:
                logger.error(f"Erro ao buscar alunos: {e}")
            finally:
                aluno_client.close()

        return {
            "status": "inserido",
            "pessoa": dados_pessoa,
            "alunos": alunos_inseridos
        }

    except Exception as e:
        logger.error(f"Falha ao processar pessoa {cod_pessoa}: {e}")
        return None
    finally:
        pessoa_client.close()


def _buscar_pessoas_pendentes() -> List[int]:
    """
    Retorna os cod_pessoa presentes em LY_ALUNO que ainda não existem em LY_PESSOA.
    Centraliza a query que antes ficava duplicada em reports/sync_pessoas.py,
    eliminando a necessidade de subprocess naquele módulo.
    """
    query = """
        SELECT DISTINCT A.pessoa
        FROM LY_ALUNO A
        LEFT JOIN LY_PESSOA P ON A.pessoa = P.pessoa
        WHERE P.pessoa IS NULL
          AND A.pessoa IS NOT NULL
    """
    with get_db_connection(database_name='lyceum') as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]


def run() -> bool:
    """
    Wrapper run() para integração com run_all.py.

    Usa a mesma lógica de reports/sync_pessoas.py para encontrar pessoas
    pendentes, mas chama buscar_e_salvar_pessoa_por_id() diretamente —
    sem subprocess — garantindo execução no mesmo processo, com logs
    unificados e sem overhead de subprocesso.

    Processamento em lotes de 100 registros para commits parciais.
    """
    logger.info("[sync_ly_pessoa_by_id] Verificando pessoas pendentes em LY_PESSOA...")

    try:
        pendentes = _buscar_pessoas_pendentes()
    except Exception as e:
        logger.error(f"Erro ao consultar pessoas pendentes: {e}")
        return False

    if not pendentes:
        logger.info("[sync_ly_pessoa_by_id] Nenhuma pessoa pendente. Tabelas já sincronizadas.")
        return True

    total = len(pendentes)
    logger.info(f"[sync_ly_pessoa_by_id] {total} pessoa(s) pendente(s) para sincronização.")

    # Processar em lotes de 100
    lote_tamanho = 100
    sucessos = 0
    falhas = 0

    for i in range(0, total, lote_tamanho):
        lote = pendentes[i:i + lote_tamanho]
        logger.info(f"[sync_ly_pessoa_by_id] Processando lote {i//lote_tamanho + 1} (IDs {i+1} a {min(i+lote_tamanho, total)})")

        for cod_pessoa in lote:
            # buscar_alunos=False porque os alunos já são sincronizados separadamente
            resultado = buscar_e_salvar_pessoa_por_id(cod_pessoa, buscar_alunos=False)
            if resultado:
                sucessos += 1
            else:
                falhas += 1
                logger.warning(f"[sync_ly_pessoa_by_id] Falha ao sincronizar pessoa {cod_pessoa}.")

            # Pequeno delay entre requisições para evitar sobrecarga
            time.sleep(config.API_DELAY_BETWEEN_REQUESTS)

        # Após processar o lote, fazer commit explícito
        try:
            with get_db_connection(database_name='lyceum') as conn:
                conn.commit()
            logger.info(f"[sync_ly_pessoa_by_id] Lote {i//lote_tamanho + 1} concluído. Sucessos: {sucessos}, Falhas: {falhas}")
        except Exception as e:
            logger.error(f"[sync_ly_pessoa_by_id] Erro ao commitar lote: {e}")

    logger.info(f"[sync_ly_pessoa_by_id] Sincronização finalizada. Total de sucessos: {sucessos}/{total}, Falhas: {falhas}")
    return falhas == 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            codigo = int(sys.argv[1])
            resultado = buscar_e_salvar_pessoa_por_id(codigo, buscar_alunos=True)
            print(resultado)
        except ValueError:
            print("Código da pessoa deve ser um número inteiro.")
    else:
        print("Uso: python -m sync.sync_ly_pessoa_by_id <codPessoa>")