"""
qstione/config/qstione_config.py

Configuração exclusiva da API de integração do Qstione.

IMPORTANTE:
    Esta configuração NÃO possui qualquer dependência da API Lyceum.

Responsabilidade:
    - URL do integrador Qstione;
    - token de autenticação;
    - timeout;
    - verificação SSL;
    - configurações relacionadas ao envio POST.
"""

import os

from dotenv import load_dotenv


# ============================================================================
# ENVIRONMENT
# ============================================================================

load_dotenv()


# ============================================================================
# CONFIGURAÇÃO QSTIONE
# ============================================================================

QSTIONE_BASE_URL = os.getenv(
    "QSTIONE_BASE_URL",
    "https://unifoa.sandbox.qstione.com.br/integrador",
).rstrip("/")


QSTIONE_TOKEN = os.getenv(
    "QSTIONE_TOKEN"
)


QSTIONE_TIMEOUT = int(
    os.getenv(
        "QSTIONE_TIMEOUT",
        "60",
    )
)


QSTIONE_SSL_VERIFY = (
    os.getenv(
        "QSTIONE_SSL_VERIFY",
        "true",
    ).strip().lower()
    not in {
        "0",
        "false",
        "no",
        "off",
    }
)


# ============================================================================
# VALIDAÇÃO
# ============================================================================

def validar_configuracao_qstione() -> None:
    """
    Valida se a configuração mínima do Qstione está disponível.

    Raises:
        RuntimeError:
            Caso o token ou a URL do integrador não estejam configurados.
    """

    faltantes = []

    if not QSTIONE_BASE_URL:
        faltantes.append(
            "QSTIONE_BASE_URL"
        )

    if not QSTIONE_TOKEN:
        faltantes.append(
            "QSTIONE_TOKEN"
        )

    if faltantes:
        raise RuntimeError(
            "Configuração da API Qstione incompleta. "
            "Variáveis ausentes no .env: "
            + ", ".join(faltantes)
        )