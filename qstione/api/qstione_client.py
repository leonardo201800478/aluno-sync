"""
qstione/api/qstione_client.py

Cliente HTTP exclusivo para o Integrador Qstione.

Características:
    - Somente POST.
    - Autenticação através de token.
    - JSON como formato de comunicação.
    - Sem GET.
    - Sem paginação.
    - Sem qualquer dependência do cliente Lyceum.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import requests

from qstione.config.qstione_config import (
    QSTIONE_BASE_URL,
    QSTIONE_TOKEN,
    QSTIONE_TIMEOUT,
    QSTIONE_SSL_VERIFY,
    validar_configuracao_qstione,
)


logger = logging.getLogger(
    "qstione.api.client"
)


class QstioneAPIError(Exception):
    """
    Exceção específica para erros da API Qstione.
    """


class QstioneAPIClient:
    """
    Cliente HTTP para comunicação com o Integrador Qstione.

    O cliente é deliberadamente limitado ao método POST,
    pois sua finalidade é exclusivamente enviar as cargas
    geradas pelos importadores.
    """

    def __init__(
        self,
        session: Optional[requests.Session] = None,
    ) -> None:
        """
        Inicializa o cliente Qstione.

        Args:
            session:
                Sessão requests opcional. Caso não seja informada,
                uma nova sessão será criada.

        Raises:
            RuntimeError:
                Caso a configuração da API esteja incompleta.
        """

        validar_configuracao_qstione()

        self.base_url = QSTIONE_BASE_URL

        self.session = (
            session
            if session is not None
            else requests.Session()
        )

        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": (
                f"Bearer {QSTIONE_TOKEN}"
            ),
        }

    def post(
        self,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> Any:
        """
        Envia uma carga para o Integrador Qstione.

        Args:
            endpoint:
                Caminho do endpoint relativo à URL base.

            payload:
                Dados da carga em formato de dicionário.

        Returns:
            Conteúdo JSON retornado pela API.

        Raises:
            QstioneAPIError:
                Caso ocorra erro HTTP ou erro de comunicação.
        """

        url = (
            f"{self.base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        logger.info(
            "POST Qstione Sandbox: %s",
            url,
        )

        try:
            response = self.session.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=QSTIONE_TIMEOUT,
                verify=QSTIONE_SSL_VERIFY,
            )

        except requests.RequestException as exc:

            logger.error(
                "Erro de comunicação com Qstione: %s",
                exc,
            )

            raise QstioneAPIError(
                f"Erro de comunicação com Qstione: {exc}"
            ) from exc

        if not response.ok:

            logger.error(
                "Qstione retornou HTTP %s: %s",
                response.status_code,
                response.text,
            )

            raise QstioneAPIError(
                "Qstione retornou HTTP "
                f"{response.status_code}: "
                f"{response.text}"
            )

        try:
            return response.json()

        except ValueError:

            return response.text