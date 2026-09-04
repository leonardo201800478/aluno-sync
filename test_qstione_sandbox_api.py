"""
Teste de responsividade do Integrador Qstione - Sandbox.

Este script NÃO utiliza a API do Lyceum.

Objetivo:
    1. Confirmar que o endpoint HTTPS do Qstione responde.
    2. Confirmar que o token de integração está sendo aceito.
    3. Medir o tempo de resposta.
    4. Verificar o comportamento do endpoint diante de um POST
       propositalmente inválido.

IMPORTANTE:
    O teste padrão envia apenas {} como payload. Isso não representa
    nenhuma das cargas IMP-001...IMP-016 do manual e não deve criar
    registros acadêmicos válidos.

Variáveis esperadas no .env da raiz do projeto:

    QSTIONE_BASE_URL=https://unifoa.sandbox.qstione.com.br/integrador
    QSTIONE_TOKEN=...
    QSTIONE_TIMEOUT=60
    QSTIONE_SSL_VERIFY=true

Uso:

    python test_qstione_sandbox_api.py

Ou, se o arquivo for colocado em qstione/tests:

    python qstione/tests/test_qstione_sandbox_api.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


# ============================================================================
# LOCALIZAÇÃO DO PROJETO
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent


def localizar_raiz_projeto() -> Path:
    """
    Procura a raiz do projeto a partir da localização deste script.

    A procura considera como indicadores:
        - arquivo .env;
        - diretório .git;
        - diretório .venv;
        - arquivo requirements.txt;
        - arquivo pyproject.toml.

    Returns:
        Caminho provável da raiz do projeto.
    """

    candidatos = [SCRIPT_DIR, *SCRIPT_DIR.parents]

    for candidato in candidatos:
        if (candidato / ".env").exists():
            return candidato

    for candidato in candidatos:
        indicadores = (
            ".git",
            ".venv",
            "requirements.txt",
            "pyproject.toml",
        )

        if any((candidato / item).exists() for item in indicadores):
            return candidato

    return SCRIPT_DIR


PROJECT_ROOT = localizar_raiz_projeto()
ENV_FILE = PROJECT_ROOT / ".env"


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

load_dotenv(ENV_FILE)


QSTIONE_BASE_URL = os.getenv(
    "QSTIONE_BASE_URL",
    "https://unifoa.sandbox.qstione.com.br/integrador",
).rstrip("/")


QSTIONE_TOKEN = os.getenv(
    "QSTIONE_TOKEN",
    "",
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
# CORES DO TERMINAL
# ============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"


def status(text: str, cor: str = RESET) -> None:
    """
    Imprime uma mensagem de status formatada.

    Args:
        text:
            Texto que será exibido.
        cor:
            Código ANSI de cor.
    """

    print(f"{cor}{text}{RESET}")


def mascarar_token(token: str) -> str:
    """
    Mascara o token para impedir que ele apareça no terminal.

    Args:
        token:
            Token completo.

    Returns:
        Token parcialmente mascarado.
    """

    if not token:
        return "(não configurado)"

    if len(token) <= 8:
        return "*" * len(token)

    return f"{token[:4]}...{token[-4:]}"


def formatar_resposta(response: requests.Response) -> str:
    """
    Extrai uma representação curta da resposta HTTP.

    O conteúdo é limitado para evitar que uma resposta muito grande
    polua o terminal.

    Args:
        response:
            Objeto Response do requests.

    Returns:
        Texto resumido da resposta.
    """

    try:
        data: Any = response.json()

        texto = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )

    except ValueError:
        texto = response.text

    texto = texto.strip()

    if len(texto) > 2000:
        texto = texto[:2000] + "\n... [resposta truncada]"

    return texto


def validar_configuracao() -> bool:
    """
    Verifica se a configuração mínima está disponível.

    Returns:
        True quando a configuração está válida.
    """

    ok = True

    if not QSTIONE_BASE_URL:
        status(
            "ERRO: QSTIONE_BASE_URL não configurada.",
            RED,
        )
        ok = False

    if not QSTIONE_TOKEN:
        status(
            "ERRO: QSTIONE_TOKEN não configurado.",
            RED,
        )
        ok = False

    if not ENV_FILE.exists():
        status(
            f"AVISO: .env não encontrado em {ENV_FILE}",
            YELLOW,
        )

    return ok


def executar_post_teste() -> bool:
    """
    Executa um POST propositalmente inválido no endpoint do integrador.

    O payload vazio serve para verificar:
        - resolução do domínio;
        - conexão HTTPS;
        - certificado TLS;
        - disponibilidade do endpoint;
        - aceitação do header de autenticação;
        - tempo de resposta;
        - código HTTP retornado pelo integrador.

    O teste considera respostas 400/401/403/404/405/415/422 como
    respostas tecnicamente válidas para o teste de responsividade,
    pois demonstram que o servidor recebeu e processou a requisição.

    Um HTTP 2xx é tratado como ATENÇÃO, porque um payload vazio
    não deveria ser usado como carga acadêmica.

    Returns:
        True se foi possível obter uma resposta HTTP.
    """

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QSTIONE_TOKEN}",
    }

    payload = {}

    status(
        "\n[TESTE 1] POST de responsividade",
        CYAN,
    )

    print(f"Endpoint : {QSTIONE_BASE_URL}")
    print(f"Token    : {mascarar_token(QSTIONE_TOKEN)}")
    print(f"Timeout  : {QSTIONE_TIMEOUT}s")
    print(f"SSL      : {QSTIONE_SSL_VERIFY}")
    print("Payload  : {}")
    print()

    inicio = time.perf_counter()

    try:
        response = requests.post(
            QSTIONE_BASE_URL,
            headers=headers,
            json=payload,
            timeout=QSTIONE_TIMEOUT,
            verify=QSTIONE_SSL_VERIFY,
        )

    except requests.exceptions.SSLError as exc:
        tempo = time.perf_counter() - inicio

        status(
            f"FALHA TLS após {tempo:.3f}s",
            RED,
        )
        print(exc)
        return False

    except requests.exceptions.Timeout as exc:
        tempo = time.perf_counter() - inicio

        status(
            f"TIMEOUT após {tempo:.3f}s",
            RED,
        )
        print(exc)
        return False

    except requests.exceptions.ConnectionError as exc:
        tempo = time.perf_counter() - inicio

        status(
            f"FALHA DE CONEXÃO após {tempo:.3f}s",
            RED,
        )
        print(exc)
        return False

    except requests.exceptions.RequestException as exc:
        tempo = time.perf_counter() - inicio

        status(
            f"ERRO HTTP após {tempo:.3f}s",
            RED,
        )
        print(exc)
        return False

    tempo = time.perf_counter() - inicio

    print(f"HTTP     : {response.status_code}")
    print(f"Tempo    : {tempo:.3f}s")
    print(f"Servidor : {response.headers.get('Server', '(não informado)')}")
    print()
    print("Resposta:")
    print(formatar_resposta(response))
    print()

    if response.status_code in {
        400,
        401,
        403,
        404,
        405,
        415,
        422,
    }:
        status(
            "OK: o endpoint respondeu ao POST.",
            GREEN,
        )
        return True

    if 200 <= response.status_code < 300:
        status(
            "ATENÇÃO: o endpoint retornou sucesso para {}.".format(
                response.status_code
            ),
            YELLOW,
        )
        status(
            "Não consideramos isso uma validação segura de carga.",
            YELLOW,
        )
        return True

    if 500 <= response.status_code < 600:
        status(
            "SERVIDOR RESPONDEU, mas retornou erro 5xx.",
            YELLOW,
        )
        return True

    status(
        "Servidor respondeu com um código HTTP inesperado.",
        YELLOW,
    )
    return True


def executar_teste_autenticacao_invalida() -> bool:
    """
    Testa o comportamento da autenticação usando um token falso.

    Este teste também utiliza POST com payload vazio.

    A expectativa normal é HTTP 401 ou 403.

    Returns:
        True quando o servidor respondeu.
    """

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer TOKEN_INVALIDO_QSTIONE_TESTE",
    }

    status(
        "\n[TESTE 2] POST com token inválido",
        CYAN,
    )

    inicio = time.perf_counter()

    try:
        response = requests.post(
            QSTIONE_BASE_URL,
            headers=headers,
            json={},
            timeout=QSTIONE_TIMEOUT,
            verify=QSTIONE_SSL_VERIFY,
        )

    except requests.exceptions.RequestException as exc:
        tempo = time.perf_counter() - inicio

        status(
            f"Falha de comunicação após {tempo:.3f}s",
            RED,
        )
        print(exc)
        return False

    tempo = time.perf_counter() - inicio

    print(f"HTTP  : {response.status_code}")
    print(f"Tempo : {tempo:.3f}s")
    print("Resposta:")
    print(formatar_resposta(response))
    print()

    if response.status_code in {401, 403}:
        status(
            "OK: o endpoint rejeitou corretamente o token inválido.",
            GREEN,
        )
        return True

    status(
        "ATENÇÃO: o comportamento não foi o esperado para token inválido.",
        YELLOW,
    )

    return True


def main() -> int:
    """
    Executa os testes do Sandbox.

    Returns:
        Código de saída:
            0 = comunicação testada com sucesso;
            1 = erro de configuração ou comunicação.
    """

    print("=" * 80)
    status(
        "QSTIONE SANDBOX - TESTE DE RESPONSIVIDADE",
        BOLD + CYAN,
    )
    print("=" * 80)

    print(f"Projeto : {PROJECT_ROOT}")
    print(f".env    : {ENV_FILE}")
    print(f"Endpoint: {QSTIONE_BASE_URL}")

    if not validar_configuracao():
        print()
        status(
            "Configuração inválida. Corrija o .env antes de continuar.",
            RED,
        )
        return 1

    primeiro_teste = executar_post_teste()

    if not primeiro_teste:
        print()
        status(
            "O Sandbox não respondeu ao POST.",
            RED,
        )
        return 1

    executar_teste_autenticacao_invalida()

    print()
    print("=" * 80)
    status(
        "TESTE FINALIZADO",
        BOLD + CYAN,
    )
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
