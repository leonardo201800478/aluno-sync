"""
qstione/core/validacoes.py
Módulo de validações para dados do Qstione
"""

import re
from datetime import datetime


def validar_email(email):
    """
    Valida formato básico de email

    Args:
        email (str): Email a ser validado

    Returns:
        bool: True se o email é válido, False caso contrário
    """
    if not email:
        return False

    email_str = str(email).strip()

    # Verifica se tem '@' e pelo menos um '.' após o '@'
    if '@' not in email_str:
        return False

    # Divide o email em parte local e domínio
    partes = email_str.split('@')

    if len(partes) != 2:
        return False

    local, dominio = partes

    # Verifica se a parte local e o domínio não estão vazios
    if not local or not dominio:
        return False

    # Verifica se o domínio tem pelo menos um ponto
    if '.' not in dominio:
        return False

    # Verifica se não há espaços em branco
    if ' ' in email_str:
        return False

    return True


def validar_cpf(cpf):
    """
    Valida formato de CPF (apenas formato, não cálculo de dígitos)

    Args:
        cpf (str): CPF a ser validado

    Returns:
        bool: True se o CPF tem formato válido, False caso contrário
    """
    if not cpf:
        return False

    cpf_str = str(cpf).strip()

    # Remove pontos e traços
    cpf_limpo = re.sub(r'[\.\-]', '', cpf_str)

    # Deve ter 11 dígitos numéricos
    if not cpf_limpo.isdigit() or len(cpf_limpo) != 11:
        return False

    # Não pode ser uma sequência de números iguais
    if cpf_limpo == cpf_limpo[0] * 11:
        return False

    return True


def validar_matricula(matricula):
    """
    Valida se a matrícula não está vazia

    Args:
        matricula (str): Matrícula a ser validada

    Returns:
        bool: True se a matrícula é válida, False caso contrário
    """
    if not matricula:
        return False

    matricula_str = str(matricula).strip()

    return len(matricula_str) > 0


def validar_nome(nome):
    """
    Valida se o nome não está vazio

    Args:
        nome (str): Nome a ser validado

    Returns:
        bool: True se o nome é válido, False caso contrário
    """
    if not nome:
        return False

    nome_str = str(nome).strip()

    return len(nome_str) > 0


def validar_data(data_str, formato="%Y-%m-%d"):
    """
    Valida se uma string é uma data válida

    Args:
        data_str (str): String da data
        formato (str): Formato esperado da data

    Returns:
        bool: True se a data é válida, False caso contrário
    """
    if not data_str:
        return False

    try:
        datetime.strptime(
            str(data_str),
            formato
        )

        return True

    except ValueError:
        return False


def validar_telefone(telefone):
    """
    Valida formato básico de telefone

    Args:
        telefone (str): Telefone a ser validado

    Returns:
        bool: True se o telefone é válido, False caso contrário
    """
    if not telefone:
        return True  # Telefone pode ser opcional

    telefone_str = str(telefone).strip()

    # Remove caracteres não numéricos
    numeros = re.sub(
        r'[^\d]',
        '',
        telefone_str
    )

    # Deve ter entre 10 e 11 dígitos (com DDD)
    if len(numeros) < 10 or len(numeros) > 11:
        return False

    return True


def validar_cep(cep):
    """
    Valida formato de CEP

    Args:
        cep (str): CEP a ser validado

    Returns:
        bool: True se o CEP é válido, False caso contrário
    """
    if not cep:
        return True  # CEP pode ser opcional

    cep_str = str(cep).strip()

    # Remove caracteres não numéricos
    cep_limpo = re.sub(
        r'[^\d]',
        '',
        cep_str
    )

    # Deve ter 8 dígitos
    if len(cep_limpo) != 8 or not cep_limpo.isdigit():
        return False

    return True


def validar_campo_obrigatorio(
    valor,
    nome_campo
):
    """
    Valida se um campo obrigatório não está vazio

    Args:
        valor (any): Valor a ser validado
        nome_campo (str): Nome do campo para mensagem de erro

    Returns:
        tuple: (bool, str) onde bool indica se é válido e str a mensagem de erro
    """
    if not valor:
        return (
            False,
            f"Campo obrigatório '{nome_campo}' não informado"
        )

    valor_str = str(valor).strip()

    if len(valor_str) == 0:
        return (
            False,
            f"Campo obrigatório '{nome_campo}' está vazio"
        )

    return True, ""


def validar_tamanho_maximo(
    valor,
    tamanho_maximo,
    nome_campo
):
    """
    Valida se o valor não excede o tamanho máximo

    Args:
        valor (str): Valor a ser validado
        tamanho_maximo (int): Tamanho máximo permitido
        nome_campo (str): Nome do campo para mensagem de erro

    Returns:
        tuple: (bool, str) onde bool indica se é válido e str a mensagem de erro
    """
    if valor is None:
        return True, ""  # Campos opcionais podem ser nulos

    valor_str = str(valor)

    if len(valor_str) > tamanho_maximo:
        return (
            False,
            f"Campo '{nome_campo}' excede o tamanho máximo de "
            f"{tamanho_maximo} caracteres"
        )

    return True, ""


def validar_formato_email(email):
    """
    Valida formato específico de email institucional

    Args:
        email (str): Email a ser validado

    Returns:
        tuple: (bool, str) onde bool indica se é válido e str a mensagem de erro
    """
    if not validar_email(email):
        return False, "Formato de email inválido"

    email_str = str(email).lower().strip()

    # Verifica se é um email institucional
    dominios_validos = [
        'foa.org.br',
        'unifoa.edu.br',
        'etecfoa.com.br'
    ]

    if not any(
        email_str.endswith(dominio)
        for dominio in dominios_validos
    ):
        return False, "Email não parece ser institucional"

    return True, ""


def validar_ativo(status):
    """
    Valida se o status de ativo é válido

    Args:
        status (str): Status a ser validado

    Returns:
        bool: True se o status é válido, False caso contrário
    """
    if not status:
        return False

    status_str = str(status).upper().strip()

    return status_str in [
        'S',
        'N',
        'A',
        'I',
        '1',
        '0',
        'TRUE',
        'FALSE'
    ]


def validar_genero(genero):
    """
    Valida se o gênero é válido

    Args:
        genero (str): Gênero a ser validado

    Returns:
        bool: True se o gênero é válido, False caso contrário
    """
    if not genero:
        return True  # Gênero pode ser opcional

    genero_str = str(genero).upper().strip()

    generos_validos = [
        'M',
        'F',
        'MASCULINO',
        'FEMININO',
        'MALE',
        'FEMALE'
    ]

    return genero_str in generos_validos


def validar_situacao_aluno(situacao):
    """
    Valida se a situação do aluno é válida

    Args:
        situacao (str): Situação do aluno

    Returns:
        bool: True se a situação é válida, False caso contrário
    """
    if not situacao:
        return True

    situacao_str = str(situacao).upper().strip()

    situacoes_validas = [
        'ATIVO',
        'INATIVO',
        'CURSANDO',
        'FORMADO',
        'EVADIDO',
        'TRANCADO',
        'JUBILADO',
        'S'
    ]

    return situacao_str in situacoes_validas


def validar_registro_docente(registro):
    """
    Valida registro de docente

    Args:
        registro (dict): Dicionário com dados do docente

    Returns:
        tuple: (bool, list) onde bool indica se é válido e lista de erros
    """
    erros = []

    # Validar campos obrigatórios
    campos_obrigatorios = [
        'matricula',
        'email',
        'nome'
    ]

    for campo in campos_obrigatorios:

        if campo not in registro or not registro[campo]:
            erros.append(
                f"Campo obrigatório '{campo}' não informado"
            )

    # Validar email
    if 'email' in registro and registro['email']:

        if not validar_email(
            registro['email']
        ):

            erros.append(
                f"Email inválido: {registro['email']}"
            )

    return len(erros) == 0, erros


def validar_registro_aluno(registro):
    """
    Valida registro de aluno

    Args:
        registro (dict): Dicionário com dados do aluno

    Returns:
        tuple: (bool, list) onde bool indica se é válido e lista de erros
    """
    erros = []

    # Validar campos obrigatórios
    campos_obrigatorios = [
        'matricula',
        'nome'
    ]

    for campo in campos_obrigatorios:

        if campo not in registro or not registro[campo]:
            erros.append(
                f"Campo obrigatório '{campo}' não informado"
            )

    # Validar email se existir
    if 'email' in registro and registro['email']:

        if not validar_email(
            registro['email']
        ):

            erros.append(
                f"Email inválido: {registro['email']}"
            )

    # Validar data de nascimento se existir
    if (
        'data_nascimento' in registro
        and registro['data_nascimento']
    ):

        if not validar_data(
            registro['data_nascimento']
        ):

            erros.append(
                "Data de nascimento inválida: "
                f"{registro['data_nascimento']}"
            )

    return len(erros) == 0, erros


def validar_campo_numerico(
    valor,
    nome_campo,
    valor_min=None,
    valor_max=None
):
    """
    Valida se um campo é numérico e está dentro dos limites

    Args:
        valor: Valor a ser validado
        nome_campo (str): Nome do campo para mensagem de erro
        valor_min: Valor mínimo permitido
        valor_max: Valor máximo permitido

    Returns:
        tuple: (bool, str) onde bool indica se é válido e str a mensagem de erro
    """
    if valor is None:
        return True, ""

    try:

        num = float(valor)

        if (
            valor_min is not None
            and num < valor_min
        ):

            return (
                False,
                f"Campo '{nome_campo}' deve ser maior "
                f"ou igual a {valor_min}"
            )

        if (
            valor_max is not None
            and num > valor_max
        ):

            return (
                False,
                f"Campo '{nome_campo}' deve ser menor "
                f"ou igual a {valor_max}"
            )

        return True, ""

    except (ValueError, TypeError):

        return (
            False,
            f"Campo '{nome_campo}' deve ser um número"
        )


def validar_sigla_curso(sigla):
    """
    Valida sigla de curso

    Args:
        sigla (str): Sigla do curso

    Returns:
        bool: True se a sigla é válida, False caso contrário
    """
    if not sigla:
        return False

    sigla_str = str(
        sigla
    ).strip().upper()

    # Sigla deve ter entre 2 e 10 caracteres
    if len(sigla_str) < 2 or len(sigla_str) > 10:
        return False

    # Deve conter apenas letras e números
    if not re.match(
        r'^[A-Z0-9]+$',
        sigla_str
    ):
        return False

    return True


def validar_codigo_curso(codigo):
    """
    Valida código do curso

    Args:
        codigo (str): Código do curso

    Returns:
        bool: True se o código é válido, False caso contrário
    """
    if not codigo:
        return False

    codigo_str = str(
        codigo
    ).strip()

    return (
        len(codigo_str) > 0
        and len(codigo_str) <= 30
    )


def validar_nome_curso(nome):
    """
    Valida nome do curso

    Args:
        nome (str): Nome do curso

    Returns:
        bool: True se o nome é válido, False caso contrário
    """
    if not nome:
        return False

    nome_str = str(
        nome
    ).strip()

    return (
        len(nome_str) > 0
        and len(nome_str) <= 64
    )


def validar_quant_periodos(quantidade):
    """
    Valida e normaliza a quantidade de períodos.

    Regras:
    - Aceita valores entre 0 e 99
    - Se o valor for 0, normaliza para 1
    - Rejeita None, vazio ou valores não numéricos

    Args:
        quantidade: Quantidade de períodos

    Returns:
        int | None: Valor normalizado (1 a 99) ou None se inválido
    """
    if quantidade is None:
        return None

    try:
        num = int(quantidade)

    except (ValueError, TypeError):
        return None

    if not 0 <= num <= 99:
        return None

    # Regra de negócio: período 0 vira 1
    return 1 if num == 0 else num


def validar_codigo_disciplina(codigo):
    """
    Valida código da disciplina

    Args:
        codigo (str): Código da disciplina

    Returns:
        bool: True se o código é válido, False caso contrário
    """
    if not codigo:
        return False

    codigo_str = str(
        codigo
    ).strip()

    return (
        len(codigo_str) > 0
        and len(codigo_str) <= 30
    )


def validar_nome_disciplina(nome):
    """
    Valida e normaliza o nome da disciplina.

    - Remove espaços extras
    - Encurta para 100 caracteres se exceder
    - Garante que o nome não fique vazio

    Args:
        nome (str): Nome da disciplina

    Returns:
        str | None: Nome válido (possivelmente truncado) ou None se inválido
    """
    if not nome:
        return None

    nome_str = str(
        nome
    ).strip()

    if not nome_str:
        return None

    # Encurta automaticamente se passar de 100 caracteres
    if len(nome_str) > 100:
        nome_str = nome_str[:100]

    return nome_str


def validar_periodo(periodo):
    """
    Valida período da disciplina

    Args:
        periodo: Período da disciplina

    Returns:
        bool: True se o período é válido, False caso contrário
    """
    if periodo is None:
        return False

    try:

        num = int(periodo)

        return 1 <= num <= 99

    except (ValueError, TypeError):

        return False


def validar_papel_usuario(papel):
    """
    Valida o papel do usuário.

    Papéis válidos:
        C = Coordenador
        P = Professor
        A = Membro do NDE

    Args:
        papel:
            Papel do usuário.

    Returns:
        bool:
            True se o papel é válido,
            False caso contrário.
    """
    if papel is None:
        return False

    try:

        papel_str = str(papel)

        return papel_str in [
            'C',
            'P',
            'A'
        ]

    except (ValueError, TypeError):

        return False


# ============================================================================
# DICIONÁRIO DE FUNÇÕES DE VALIDAÇÃO
# ============================================================================

VALIDACOES = {
    'email': validar_email,
    'cpf': validar_cpf,
    'matricula': validar_matricula,
    'nome': validar_nome,
    'data': validar_data,
    'telefone': validar_telefone,
    'cep': validar_cep,
    'ativo': validar_ativo,
    'genero': validar_genero,
    'situacao': validar_situacao_aluno,
    'codigo_disciplina_antigo': validar_codigo_disciplina,
    'sigla_curso': validar_sigla_curso,
    'codigo_curso': validar_codigo_curso,
    'nome_curso': validar_nome_curso,
    'quant_periodos': validar_quant_periodos,
    'codigo_disciplina': validar_codigo_disciplina,
    'nome_disciplina': validar_nome_disciplina,
    'periodo': validar_periodo,
    'papel_usuario': validar_papel_usuario,
}