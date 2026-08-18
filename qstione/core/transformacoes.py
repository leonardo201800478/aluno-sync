"""
qstione/core/transformacoes.py
Funções de transformação de dados
"""

import re
import unicodedata

def extrair_usuario_email(email):
    """
    Extrai a parte do email antes do '@' e converte para minúsculas
    Exemplo: LUIGI.ANDRIGHI@FOA.ORG.BR -> luigi.andrighi
    """
    if not email:
        return None
    
    email_str = str(email).strip()
    pos_arroba = email_str.find('@')
    if pos_arroba > 0:
        return email_str[:pos_arroba].lower()
    return email_str.lower()

def converter_minusculas(texto):
    """Converte texto para minúsculas"""
    if texto:
        return str(texto).lower()
    return texto

def converter_inteiro(valor):
    """Converte valor para inteiro"""
    if valor is None:
        return None
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        return None

def valor_fixo_4000000001(texto):
    """Retorna valor fixo '4000000001'"""
    return '4000000001'

def valor_fixo_2026_2(texto):
    """Retorna valor fixo '2026.2'"""
    return '2026.2'

def valor_fixo_vazio(texto):
    """Retorna string vazia"""
    return ''

def formatar_cpf(cpf):
    """Formata CPF para o padrão 000.000.000-00"""
    if not cpf:
        return None
    cpf_str = str(cpf).replace('.', '').replace('-', '').strip()
    if len(cpf_str) == 11 and cpf_str.isdigit():
        return f"{cpf_str[:3]}.{cpf_str[3:6]}.{cpf_str[6:9]}-{cpf_str[9:]}"
    return cpf_str

def truncar_texto(texto, limite=None):
    """Trunca texto para o limite especificado"""
    if limite is None:
        limite = 100
    if texto and len(str(texto)) > limite:
        return str(texto)[:limite]
    return texto

def remover_acentos(texto):
    """Remove acentos do texto"""
    if not texto:
        return texto
    texto = unicodedata.normalize('NFD', str(texto))
    return texto.encode('ascii', 'ignore').decode('utf-8')

def gerar_codigo_disciplina_curso(codigo_disciplina, nome_curso, curso_id):
    """
    Gera código da disciplina formatado: código-disciplina + '-' + iniciais do curso.
    Para Medicina (005/014), mantém somente o código original da disciplina.
    """
    if curso_id in ['005', '014']:
        return str(codigo_disciplina)[:30]

    palavras = str(nome_curso).strip().split()
    iniciais = []
    for palavra in palavras:
        palavra_limpa = re.sub(r'[^a-zA-ZÀ-ÿ]', '', palavra)
        if len(palavra_limpa) >= 3:
            iniciais.append(palavra_limpa[:3].upper())
        elif palavra_limpa:
            iniciais.append(palavra_limpa.upper())

    iniciais_str = ''.join(iniciais)
    codigo_final = f"{codigo_disciplina}-{iniciais_str}" if iniciais_str else str(codigo_disciplina)
    return codigo_final[:30]

def extrair_iniciais_curso(nome_curso, limite=30):
    """Extrai as três primeiras letras de cada palavra do nome do curso."""
    if not nome_curso:
        return ""
    palavras = str(nome_curso).strip().split()
    iniciais = []
    for palavra in palavras:
        palavra_limpa = re.sub(r'[^a-zA-ZÀ-ÿ]', '', palavra)
        if len(palavra_limpa) >= 3:
            iniciais.append(palavra_limpa[:3].upper())
        elif palavra_limpa:
            iniciais.append(palavra_limpa.upper())
    return ''.join(iniciais)[:limite]

def gerar_codigo_oferta(disciplina, turma, ano, semestre):
    """Gera código da oferta: disciplina + '_' + turma + '_' + ano + semestre."""
    if not all([disciplina, turma, ano, semestre]):
        return None
    return f"{disciplina}_{turma}_{ano}{semestre}"[:30]

def gerar_codigo_disciplina_oferta(disciplina, nome_curso, curso_id):
    """Gera código de disciplina de oferta usando a mesma regra do imp_002."""
    return gerar_codigo_disciplina_curso(disciplina, nome_curso, curso_id)

def gerar_codigo_tipo_oferta(turma):
    """
    Determina o tipo da oferta.

    Regras do Lyceum utilizadas pelo projeto:
    - T0* -> REG (regular)
    - T2* -> REC (recuperação)
    - T3* -> REP (reposição/reprovação)
    - E*   -> REG (turmas especiais que, no conjunto atual do Lyceum,
      continuam sendo ofertas regulares)

    O reconhecimento de E* é necessário porque existem turmas reais como
    E253_E10N, E253_E8N e E263_E07N. Sem essa regra elas produzem NULL em
    codigoTipoOferta, que é uma coluna NOT NULL da imp_005_ofertas.
    """
    if not turma:
        return None

    turma_str = str(turma).strip().upper()
    if turma_str.startswith('T0') or turma_str.startswith('E'):
        return 'REG'
    if turma_str.startswith('T2'):
        return 'REC'
    if turma_str.startswith('T3'):
        return 'REP'
    return None

def gerar_codigo_oferta_origem(disciplina, turma, ano, semestre, turmas_regulares):
    """Gera código da oferta de origem para turmas REC ou REP."""
    if not turma or not turma.startswith(('T2', 'T3')):
        return ''
    turma_regular = None
    for reg_turma in turmas_regulares.get((disciplina, ano, semestre), []):
        if reg_turma.startswith('T0'):
            turma_regular = reg_turma
            break
    if turma_regular:
        return gerar_codigo_oferta(disciplina, turma_regular, ano, semestre)
    return ''

def gerar_email_aluno(matricula, unidade_ensino):
    """Gera o e-mail do aluno baseado na unidade de ensino."""
    if not matricula:
        return None
    matricula_str = str(matricula).strip()
    dominio = '@etecfoa.com.br' if unidade_ensino == '007' else '@unifoa.edu.br'
    return (matricula_str + dominio).lower()

def determinar_papel_usuario(num_func, curso, coordenadores_dict):
    """Determina o papel do usuário: C para coordenador, P para professor."""
    if not num_func or not curso:
        return 'P'
    if (str(num_func), str(curso)) in coordenadores_dict:
        return 'C'
    return 'P'

def mapear_turno(turno):
    """Mapeia o turno para M, T, N, I ou O."""
    if not turno:
        return None
    turno_str = str(turno).strip().upper()
    if turno_str in ['M', 'MANHÃ', 'MANHA', 'MANH']:
        return 'M'
    if turno_str in ['T', 'TARDE', 'TARD']:
        return 'T'
    if turno_str in ['N', 'NOITE', 'NOIT']:
        return 'N'
    if turno_str in ['I', 'INTEGRAL', 'INT']:
        return 'I'
    return 'O'