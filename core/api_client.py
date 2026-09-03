#!/usr/bin/env python3
"""
core/api_client.py

Clientes para a API Lyceum.

Características:
    - Autenticação Basic Auth.
    - Somente GET.
    - Paginação automática.
    - Paginação de página individual para sincronizações incrementais.
"""

import requests
import time
import urllib3

from typing import List, Optional, Any, Dict

from core.config import config


# ============================================================================
# CLIENTE BASE
# ============================================================================

class BaseAPIClient:
    """
    Cliente base da API Lyceum.

    Responsabilidades:
        - autenticação;
        - requisições GET;
        - paginação automática;
        - controle da sessão HTTP.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None
    ):
        """
        Inicializa o cliente da API.

        Parameters
        ----------
        session:
            Sessão requests opcional.
        """

        missing = []

        if not config.LYCEUM_BASE_URL:
            missing.append("LYCEUM_BASE_URL")

        if not config.LYCEUM_USERNAME:
            missing.append("LYCEUM_USERNAME")

        if not config.LYCEUM_PASSWORD:
            missing.append("LYCEUM_PASSWORD")

        if missing:

            raise RuntimeError(
                "Credenciais da API Lyceum incompletas. "
                "Variáveis faltando no .env: "
                + ", ".join(missing)
            )

        self.base_url = (
            config.LYCEUM_BASE_URL.rstrip("/")
        )

        self.auth = (
            config.LYCEUM_USERNAME,
            config.LYCEUM_PASSWORD
        )

        self.headers = {
            "Accept": "application/json"
        }

        self.session = (
            session
            or requests.Session()
        )

        if config.LYCEUM_SSL_VERIFY is False:

            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning
            )

    # ------------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------------

    def get(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> Any:
        """
        Executa uma requisição GET.

        Retorna:
            JSON retornado pela API ou None em caso de erro.
        """

        url = (
            f"{self.base_url}{endpoint}"
        )

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

                print(
                    f"⚠️ HTTP {response.status_code} → {url}"
                )

                return None

            return response.json()

        except Exception as exc:

            print(
                f"⚠️ Erro na requisição → "
                f"{url}: {exc}"
            )

            return None

    # ------------------------------------------------------------------------
    # PAGINAÇÃO AUTOMÁTICA
    # ------------------------------------------------------------------------

    def get_paginated(
        self,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> List[dict]:
        """
        Percorre todas as páginas disponíveis.

        A API pode retornar:

            {"data": [...]}

        ou diretamente:

            [...]
        """

        results: List[dict] = []

        page = config.API_PAGE_START

        print(
            f"  🔄 Iniciando paginação: {endpoint}"
        )

        if params:

            print(
                f"  📋 Parâmetros: {params}"
            )

        while True:

            request_params = {
                "page": page,
                "size": config.API_PAGE_SIZE
            }

            if params:

                request_params.update(
                    params
                )

            print(
                f"    📄 Página {page} "
                f"(size={config.API_PAGE_SIZE})..."
            )

            data = self.get(
                endpoint,
                params=request_params
            )

            if not data:

                print(
                    f"    ⏹️ Página {page} retornou None"
                )

                break

            if (
                isinstance(data, dict)
                and "data" in data
            ):

                items = data["data"]

                if not isinstance(items, list):

                    print(
                        "    ⚠️ 'data' não é uma lista: "
                        f"{type(items)}"
                    )

                    break

                if len(items) == 0:

                    print(
                        f"    ✅ Página {page} vazia."
                    )

                    break

                results.extend(items)

                print(
                    f"    📊 Página {page}: "
                    f"{len(items)} registros "
                    f"(total: {len(results)})"
                )

            elif isinstance(data, list):

                if len(data) == 0:

                    print(
                        f"    ✅ Página {page} vazia."
                    )

                    break

                results.extend(data)

                print(
                    f"    📊 Página {page}: "
                    f"{len(data)} registros "
                    f"(total: {len(results)})"
                )

            else:

                print(
                    "    ⚠️ Formato inesperado: "
                    f"{type(data)}"
                )

                break

            page += 1

            if config.API_DELAY_BETWEEN_REQUESTS > 0:

                time.sleep(
                    config.API_DELAY_BETWEEN_REQUESTS
                )

        print(
            f"  ✅ Paginação completa: "
            f"{len(results)} registros."
        )

        return results

    # ------------------------------------------------------------------------
    # FECHAMENTO
    # ------------------------------------------------------------------------

    def close(self):
        """
        Fecha a sessão HTTP.
        """

        if hasattr(self, "session"):

            self.session.close()


# ============================================================================
# FÁBRICA
# ============================================================================

class APIClientFactory:
    """
    Fábrica de clientes com sessões independentes.
    """

    @staticmethod
    def create_curso_client():
        return CursoAPIClient()

    @staticmethod
    def create_curriculo_client():
        return CurriculoAPIClient()

    @staticmethod
    def create_aluno_client():
        return AlunoAPIClient()

    @staticmethod
    def create_docente_client():
        return DocenteAPIClient()

    @staticmethod
    def create_disciplina_client():
        return DisciplinaAPIClient()

    @staticmethod
    def create_turma_client():
        return TurmaAPIClient()

    @staticmethod
    def create_turma_docente_client():
        return TurmaDocenteAPIClient()

    @staticmethod
    def create_matricula_client():
        return MatriculaAPIClient()

    @staticmethod
    def create_grade_client():
        return GradeAPIClient()

    @staticmethod
    def create_coordenacao_client():
        return CoordenacaoAPIClient()

    @staticmethod
    def create_pessoa_client():
        return PessoaAPIClient()

    @staticmethod
    def create_prova_disciplina_client():
        return ProvaDisciplinaAPIClient()

    @staticmethod
    def create_prova_client():
        return ProvaAPIClient()


# ============================================================================
# CURSOS
# ============================================================================

class CursoAPIClient(BaseAPIClient):

    def get_cursos(self) -> List[dict]:
        return self.get_paginated(
            "/v2/tabela/cursos"
        )


# ============================================================================
# CURRÍCULOS
# ============================================================================

class CurriculoAPIClient(BaseAPIClient):

    def get_curriculos(self) -> List[dict]:
        return self.get_paginated(
            "/v2/tabela/curriculos"
        )

    def get_curriculo(
        self,
        curriculo_code: str
    ) -> Optional[dict]:

        data = self.get(
            "/v2/tabela/curriculos",
            params={
                "pk[curriculo]": curriculo_code
            }
        )

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            items = data["data"]

            if (
                isinstance(items, list)
                and items
            ):

                return items[0]

        return None


# ============================================================================
# ALUNOS
# ============================================================================

class AlunoAPIClient(BaseAPIClient):

    def get_alunos(self) -> List[dict]:
        return self.get_paginated(
            "/v2/tabela/alunos"
        )

    def get_aluno(
        self,
        matricula: str
    ) -> Optional[dict]:

        data = self.get(
            "/v2/tabela/alunos",
            params={
                "pk[aluno]": matricula
            }
        )

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            items = data["data"]

            if (
                isinstance(items, list)
                and items
            ):

                return items[0]

        return None


# ============================================================================
# DOCENTES
# ============================================================================

class DocenteAPIClient(BaseAPIClient):

    def get_docentes(self) -> List[dict]:
        return self.get_paginated(
            "/v2/tabela/docente"
        )


# ============================================================================
# DISCIPLINAS
# ============================================================================

class DisciplinaAPIClient(BaseAPIClient):

    def get_disciplinas(self) -> List[dict]:
        return self.get_paginated(
            "/v2/tabela/disciplinas"
        )


# ============================================================================
# TURMAS
# ============================================================================

class TurmaAPIClient(BaseAPIClient):

    def get_turmas(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/turmas"
        )

    def get_turmas_filtradas(
        self,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:
        """
        Obtém todas as turmas usando filtros da API.
        """

        params = {}

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        return self.get_paginated(
            "/v2/tabela/turmas",
            params=params
        )

    def get_turmas_from_page(
        self,
        page: int,
        page_size: int = None,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:
        """
        Obtém somente uma página de turmas.

        Este método é utilizado pelas sincronizações
        incrementais para que o processo não precise
        carregar toda a API em memória.

        Parameters
        ----------
        page:
            Página desejada.

        page_size:
            Quantidade de registros da página.

        ano:
            Filtro opcional de ano.

        semestre:
            Filtro opcional de semestre.
        """

        if page_size is None:

            page_size = config.API_PAGE_SIZE

        params = {
            "page": page,
            "size": page_size
        }

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        data = self.get(
            "/v2/tabela/turmas",
            params=params
        )

        if not data:
            return []

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            items = data["data"]

            if isinstance(items, list):

                return items

            return []

        if isinstance(data, list):

            return data

        return []


# ============================================================================
# TURMA DOCENTE
# ============================================================================

class TurmaDocenteAPIClient(BaseAPIClient):

    def get_turmas_docentes(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/turma-docente"
        )

    def get_turmas_docentes_filtradas(
        self,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:

        params = {}

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        return self.get_paginated(
            "/v2/tabela/turma-docente",
            params=params
        )

    def get_turmas_docentes_from_page(
        self,
        start_page: int,
        page_size: int = None,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:
        """
        Obtém somente uma página de turma-docente.

        Inclui filtros opcionais de ano e semestre.
        """

        if page_size is None:

            page_size = config.API_PAGE_SIZE

        params = {
            "page": start_page,
            "size": page_size
        }

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        data = self.get(
            "/v2/tabela/turma-docente",
            params=params
        )

        if not data:
            return []

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            items = data["data"]

            if isinstance(items, list):

                return items

            return []

        if isinstance(data, list):

            return data

        return []


# ============================================================================
# MATRÍCULAS
# ============================================================================

class MatriculaAPIClient(BaseAPIClient):

    def get_matriculas(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/matriculas"
        )

    def get_matriculas_filtradas(
        self,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:

        params = {}

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        return self.get_paginated(
            "/v2/tabela/matriculas",
            params=params
        )

    def get_matriculas_by_aluno(
        self,
        aluno_code: str
    ) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/matriculas",
            params={
                "pk[aluno]": aluno_code
            }
        )

    def get_matriculas_by_turma(
        self,
        turma_code: str
    ) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/matriculas",
            params={
                "pk[turma]": turma_code
            }
        )


# ============================================================================
# GRADE
# ============================================================================

class GradeAPIClient(BaseAPIClient):

    def get_grades(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/grades"
        )


# ============================================================================
# PESSOA
# ============================================================================

class PessoaAPIClient(BaseAPIClient):

    def get_pessoas(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/pessoas"
        )

    def get_pessoa_by_id(
        self,
        cod_pessoa: int
    ) -> Optional[dict]:

        data = self.get(
            "/v2/tabela/pessoas",
            params={
                "pk[pessoa]": cod_pessoa
            }
        )

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            items = data["data"]

            if (
                isinstance(items, list)
                and items
            ):

                return items[0]

        elif (
            isinstance(data, dict)
            and "pessoa" in data
        ):

            return data

        elif (
            isinstance(data, list)
            and data
        ):

            return data[0]

        return None

    def get_pessoa_detalhada(
        self,
        id_pessoa: int
    ) -> Optional[dict]:

        data = self.get(
            f"/v2/pessoas/idPessoa/"
            f"{id_pessoa}/obterPessoa"
        )

        if (
            isinstance(data, dict)
            and "data" in data
        ):

            return data["data"]

        if isinstance(data, dict):

            return data

        return None


# ============================================================================
# COORDENAÇÃO
# ============================================================================

class CoordenacaoAPIClient(BaseAPIClient):

    def get_coordenacoes(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/coordenacao"
        )

    def get_coordenacoes_filtradas(
        self,
        ano: Optional[int] = None,
        semestre: Optional[int] = None
    ) -> List[dict]:

        params = {}

        if ano is not None:
            params["ano"] = ano

        if semestre is not None:
            params["semestre"] = semestre

        return self.get_paginated(
            "/v2/tabela/coordenacao",
            params=params
        )


# ============================================================================
# PROVAS-DISCIPLINAS
# ============================================================================

class ProvaDisciplinaAPIClient(BaseAPIClient):

    def get_provas_disciplinas(self) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/provas-disciplinas"
        )

    def get_provas_disciplinas_filtradas(
        self,
        **kwargs
    ) -> List[dict]:

        return self.get_paginated(
            "/v2/tabela/provas-disciplinas",
            params=kwargs
        )


# ============================================================================
# PROVAS
# ============================================================================

class ProvaAPIClient(BaseAPIClient):

    def get_prova(
        self,
        ano: int,
        disciplina: str,
        prova: str,
        semestre: int,
        turma: str
    ) -> Optional[dict]:

        params = {
            "pk[ano]": ano,
            "pk[disciplina]": disciplina,
            "pk[prova]": prova,
            "pk[semestre]": semestre,
            "pk[turma]": turma
        }

        data = self.get(
            "/v2/tabela/provas",
            params=params
        )

        if isinstance(data, dict):

            if "data" in data:

                items = data["data"]

                if (
                    isinstance(items, list)
                    and items
                ):

                    return items[0]

            else:

                return data

        return None


# ============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# ============================================================================

def get_curriculo_client():
    return APIClientFactory.create_curriculo_client()


def get_aluno_client():
    return APIClientFactory.create_aluno_client()


def get_curso_client():
    return APIClientFactory.create_curso_client()


def get_docente_client():
    return APIClientFactory.create_docente_client()


def get_disciplina_client():
    return APIClientFactory.create_disciplina_client()


def get_turma_client():
    return APIClientFactory.create_turma_client()


def get_turma_docente_client():
    return APIClientFactory.create_turma_docente_client()


def get_matricula_client():
    return APIClientFactory.create_matricula_client()


def get_grade_client():
    return APIClientFactory.create_grade_client()


def get_coordenacao_client():
    return APIClientFactory.create_coordenacao_client()


def get_pessoa_client():
    return APIClientFactory.create_pessoa_client()


def get_prova_disciplina_client():
    return APIClientFactory.create_prova_disciplina_client()


def get_prova_client():
    return APIClientFactory.create_prova_client()