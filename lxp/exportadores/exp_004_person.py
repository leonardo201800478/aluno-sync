"""
lxp/exportadores/exp_004_person.py

Exportação de Pessoas do Lyceum para o LXP.

Fluxo:

    LY_PESSOA
        ↓
    validação / transformação
        ↓
    lxp_person
        ↓
    person.unifoa2.csv

Execução:
    Botão PLAY do VS Code.

REGRAS
------
1. Sempre consulta TODAS as pessoas da LY_PESSOA.

2. externalId:
       LY_PESSOA.pessoa

3. Pessoa existente na tabela lxp_person:
       UPDATE

4. Pessoa inexistente na tabela lxp_person:
       INSERT

5. CPF:
       - remove máscara;
       - completa zeros à esquerda;
       - deve possuir 11 dígitos;
       - valida os dois dígitos verificadores;
       - CPF inválido não é exportado.

6. user.email:
       prioridade:
           e_mail
           e_mail_com
           e_mail_interno
           mailbox

7. user.username:
       e-mail terminado em @foa.org.br:
           próprio e-mail

       qualquer outro domínio:
           CPF

8. user.password:
       sempre o CPF validado.

9. address.state:
       RJ

10. CSV:
       separador ;
       encoding utf-8-sig

11. O CSV representa o estado completo atual das pessoas válidas
    encontradas no Lyceum.

12. A tabela lxp_person é sincronizada incrementalmente através
    do externalId.
"""

# ============================================================================
# PATH DO PROJETO
# ============================================================================

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).parent.parent.parent)
)


# ============================================================================
# IMPORTS
# ============================================================================

import os
import re

import pandas as pd

from core.logger import logger
from core.database import (
    get_db_connection,
    execute_query,
    fetch_one,
)


# ============================================================================
# CONFIGURAÇÕES
# ============================================================================

DATABASE_LYCEUM = "lyceum"

DATABASE_LXP = "lxp"

TABELA_LXP = "lxp_person"

DIRETORIO_EXPORTACAO = "exportacoes/lxp"

ARQUIVO_CSV = (
    "exportacoes/lxp/person.unifoa2.csv"
)

ESTADO_PADRAO = "RJ"

DOMINIO_INSTITUCIONAL = "@foa.org.br"


# ============================================================================
# COLUNAS DO CSV
# ============================================================================

COLUNAS_CSV = [
    "name",
    "socialName",
    "identityDocument",
    "identityDocumentTypeId",
    "passportNumber",
    "externalId",
    "address.zipCode",
    "address.state",
    "address.city",
    "address.address",
    "address.number",
    "address.neighborhood",
    "address.complement",
    "user.email",
    "user.username",
    "user.password",
    "tags",
    "isActive",
]


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================


def limpar_texto(valor):
    """
    Converte um valor para string e remove espaços externos.

    Parameters
    ----------
    valor:
        Valor original.

    Returns
    -------
    str
        Texto limpo ou string vazia.
    """

    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except (TypeError, ValueError):
        pass

    return str(valor).strip()


def limpar_documento(valor):
    """
    Remove todos os caracteres não numéricos.

    Utilizado principalmente para CPF e CEP.

    Parameters
    ----------
    valor:
        Valor original.

    Returns
    -------
    str
        Somente os dígitos encontrados.
    """

    valor = limpar_texto(valor)

    if not valor:
        return ""

    return re.sub(
        r"\D",
        "",
        valor
    )


# ============================================================================
# CPF
# ============================================================================


def normalizar_cpf(valor):
    """
    Normaliza o CPF.

    Remove máscara e completa zeros à esquerda até 11 dígitos.

    Exemplos
    --------
    1234567890
        -> 01234567890

    123.456.789-09
        -> 12345678909

    Parameters
    ----------
    valor:
        CPF original.

    Returns
    -------
    str
        CPF normalizado ou string vazia.
    """

    cpf = limpar_documento(valor)

    if not cpf:
        return ""

    if len(cpf) > 11:
        return ""

    return cpf.zfill(11)


def validar_cpf(valor):
    """
    Valida matematicamente um CPF.

    Verifica:

        - exatamente 11 dígitos;
        - não ser composto por um único dígito;
        - primeiro dígito verificador;
        - segundo dígito verificador.

    Parameters
    ----------
    valor:
        CPF original ou normalizado.

    Returns
    -------
    tuple[str, bool]
        CPF normalizado e resultado da validação.
    """

    cpf = normalizar_cpf(valor)

    if not cpf:
        return "", False

    if len(cpf) != 11:
        return cpf, False

    if len(set(cpf)) == 1:
        return cpf, False

    # ------------------------------------------------------------------------
    # Primeiro dígito verificador
    # ------------------------------------------------------------------------

    soma = 0

    for indice in range(9):
        soma += (
            int(cpf[indice])
            * (10 - indice)
        )

    resto = soma % 11

    digito1 = (
        0
        if resto < 2
        else 11 - resto
    )

    if digito1 != int(cpf[9]):
        return cpf, False

    # ------------------------------------------------------------------------
    # Segundo dígito verificador
    # ------------------------------------------------------------------------

    soma = 0

    for indice in range(10):
        soma += (
            int(cpf[indice])
            * (11 - indice)
        )

    resto = soma % 11

    digito2 = (
        0
        if resto < 2
        else 11 - resto
    )

    if digito2 != int(cpf[10]):
        return cpf, False

    return cpf, True


def preparar_cpf(valor, external_id):
    """
    Normaliza e valida o CPF de uma pessoa.

    CPF vazio não é considerado erro de cadastro da pessoa.

    CPF informado, porém inválido, provoca descarte do registro.

    Parameters
    ----------
    valor:
        CPF original.

    external_id:
        Código da pessoa no Lyceum.

    Returns
    -------
    str
        CPF válido com 11 dígitos ou string vazia.

    Raises
    ------
    ValueError
        Quando o CPF informado é inválido.
    """

    cpf_original = limpar_texto(
        valor
    )

    if not cpf_original:
        return ""

    cpf, valido = validar_cpf(
        cpf_original
    )

    if not valido:

        logger.error(
            "CPF inválido: externalId=%s | CPF=%s",
            external_id,
            cpf_original
        )

        raise ValueError(
            f"CPF inválido para externalId={external_id}"
        )

    return cpf


# ============================================================================
# E-MAIL
# ============================================================================


def normalizar_email(valor):
    """
    Normaliza um endereço de e-mail.

    Parameters
    ----------
    valor:
        E-mail original.

    Returns
    -------
    str
        E-mail em letras minúsculas e sem espaços externos.
    """

    valor = limpar_texto(valor)

    if not valor:
        return ""

    return valor.lower()


def selecionar_email(row):
    """
    Seleciona o melhor e-mail disponível.

    Ordem de prioridade:

        1. e_mail
        2. e_mail_com
        3. e_mail_interno
        4. mailbox

    Parameters
    ----------
    row:
        Linha do DataFrame.

    Returns
    -------
    str
        E-mail selecionado.
    """

    candidatos = [
        row.get("e_mail"),
        row.get("e_mail_com"),
        row.get("e_mail_interno"),
        row.get("mailbox"),
    ]

    for candidato in candidatos:

        email = normalizar_email(
            candidato
        )

        if email:
            return email

    return ""


def gerar_username(
    email,
    identity_document
):
    """
    Gera o username conforme o domínio do e-mail.

    @foa.org.br:
        username = próprio e-mail

    Outros domínios:
        username = CPF

    Sem CPF:
        username = vazio

    Parameters
    ----------
    email:
        E-mail selecionado.

    identity_document:
        CPF validado.

    Returns
    -------
    str
        Username.
    """

    email = normalizar_email(
        email
    )

    identity_document = limpar_texto(
        identity_document
    )

    if not identity_document:
        return ""

    if email.endswith(
        DOMINIO_INSTITUCIONAL
    ):
        return email

    return identity_document


# ============================================================================
# CONSULTA LYCEUM
# ============================================================================


def obter_pessoas_lyceum():
    """
    Busca todas as pessoas cadastradas na LY_PESSOA.

    Não existe filtro por pessoa nesta etapa.

    Returns
    -------
    pandas.DataFrame
        Todas as pessoas encontradas.
    """

    logger.info(
        "Consultando todas as pessoas da LY_PESSOA..."
    )

    sql = """
        SELECT

            p.pessoa AS externalId,

            p.nome_compl AS name,

            p.nome_social AS socialName,

            p.cpf AS identityDocument,

            p.passaporte AS passportNumber,

            p.cep AS [address.zipCode],

            p.end_municipio AS [address.city],

            p.endereco AS [address.address],

            p.end_num AS [address.number],

            p.bairro AS [address.neighborhood],

            p.end_compl AS [address.complement],

            p.e_mail AS e_mail,

            p.e_mail_com AS e_mail_com,

            p.e_mail_interno AS e_mail_interno,

            p.mailbox AS mailbox

        FROM LY_PESSOA p

        WHERE p.pessoa IS NOT NULL

          AND p.nome_compl IS NOT NULL

          AND LTRIM(RTRIM(p.nome_compl)) <> ''

        ORDER BY p.pessoa
    """

    try:

        with get_db_connection(
            database_name=DATABASE_LYCEUM
        ) as conn:

            df = pd.read_sql_query(
                sql,
                conn
            )

        logger.info(
            "Pessoas encontradas na LY_PESSOA: %d",
            len(df)
        )

        return df

    except Exception as e:

        logger.exception(
            "Erro ao consultar LY_PESSOA: %s",
            e
        )

        raise


# ============================================================================
# TRANSFORMAÇÃO
# ============================================================================


def transformar_pessoas(df):
    """
    Transforma os dados do Lyceum no layout do LXP.

    Regras:

        - valida externalId;
        - valida nome;
        - normaliza CPF;
        - valida CPF;
        - seleciona e-mail;
        - gera username;
        - gera password;
        - fixa estado como RJ;
        - remove duplicidades.

    Parameters
    ----------
    df:
        DataFrame original da LY_PESSOA.

    Returns
    -------
    pandas.DataFrame
        DataFrame pronto para sincronização e CSV.
    """

    logger.info(
        "Transformando e validando pessoas..."
    )

    registros = []

    descartados_sem_id = 0
    descartados_sem_nome = 0
    cpfs_invalidos = 0

    for _, row in df.iterrows():

        # ====================================================================
        # EXTERNAL ID
        # ====================================================================

        external_id = limpar_texto(
            row["externalId"]
        )

        if not external_id:

            descartados_sem_id += 1

            logger.warning(
                "Pessoa sem externalId. Registro descartado."
            )

            continue

        # ====================================================================
        # NOME
        # ====================================================================

        name = limpar_texto(
            row["name"]
        )

        if not name:

            descartados_sem_nome += 1

            logger.warning(
                "externalId=%s sem nome. Registro descartado.",
                external_id
            )

            continue

        # ====================================================================
        # CPF
        # ====================================================================

        try:

            cpf = preparar_cpf(
                row["identityDocument"],
                external_id
            )

        except ValueError:

            cpfs_invalidos += 1

            continue

        # ====================================================================
        # E-MAIL
        # ====================================================================

        email = selecionar_email(
            row
        )

        # ====================================================================
        # USERNAME
        # ====================================================================

        username = gerar_username(
            email,
            cpf
        )

        # ====================================================================
        # PASSWORD
        # ====================================================================
        #
        # Sempre o CPF.
        #
        # ====================================================================

        password = cpf

        # ====================================================================
        # REGISTRO FINAL
        # ====================================================================

        registro = {

            "name": name,

            "socialName": limpar_texto(
                row["socialName"]
            ),

            "identityDocument": cpf,

            "identityDocumentTypeId": (
                "CPF"
                if cpf
                else ""
            ),

            "passportNumber": limpar_texto(
                row["passportNumber"]
            ),

            "externalId": external_id,

            "address.zipCode": limpar_documento(
                row["address.zipCode"]
            ),

            "address.state": ESTADO_PADRAO,

            "address.city": limpar_texto(
                row["address.city"]
            ),

            "address.address": limpar_texto(
                row["address.address"]
            ),

            "address.number": limpar_texto(
                row["address.number"]
            ),

            "address.neighborhood": limpar_texto(
                row["address.neighborhood"]
            ),

            "address.complement": limpar_texto(
                row["address.complement"]
            ),

            "user.email": email,

            "user.username": username,

            "user.password": password,

            "tags": "",

            "isActive": "true",
        }

        registros.append(
            registro
        )

    # =========================================================================
    # DATAFRAME FINAL
    # =========================================================================

    resultado = pd.DataFrame(
        registros,
        columns=COLUNAS_CSV
    )

    # =========================================================================
    # DEDUPLICAÇÃO
    # =========================================================================

    if not resultado.empty:

        quantidade_antes = len(
            resultado
        )

        resultado = (
            resultado
            .drop_duplicates(
                subset=["externalId"],
                keep="first"
            )
            .reset_index(drop=True)
        )

        duplicados = (
            quantidade_antes
            - len(resultado)
        )

        if duplicados > 0:

            logger.warning(
                "Duplicidades removidas por externalId: %d",
                duplicados
            )

    # =========================================================================
    # RESUMO
    # =========================================================================

    logger.info(
        "Pessoas válidas: %d",
        len(resultado)
    )

    logger.info(
        "Descartadas sem externalId: %d",
        descartados_sem_id
    )

    logger.info(
        "Descartadas sem nome: %d",
        descartados_sem_nome
    )

    logger.info(
        "Descartadas por CPF inválido: %d",
        cpfs_invalidos
    )

    return resultado


# ============================================================================
# TABELA LXP
# ============================================================================


def criar_tabela_person():
    """
    Cria a tabela lxp_person caso ela ainda não exista.

    Returns
    -------
    bool
        True se a tabela estiver disponível.
    """

    logger.info(
        "Verificando tabela %s...",
        TABELA_LXP
    )

    try:

        sql_check = """
            SELECT COUNT(*)
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = ?
        """

        result = fetch_one(
            sql_check,
            (TABELA_LXP,),
            database_name=DATABASE_LXP
        )

        if result is None:

            logger.error(
                "Não foi possível verificar a tabela %s.",
                TABELA_LXP
            )

            return False

        if result[0] > 0:

            logger.info(
                "Tabela %s já existe.",
                TABELA_LXP
            )

            return True

        logger.info(
            "Criando tabela %s...",
            TABELA_LXP
        )

        sql_create = f"""
            CREATE TABLE {TABELA_LXP} (

                externalId NVARCHAR(50) NOT NULL
                    PRIMARY KEY,

                name NVARCHAR(500) NOT NULL,

                socialName NVARCHAR(500) NULL,

                identityDocument NVARCHAR(30) NULL,

                identityDocumentTypeId NVARCHAR(20) NULL,

                passportNumber NVARCHAR(50) NULL,

                [address.zipCode] NVARCHAR(20) NULL,

                [address.state] NVARCHAR(10) NULL,

                [address.city] NVARCHAR(100) NULL,

                [address.address] NVARCHAR(255) NULL,

                [address.number] NVARCHAR(30) NULL,

                [address.neighborhood] NVARCHAR(100) NULL,

                [address.complement] NVARCHAR(255) NULL,

                [user.email] NVARCHAR(255) NULL,

                [user.username] NVARCHAR(255) NULL,

                [user.password] NVARCHAR(255) NULL,

                tags NVARCHAR(255) NULL,

                isActive NVARCHAR(10) NOT NULL
                    DEFAULT 'true',

                created_at DATETIME DEFAULT GETDATE(),

                updated_at DATETIME DEFAULT GETDATE()
            );
        """

        execute_query(
            sql_create,
            database_name=DATABASE_LXP
        )

        logger.info(
            "Tabela %s criada com sucesso.",
            TABELA_LXP
        )

        return True

    except Exception as e:

        logger.exception(
            "Erro ao criar tabela %s: %s",
            TABELA_LXP,
            e
        )

        return False


# ============================================================================
# SINCRONIZAÇÃO
# ============================================================================


def sincronizar_pessoas(df):
    """
    Sincroniza as pessoas com lxp_person.

    Regra:

        externalId existente:
            UPDATE

        externalId inexistente:
            INSERT

    Não utiliza MERGE. A existência da pessoa é verificada antes
    da operação para deixar explícito o comportamento.

    Parameters
    ----------
    df:
        DataFrame final.

    Returns
    -------
    bool
        True quando não houver erros.
    """

    logger.info(
        "Iniciando sincronização com %s...",
        TABELA_LXP
    )

    sql_existe = f"""
        SELECT COUNT(*)
        FROM {TABELA_LXP}
        WHERE externalId = ?
    """

    sql_update = f"""
        UPDATE {TABELA_LXP}
        SET
            name = ?,
            socialName = ?,
            identityDocument = ?,
            identityDocumentTypeId = ?,
            passportNumber = ?,
            [address.zipCode] = ?,
            [address.state] = ?,
            [address.city] = ?,
            [address.address] = ?,
            [address.number] = ?,
            [address.neighborhood] = ?,
            [address.complement] = ?,
            [user.email] = ?,
            [user.username] = ?,
            [user.password] = ?,
            tags = ?,
            isActive = ?,
            updated_at = GETDATE()
        WHERE externalId = ?
    """

    sql_insert = f"""
        INSERT INTO {TABELA_LXP} (
            externalId,
            name,
            socialName,
            identityDocument,
            identityDocumentTypeId,
            passportNumber,
            [address.zipCode],
            [address.state],
            [address.city],
            [address.address],
            [address.number],
            [address.neighborhood],
            [address.complement],
            [user.email],
            [user.username],
            [user.password],
            tags,
            isActive
        )
        VALUES (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
    """

    inseridos = 0
    atualizados = 0
    erros = 0

    for _, row in df.iterrows():

        external_id = row["externalId"]

        try:

            # ================================================================
            # VERIFICA EXISTÊNCIA
            # ================================================================

            resultado = fetch_one(
                sql_existe,
                (external_id,),
                database_name=DATABASE_LXP
            )

            if resultado is None:

                raise RuntimeError(
                    "Não foi possível verificar "
                    "a existência da pessoa."
                )

            existe = (
                resultado[0] > 0
            )

            # ================================================================
            # UPDATE
            # ================================================================

            if existe:

                parametros = (
                    row["name"],
                    row["socialName"],
                    row["identityDocument"],
                    row["identityDocumentTypeId"],
                    row["passportNumber"],
                    row["address.zipCode"],
                    row["address.state"],
                    row["address.city"],
                    row["address.address"],
                    row["address.number"],
                    row["address.neighborhood"],
                    row["address.complement"],
                    row["user.email"],
                    row["user.username"],
                    row["user.password"],
                    row["tags"],
                    row["isActive"],
                    external_id,
                )

                execute_query(
                    sql_update,
                    parametros,
                    database_name=DATABASE_LXP
                )

                atualizados += 1

            # ================================================================
            # INSERT
            # ================================================================

            else:

                parametros = (
                    external_id,
                    row["name"],
                    row["socialName"],
                    row["identityDocument"],
                    row["identityDocumentTypeId"],
                    row["passportNumber"],
                    row["address.zipCode"],
                    row["address.state"],
                    row["address.city"],
                    row["address.address"],
                    row["address.number"],
                    row["address.neighborhood"],
                    row["address.complement"],
                    row["user.email"],
                    row["user.username"],
                    row["user.password"],
                    row["tags"],
                    row["isActive"],
                )

                execute_query(
                    sql_insert,
                    parametros,
                    database_name=DATABASE_LXP
                )

                inseridos += 1

        except Exception as e:

            erros += 1

            logger.error(
                "Erro ao sincronizar externalId=%s: %s",
                external_id,
                e
            )

    # =========================================================================
    # RESULTADO
    # =========================================================================

    logger.info(
        "Sincronização concluída."
    )

    logger.info(
        "  Inseridos   : %d",
        inseridos
    )

    logger.info(
        "  Atualizados : %d",
        atualizados
    )

    logger.info(
        "  Erros       : %d",
        erros
    )

    logger.info(
        "  Total        : %d",
        inseridos + atualizados + erros
    )

    return erros == 0


# ============================================================================
# CSV
# ============================================================================


def gerar_csv(df):
    """
    Gera o arquivo person.unifoa2.csv.

    Parameters
    ----------
    df:
        DataFrame final.

    Returns
    -------
    bool
        True se o arquivo foi gerado com sucesso.
    """

    logger.info(
        "Gerando CSV..."
    )

    try:

        os.makedirs(
            DIRETORIO_EXPORTACAO,
            exist_ok=True
        )

        df_csv = (
            df[
                COLUNAS_CSV
            ]
            .copy()
            .fillna("")
        )

        df_csv.to_csv(
            ARQUIVO_CSV,
            sep=";",
            index=False,
            encoding="utf-8-sig"
        )

        logger.info(
            "CSV salvo em: %s",
            ARQUIVO_CSV
        )

        logger.info(
            "Registros no CSV: %d",
            len(df_csv)
        )

        return True

    except Exception as e:

        logger.exception(
            "Erro ao gerar CSV: %s",
            e
        )

        return False


# ============================================================================
# ESTATÍSTICAS
# ============================================================================


def exibir_estatisticas(df):
    """
    Exibe estatísticas da exportação.

    Parameters
    ----------
    df:
        DataFrame final.
    """

    if df.empty:
        return

    total = len(df)

    com_cpf = (
        df["identityDocument"]
        .ne("")
        .sum()
    )

    com_email = (
        df["user.email"]
        .ne("")
        .sum()
    )

    emails_foa = (
        df["user.email"]
        .str.endswith(
            DOMINIO_INSTITUCIONAL
        )
        .sum()
    )

    usernames_cpf = (
        (
            df["user.email"]
            != ""
        )
        &
        ~df["user.email"].str.endswith(
            DOMINIO_INSTITUCIONAL
        )
    ).sum()

    sem_email = (
        df["user.email"]
        .eq("")
        .sum()
    )

    logger.info(
        "Estatísticas:"
    )

    logger.info(
        "  Total de pessoas        : %d",
        total
    )

    logger.info(
        "  CPF válido              : %d",
        com_cpf
    )

    logger.info(
        "  Com e-mail              : %d",
        com_email
    )

    logger.info(
        "  E-mail @foa.org.br      : %d",
        emails_foa
    )

    logger.info(
        "  Username baseado no CPF: %d",
        usernames_cpf
    )

    logger.info(
        "  Sem e-mail              : %d",
        sem_email
    )


# ============================================================================
# AMOSTRA
# ============================================================================


def exibir_amostra(df):
    """
    Exibe até 10 registros no log.

    A senha nunca é exibida.

    Parameters
    ----------
    df:
        DataFrame final.
    """

    if df.empty:

        logger.warning(
            "Nenhum registro para exibir."
        )

        return

    logger.info(
        "Amostra dos registros:"
    )

    amostra = df[
        [
            "externalId",
            "name",
            "identityDocument",
            "user.email",
            "user.username",
            "address.city",
            "isActive",
        ]
    ].head(10)

    for _, row in amostra.iterrows():

        logger.info(
            "externalId=%s | name=%s | CPF=%s | "
            "email=%s | username=%s | cidade=%s | active=%s",

            row["externalId"],
            row["name"],
            row["identityDocument"],
            row["user.email"],
            row["user.username"],
            row["address.city"],
            row["isActive"],
        )


# ============================================================================
# EXECUÇÃO
# ============================================================================


def run() -> bool:
    """
    Executa a exportação completa de Pessoas.

    Fluxo:

        1. Busca todas as pessoas no Lyceum.
        2. Normaliza e valida os dados.
        3. Cria lxp_person se necessário.
        4. Para cada externalId:
               existente     -> UPDATE
               inexistente   -> INSERT
        5. Gera o CSV completo.

    Returns
    -------
    bool
        True quando o processo termina sem erros.
    """

    logger.info(
        "============================================================"
    )

    logger.info(
        "=== INÍCIO DA EXPORTAÇÃO DE PESSOAS ==="
    )

    logger.info(
        "============================================================"
    )

    try:

        # ====================================================================
        # 1. CONSULTA
        # ====================================================================

        df = obter_pessoas_lyceum()

        if df.empty:

            logger.warning(
                "Nenhuma pessoa encontrada na LY_PESSOA."
            )

            if not criar_tabela_person():

                logger.error(
                    "Falha ao criar/verificar tabela LXP."
                )

                return False

            return True

        # ====================================================================
        # 2. TRANSFORMAÇÃO
        # ====================================================================

        df = transformar_pessoas(
            df
        )

        if df.empty:

            logger.error(
                "Nenhuma pessoa válida para exportação."
            )

            return False

        # ====================================================================
        # 3. ESTATÍSTICAS
        # ====================================================================

        exibir_estatisticas(
            df
        )

        # ====================================================================
        # 4. TABELA LXP
        # ====================================================================

        if not criar_tabela_person():

            logger.error(
                "Falha ao criar/verificar tabela %s.",
                TABELA_LXP
            )

            return False

        # ====================================================================
        # 5. SINCRONIZAÇÃO
        # ====================================================================

        if not sincronizar_pessoas(
            df
        ):

            logger.error(
                "A sincronização terminou com erros."
            )

            return False

        # ====================================================================
        # 6. AMOSTRA
        # ====================================================================

        exibir_amostra(
            df
        )

        # ====================================================================
        # 7. CSV
        # ====================================================================

        if not gerar_csv(
            df
        ):

            logger.error(
                "Falha ao gerar CSV."
            )

            return False

        # ====================================================================
        # FINAL
        # ====================================================================

        logger.info(
            "============================================================"
        )

        logger.info(
            "=== EXPORTAÇÃO DE PESSOAS CONCLUÍDA COM SUCESSO ==="
        )

        logger.info(
            "Total de pessoas processadas: %d",
            len(df)
        )

        logger.info(
            "CSV: %s",
            ARQUIVO_CSV
        )

        logger.info(
            "============================================================"
        )

        return True

    except Exception as e:

        logger.exception(
            "Exceção não tratada no run(): %s",
            e
        )

        return False


# ============================================================================
# EXECUÇÃO PELO PLAY DO VS CODE
# ============================================================================

if __name__ == "__main__":

    sys.exit(
        0 if run() else 1
    )