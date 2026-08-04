# core/api_client.py

import requests
import time
import urllib3
from typing import List, Optional, Any, Dict
from core.config import config


class BaseAPIClient:
    """
    Cliente base da API Lyceum
    - Autenticação: Basic Auth
    - Método: GET somente
    - Paginação automática (page 0 → última página válida)
    - size fixo conforme configuração
    """

    def __init__(self, session: Optional[requests.Session] = None):
        # Verificação detalhada das credenciais
        missing = []
        if not config.LYCEUM_BASE_URL:
            missing.append("LYCEUM_BASE_URL")
        if not config.LYCEUM_USERNAME:
            missing.append("LYCEUM_USERNAME")
        if not config.LYCEUM_PASSWORD:
            missing.append("LYCEUM_PASSWORD")

        if missing:
            raise RuntimeError(
                f"Credenciais da API Lyceum incompletas. Variáveis faltando no .env: {', '.join(missing)}"
            )

        self.base_url = config.LYCEUM_BASE_URL.rstrip("/")
        self.auth = (config.LYCEUM_USERNAME, config.LYCEUM_PASSWORD)
        self.headers = {
            "Accept": "application/json"
        }
        # Usar sessão fornecida ou criar uma nova
        self.session = session or requests.Session()

        # Suprime aviso de SSL apenas quando verificação estiver desabilitada
        if config.LYCEUM_SSL_VERIFY is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """
        Executa uma requisição GET simples.
        Retorna JSON ou None em caso de erro HTTP.
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.get(
                url,
                auth=self.auth,
                headers=self.headers,
                params=params,
                timeout=config.API_TIMEOUT,
                verify=config.LYCEUM_SSL_VERIFY
            )

            if response.status_code != 200:
                print(f"⚠️ HTTP {response.status_code} → {url}")
                return None

            return response.json()
        except Exception as e:
            print(f"⚠️ Erro na requisição → {url}: {e}")
            return None

    def get_paginated(self, endpoint: str, params: Optional[Dict] = None) -> List[dict]:
        """
        Percorre todas as páginas disponíveis da API.
        A API retorna {'data': [...]} em vez de lista direta.
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros adicionais para a requisição (opcional)
        """
        results: List[dict] = []
        page = config.API_PAGE_START
        
        print(f"  🔄 Iniciando paginação no endpoint: {endpoint}")
        if params:
            print(f"  📋 Parâmetros: {params}")
        
        while True:
            # Base parameters - página e tamanho
            request_params = {
                "page": page,
                "size": config.API_PAGE_SIZE
            }
            
            # Adicionar parâmetros extras se fornecidos
            if params:
                request_params.update(params)
            
            print(f"    📄 Página {page} (size={config.API_PAGE_SIZE})...")
            
            data = self.get(endpoint, params=request_params)
            
            # Fim da paginação
            if not data:
                print(f"    ⏹️  Página {page} retornou None")
                break
            
            # Verifica se é um dicionário com chave 'data'
            if isinstance(data, dict) and 'data' in data:
                items = data['data']
                if not isinstance(items, list):
                    print(f"    ⚠️  'data' não é uma lista: {type(items)}")
                    break
                    
                if len(items) == 0:
                    print(f"    ✅ Página {page} vazia - fim da paginação")
                    break
                    
                results.extend(items)
                print(f"    📊 Página {page}: {len(items)} registros (total: {len(results)})")
                
            elif isinstance(data, list):
                # Formato alternativo: lista direta
                if len(data) == 0:
                    print(f"    ✅ Página {page} vazia - fim da paginação")
                    break
                    
                results.extend(data)
                print(f"    📊 Página {page}: {len(data)} registros (total: {len(results)})")
            else:
                print(f"    ⚠️  Formato de resposta inesperado: {type(data)}")
                print(f"    Conteúdo: {str(data)[:200]}...")
                break
            
            page += 1

            # Evita sobrecarga na API
            time.sleep(config.API_DELAY_BETWEEN_REQUESTS)
        
        print(f"  ✅ Paginação completa: {len(results)} registros no total")
        return results
    
    def close(self):
        """Fecha a sessão HTTP"""
        if hasattr(self, 'session'):
            self.session.close()


# ==================================================
# FÁBRICA DE CLIENTES - Garante que cada consulta use uma sessão separada
# ==================================================

class APIClientFactory:
    """Fábrica para criar clientes de API com sessões isoladas"""
    
    @staticmethod
    def create_curso_client() -> 'CursoAPIClient':
        """Cria cliente de cursos com sessão isolada"""
        return CursoAPIClient()
    
    @staticmethod
    def create_curriculo_client() -> 'CurriculoAPIClient':
        """Cria cliente de currículos com sessão isolada"""
        return CurriculoAPIClient()
    
    @staticmethod
    def create_aluno_client() -> 'AlunoAPIClient':
        """Cria cliente de alunos com sessão isolada"""
        return AlunoAPIClient()
    
    @staticmethod
    def create_docente_client() -> 'DocenteAPIClient':
        """Cria cliente de docentes com sessão isolada"""
        return DocenteAPIClient()
    
    @staticmethod
    def create_disciplina_client() -> 'DisciplinaAPIClient':
        """Cria cliente de disciplinas com sessão isolada"""
        return DisciplinaAPIClient()
    
    @staticmethod
    def create_turma_client() -> 'TurmaAPIClient':
        """Cria cliente de turmas com sessão isolada"""
        return TurmaAPIClient()
    
    @staticmethod
    def create_turma_docente_client() -> 'TurmaDocenteAPIClient':
        """Cria cliente de turma-docente com sessão isolada"""
        return TurmaDocenteAPIClient()
    
    @staticmethod
    def create_matricula_client() -> 'MatriculaAPIClient':
        """Cria cliente de matrículas com sessão isolada"""
        return MatriculaAPIClient()
    
    @staticmethod
    def create_grade_client() -> 'GradeAPIClient':
        """Cria cliente de grades com sessão isolada"""
        return GradeAPIClient()
    
    @staticmethod
    def create_coordenacao_client() -> 'CoordenacaoAPIClient':
        """Cria cliente de coordenações com sessão isolada"""
        return CoordenacaoAPIClient()
    
    @staticmethod
    def create_pessoa_client() -> 'PessoaAPIClient':
        """Cria cliente de pessoas com sessão isolada"""
        return PessoaAPIClient()
    
    # ========== NOVOS CLIENTES ==========
    @staticmethod
    def create_prova_disciplina_client() -> 'ProvaDisciplinaAPIClient':
        """Cria cliente de provas-disciplinas com sessão isolada"""
        return ProvaDisciplinaAPIClient()
    
    @staticmethod
    def create_prova_client() -> 'ProvaAPIClient':
        """Cria cliente de provas com sessão isolada"""
        return ProvaAPIClient()


# ==================================================
# CLIENTES ESPECÍFICOS POR ENTIDADE
# ==================================================

class CursoAPIClient(BaseAPIClient):
    def get_cursos(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/cursos")


class CurriculoAPIClient(BaseAPIClient):
    def get_curriculos(self) -> List[dict]:
        """Obtém todos os currículos"""
        return self.get_paginated("/v2/tabela/curriculos")
    
    def get_curriculo(self, curriculo_code: str) -> Optional[dict]:
        """Obtém um currículo específico por código"""
        endpoint = "/v2/tabela/curriculos"
        params = {"pk[curriculo]": curriculo_code}
        data = self.get(endpoint, params=params)
        if data and isinstance(data, dict) and 'data' in data:
            items = data['data']
            if isinstance(items, list) and len(items) > 0:
                return items[0]
        return None


class AlunoAPIClient(BaseAPIClient):
    def get_alunos(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/alunos")
    
    def get_aluno(self, matricula: str) -> Optional[dict]:
        """Obtém um aluno específico por matrícula"""
        endpoint = "/v2/tabela/alunos"
        params = {"pk[aluno]": matricula}
        data = self.get(endpoint, params=params)
        if data and isinstance(data, dict) and 'data' in data:
            items = data['data']
            if isinstance(items, list) and len(items) > 0:
                return items[0]
        return None


class DocenteAPIClient(BaseAPIClient):
    def get_docentes(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/docente")


class DisciplinaAPIClient(BaseAPIClient):
    def get_disciplinas(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/disciplinas")


class TurmaAPIClient(BaseAPIClient):
    def get_turmas(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/turmas")
    
    def get_turmas_filtradas(self, ano: Optional[int] = None, semestre: Optional[int] = None) -> List[dict]:
        """Obtém turmas com filtros opcionais de ano e semestre"""
        params = {}
        if ano is not None:
            params["ano"] = ano
        if semestre is not None:
            params["semestre"] = semestre
        return self.get_paginated("/v2/tabela/turmas", params=params)


class TurmaDocenteAPIClient(BaseAPIClient):
    def get_turmas_docentes(self) -> List[dict]:
        return self.get_paginated("/v2/tabela/turma-docente")

    def get_turmas_docentes_filtradas(self, ano: Optional[int] = None, semestre: Optional[int] = None) -> List[dict]:
        # Mantido para compatibilidade, mas usa get_paginated sem filtro real
        params = {}
        if ano is not None:
            params["ano"] = ano
        if semestre is not None:
            params["semestre"] = semestre
        return self.get_paginated("/v2/tabela/turma-docente", params=params)

    def get_turmas_docentes_from_page(self, start_page: int, page_size: int = 100) -> List[dict]:
        """
        Obtém uma única página de registros a partir da página especificada.
        Retorna a lista de itens daquela página e, como atributo adicional, a página atual.
        """
        params = {
            "page": start_page,
            "size": page_size
        }
        data = self.get("/v2/tabela/turma-docente", params=params)
        if data and isinstance(data, dict) and 'data' in data:
            return data['data']
        return []

class MatriculaAPIClient(BaseAPIClient):
    def get_matriculas(self) -> List[dict]:
        """Obtém todas as matrículas (sem filtros)"""
        return self.get_paginated("/v2/tabela/matriculas")
    
    def get_matriculas_filtradas(self, ano: Optional[int] = None, semestre: Optional[int] = None) -> List[dict]:
        """
        Obtém matrículas com filtros opcionais de ano e semestre
        
        Args:
            ano: Ano para filtrar (opcional)
            semestre: Semestre para filtrar (opcional)
            
        Returns:
            Lista de matrículas filtradas
        """
        params = {}
        if ano is not None:
            params["ano"] = ano
        if semestre is not None:
            params["semestre"] = semestre
        
        print(f"🔍 Buscando matrículas com filtros: ano={ano}, semestre={semestre}")
        return self.get_paginated("/v2/tabela/matriculas", params=params)
    
    def get_matriculas_by_aluno(self, aluno_code: str) -> List[dict]:
        """Obtém matrículas de um aluno específico"""
        params = {"pk[aluno]": aluno_code}
        return self.get_paginated("/v2/tabela/matriculas", params=params)
    
    def get_matriculas_by_turma(self, turma_code: str) -> List[dict]:
        """Obtém matrículas de uma turma específica"""
        params = {"pk[turma]": turma_code}
        return self.get_paginated("/v2/tabela/matriculas", params=params)
    

class GradeAPIClient(BaseAPIClient):
    def get_grades(self) -> List[dict]:
        """Obtém todas as grades"""
        return self.get_paginated("/v2/tabela/grades")
    

class PessoaAPIClient(BaseAPIClient):
    def get_pessoas(self) -> List[dict]:
        """Obtém todas as pessoas (com paginação)"""
        return self.get_paginated("/v2/tabela/pessoas")

    def get_pessoa_by_id(self, cod_pessoa: int) -> Optional[dict]:
        """
        Obtém uma pessoa específica pelo código usando o filtro pk[pessoa].
        Trata tanto resposta com {'data': [...]} quanto o objeto direto.
        """
        endpoint = "/v2/tabela/pessoas"
        params = {"pk[pessoa]": cod_pessoa}
        data = self.get(endpoint, params=params)
        print(f"DEBUG - Resposta da API para pessoa {cod_pessoa}: {data}")

        if isinstance(data, dict) and 'data' in data:
            items = data['data']
            if isinstance(items, list) and len(items) > 0:
                return items[0]
        elif isinstance(data, dict) and 'pessoa' in data:
            return data
        elif isinstance(data, list) and len(data) > 0:
            return data[0]
        return None

    def get_pessoa_detalhada(self, id_pessoa: int) -> Optional[dict]:
        """
        Busca uma pessoa pelo ID usando o endpoint específico:
        /v2/pessoas/idPessoa/{idPessoa}/obterPessoa
        """
        endpoint = f"/v2/pessoas/idPessoa/{id_pessoa}/obterPessoa"
        data = self.get(endpoint)
        if data and isinstance(data, dict):
            if 'data' in data:
                return data['data']
            return data
        return None


class CoordenacaoAPIClient(BaseAPIClient):
    def get_coordenacoes(self) -> List[dict]:
        """
        Obtém todas as coordenações via paginação
        """
        return self.get_paginated("/v2/tabela/coordenacao")
    
    def get_coordenacoes_filtradas(self, ano: Optional[int] = None, semestre: Optional[int] = None) -> List[dict]:
        """
        Obtém coordenações com filtros opcionais de ano e semestre
        """
        params = {}
        if ano is not None:
            params["ano"] = ano
        if semestre is not None:
            params["semestre"] = semestre
        return self.get_paginated("/v2/tabela/coordenacao", params=params)


# ========== NOVOS CLIENTES ==========

class ProvaDisciplinaAPIClient(BaseAPIClient):
    """
    Cliente para o endpoint /v2/tabela/provas-disciplinas
    Retorna lista paginada de provas-disciplinas.
    """
    def get_provas_disciplinas(self) -> List[dict]:
        """
        Obtém todas as provas-disciplinas (paginação automática).
        """
        return self.get_paginated("/v2/tabela/provas-disciplinas")
    
    def get_provas_disciplinas_filtradas(self, **kwargs) -> List[dict]:
        """
        Obtém provas-disciplinas com filtros adicionais.
        Exemplo: ?classificacao=... 
        """
        return self.get_paginated("/v2/tabela/provas-disciplinas", params=kwargs)

class ProvaAPIClient(BaseAPIClient):
    def get_prova(self, ano: int, disciplina: str, prova: str, semestre: int, turma: str) -> Optional[dict]:
        params = {
            "pk[ano]": ano,
            "pk[disciplina]": disciplina,
            "pk[prova]": prova,
            "pk[semestre]": semestre,
            "pk[turma]": turma,
        }
        data = self.get("/v2/tabela/provas", params=params)
        if isinstance(data, dict):
            if 'data' in data:
                items = data['data']
                if isinstance(items, list) and len(items) > 0:
                    return items[0]
            else:
                return data
        return None

# ==================================================
# MÉTODOS DE CONVENIÊNCIA - Mantém compatibilidade
# ==================================================

def get_curriculo_client() -> CurriculoAPIClient:
    return APIClientFactory.create_curriculo_client()

def get_aluno_client() -> AlunoAPIClient:
    return APIClientFactory.create_aluno_client()

def get_curso_client() -> CursoAPIClient:
    return APIClientFactory.create_curso_client()

def get_docente_client() -> DocenteAPIClient:
    return APIClientFactory.create_docente_client()

def get_disciplina_client() -> DisciplinaAPIClient:
    return APIClientFactory.create_disciplina_client()

def get_turma_client() -> TurmaAPIClient:
    return APIClientFactory.create_turma_client()

def get_turma_docente_client() -> TurmaDocenteAPIClient:
    return APIClientFactory.create_turma_docente_client()

def get_matricula_client() -> MatriculaAPIClient:
    return APIClientFactory.create_matricula_client()

def get_grade_client() -> GradeAPIClient:
    return APIClientFactory.create_grade_client()

def get_coordenacao_client() -> CoordenacaoAPIClient:
    return APIClientFactory.create_coordenacao_client()

def get_pessoa_client() -> PessoaAPIClient:
    return APIClientFactory.create_pessoa_client()

# ========== NOVAS FUNÇÕES DE CONVENIÊNCIA ==========

def get_prova_disciplina_client() -> ProvaDisciplinaAPIClient:
    """Retorna um cliente de provas-disciplinas com sessão isolada"""
    return APIClientFactory.create_prova_disciplina_client()

def get_prova_client() -> ProvaAPIClient:
    """Retorna um cliente de provas com sessão isolada"""
    return APIClientFactory.create_prova_client()