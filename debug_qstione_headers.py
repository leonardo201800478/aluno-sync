"""
debug_qstione_headers.py

DiagnÃ³stico do endpoint do Integrador Qstione Sandbox.

Objetivos:
1. Validar se o token estÃ¡ sendo carregado corretamente do .env.
2. Confirmar quais headers o requests efetivamente prepara.
3. Enviar um POST mÃ­nimo com:
      - tokenIdInstituicao
      - codigoTransacao
4. Testar uma segunda chamada com token invÃ¡lido, para comparar a resposta.
5. Nunca exibir o token completo.

NÃ£o altera os importadores nem o cliente do Lyceum.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv


# =============================================================================
# CONFIGURAÃ‡ÃƒO
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"

load_dotenv(ENV_FILE)

QSTIONE_BASE_URL = os.getenv(
    "QSTIONE_BASE_URL",
    "https://unifoa.sandbox.qstione.com.br/integrador",
).strip()

QSTIONE_TOKEN = os.getenv("QSTIONE_TOKEN", "").strip()

QSTIONE_TIMEOUT = int(os.getenv("QSTIONE_TIMEOUT", "60"))

QSTIONE_SSL_VERIFY = (
    os.getenv("QSTIONE_SSL_VERIFY", "true").strip().lower()
    not in {"false", "0", "no", "nao", "nÃ£o"}
)


# =============================================================================
# FUNÃ‡Ã•ES AUXILIARES
# =============================================================================

def mascarar_token(token: str) -> str:
    """Exibe somente inÃ­cio e fim do token."""
    if not token:
        return "<vazio>"

    if len(token) <= 8:
        return "*" * len(token)

    return f"{token[:4]}...{token[-4:]}"


def mascarar_header(nome: str, valor: str) -> str:
    """Mascara valores sensÃ­veis ao exibir headers."""
    if nome.lower() == "tokenidinstituicao":
        return mascarar_token(valor)

    return valor


def imprimir_headers(headers: dict[str, str], titulo: str) -> None:
    print()
    print(titulo)

    for nome, valor in headers.items():
        print(f"{nome}: {mascarar_header(nome, str(valor))}")


def interpretar_resposta(response: requests.Response) -> None:
    """Mostra a resposta sem expor informaÃ§Ãµes desnecessÃ¡rias."""

    print()
    print("-" * 80)
    print(f"HTTP: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', '<nÃ£o informado>')}")
    print(f"Servidor: {response.headers.get('Server', '<nÃ£o informado>')}")
    print()
    print("Resposta:")

    try:
        dados = response.json()

        # Respostas do Integrador normalmente vÃªm como lista de registros.
        if isinstance(dados, list):
            for item in dados:
                if isinstance(item, dict):
                    print(
                        f"numeroRegistro: {item.get('numeroRegistro', '<nÃ£o informado>')}"
                    )
                    print(
                        f"nomeExcecao: {item.get('nomeExcecao', '<nÃ£o informado>')}"
                    )
                    print(
                        f"detalhesFalha: "
                        f"{item.get('detalhesFalha', '<nÃ£o informado>')}"
                    )
                else:
                    print(item)
        else:
            print(dados)

    except ValueError:
        # Caso a API devolva texto em vez de JSON.
        print(response.text[:5000])

    print("-" * 80)


def preparar_request(
    headers: dict[str, str],
    payload: dict,
) -> requests.PreparedRequest:
    """
    Prepara a requisiÃ§Ã£o sem enviÃ¡-la.

    Isso permite verificar o que o requests realmente colocarÃ¡ no HTTP.
    """

    request = requests.Request(
        method="POST",
        url=QSTIONE_BASE_URL,
        headers=headers,
        json=payload,
    )

    session = requests.Session()

    return session.prepare_request(request)


def imprimir_prepared_headers(
    prepared: requests.PreparedRequest,
    titulo: str,
) -> None:
    """Exibe os headers efetivamente preparados pelo requests."""

    print()
    print(titulo)

    for nome, valor in prepared.headers.items():
        print(f"{nome}: {mascarar_header(nome, str(valor))}")


def enviar_teste(
    nome_teste: str,
    token: str,
    codigo_transacao: str,
) -> None:
    """Executa um POST mÃ­nimo no Integrador."""

    print()
    print("=" * 80)
    print(nome_teste)
    print("=" * 80)

    payload = {}

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "tokenIdInstituicao": token,
        "codigoTransacao": codigo_transacao,
    }

    imprimir_headers(headers, "Headers definidos:")

    prepared = preparar_request(headers, payload)

    imprimir_prepared_headers(
        prepared,
        "Headers efetivamente preparados pelo requests:",
    )

    print()
    print(f"URL preparada: {prepared.url}")
    print(f"MÃ©todo: {prepared.method}")
    print(f"Corpo preparado: {prepared.body!r}")

    print()
    print("Enviando POST...")

    inicio = time.perf_counter()

    try:
        with requests.Session() as session:
            response = session.send(
                prepared,
                timeout=QSTIONE_TIMEOUT,
                verify=QSTIONE_SSL_VERIFY,
            )

        tempo = time.perf_counter() - inicio

        print(f"Tempo: {tempo:.3f} s")
        interpretar_resposta(response)

    except requests.RequestException as exc:
        tempo = time.perf_counter() - inicio

        print(f"Tempo atÃ© a falha: {tempo:.3f} s")
        print()
        print("ERRO DE COMUNICAÃ‡ÃƒO:")
        print(type(exc).__name__)
        print(str(exc))


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    print("=" * 80)
    print("DIAGNÃ“STICO QSTIONE - TESTE DE HEADERS")
    print("=" * 80)

    print(f"Arquivo .env: {ENV_FILE}")
    print(f".env encontrado: {ENV_FILE.exists()}")
    print(f"URL: {QSTIONE_BASE_URL}")
    print(f"Token configurado: {bool(QSTIONE_TOKEN)}")
    print(f"Tamanho do token: {len(QSTIONE_TOKEN)}")
    print(f"Token mascarado: {mascarar_token(QSTIONE_TOKEN)}")
    print(f"EspaÃ§os no token: {any(c.isspace() for c in QSTIONE_TOKEN)}")
    print(f"SSL verify: {QSTIONE_SSL_VERIFY}")
    print(f"Timeout: {QSTIONE_TIMEOUT}s")

    # -------------------------------------------------------------------------
    # ValidaÃ§Ãµes antes do POST
    # -------------------------------------------------------------------------

    problemas = []

    if not QSTIONE_TOKEN:
        problemas.append("QSTIONE_TOKEN estÃ¡ vazio.")

    if any(c.isspace() for c in QSTIONE_TOKEN):
        problemas.append("QSTIONE_TOKEN contÃ©m espaÃ§os ou quebras de linha.")

    if len(QSTIONE_TOKEN) != 128:
        problemas.append(
            f"QSTIONE_TOKEN possui {len(QSTIONE_TOKEN)} caracteres; "
            "o esperado neste ambiente Ã© 128."
        )

    if not QSTIONE_BASE_URL:
        problemas.append("QSTIONE_BASE_URL estÃ¡ vazio.")

    if problemas:
        print()
        print("ATENÃ‡ÃƒO - problemas encontrados:")

        for problema in problemas:
            print(f"  - {problema}")

        print()
        print("O teste serÃ¡ interrompido para evitar uma chamada invÃ¡lida.")
        return

    # -------------------------------------------------------------------------
    # Gera cÃ³digoTransacao Ãºnico para o teste.
    #
    # O retorno anterior comprovou que tokenIdInstituicao estÃ¡ sendo recebido.
    # Agora o Integrador solicitou explicitamente codigoTransacao.
    # -------------------------------------------------------------------------

    codigo_transacao = str(int(time.time() * 1000))

    print()
    print(f"codigoTransacao gerado: {codigo_transacao}")

    # -------------------------------------------------------------------------
    # TESTE 1 - token real + codigoTransacao
    # -------------------------------------------------------------------------

    enviar_teste(
        nome_teste="TESTE 1 - TOKEN REAL + codigoTransacao",
        token=QSTIONE_TOKEN,
        codigo_transacao = str(int(time.time() * 1000) % 10_000_000).zfill(7),
    )

    # -------------------------------------------------------------------------
    # TESTE 2 - token invÃ¡lido + novo codigoTransacao
    #
    # Serve para verificar se o comportamento muda quando o token Ã© alterado.
    # -------------------------------------------------------------------------

    codigo_transacao_invalido = str(int(time.time() * 1000) + 1)

    enviar_teste(
        nome_teste="TESTE 2 - TOKEN INVÃLIDO + codigoTransacao",
        token="TOKEN_INVALIDO_TESTE",
        codigo_transacao=codigo_transacao_invalido,
    )

    print()
    print("=" * 80)
    print("FIM DO DIAGNÃ“STICO")
    print("=" * 80)


if __name__ == "__main__":
    main()

