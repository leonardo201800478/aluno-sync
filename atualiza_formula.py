import pyodbc
from typing import List, Tuple

# ============================================================
# CONFIGURAÇÕES (ALTERE SE NECESSÁRIO)
# ============================================================
SERVER = 'dbsql'                # Nome do servidor (como na extensão)
DATABASE = 'academico'          # Nome do banco de dados
BATCH_SIZE = 100                # Linhas por lote (commit a cada lote)

# Lista de drivers em ordem de preferência (prioridade para compatibilidade com 2008)
DRIVER_CANDIDATES = [
    'SQL Server Native Client 11.0',   # Melhor para SQL Server 2008
    'SQL Server',                      # Driver genérico (mais lento, mas funciona)
    'ODBC Driver 17 for SQL Server',   # Versão mais nova, também compatível
    'ODBC Driver 18 for SQL Server'
]

# ============================================================
# FUNÇÃO PARA ENCONTRAR DRIVER DISPONÍVEL
# ============================================================
def get_driver():
    """Retorna o primeiro driver da lista que estiver instalado."""
    available = pyodbc.drivers()
    for candidate in DRIVER_CANDIDATES:
        if candidate in available:
            return candidate
    print("❌ Nenhum driver ODBC compatível encontrado.")
    print("Drivers instalados no sistema:")
    for d in available:
        print(f"  - {d}")
    raise RuntimeError("Driver ODBC não encontrado. Instale um dos drivers listados acima.")


# ============================================================
# LÓGICA DE TRANSFORMAÇÃO (MESMA DA QUERY SQL)
# ============================================================
def processar_formula(original: str) -> str:
    """
    Converte a fórmula original no formato:
        (1)MAT, (1)FIS, (2)QUI
    para:
        (MAT E FIS) OU QUI
    """
    if not original or original.strip() == '':
        return ''

    # Remove quebras de linha e espaços
    limpo = original.replace('\r', '').replace('\n', '').replace(' ', '')

    # Divide por vírgula
    tokens = [t for t in limpo.split(',') if t != '']

    # Extrai (tipo, disciplina)
    itens = []
    for token in tokens:
        if ')' not in token:
            continue
        try:
            tipo_str = token[1:token.index(')')]  # entre '(' e ')'
            tipo = int(tipo_str)
            disciplina = token[token.index(')') + 1:].strip()
            if disciplina:
                itens.append((tipo, disciplina))
        except (ValueError, IndexError):
            # Token malformado, ignora
            continue

    if not itens:
        return ''

    # Agrupa por mudança de tipo
    grupos = []
    grupo_atual = [itens[0][1]]
    tipo_atual = itens[0][0]

    for tipo, disc in itens[1:]:
        if tipo == tipo_atual:
            grupo_atual.append(disc)
        else:
            grupos.append(grupo_atual)
            grupo_atual = [disc]
            tipo_atual = tipo
    if grupo_atual:
        grupos.append(grupo_atual)

    # Monta a expressão final
    partes_grupo = []
    for grupo in grupos:
        if len(grupo) == 1:
            partes_grupo.append(grupo[0])
        else:
            partes_grupo.append('(' + ' E '.join(grupo) + ')')

    return ' OU '.join(partes_grupo)


# ============================================================
# FUNÇÃO PARA ATUALIZAR UM LOTE
# ============================================================
def atualizar_lote(cursor, lotes: List[Tuple]):
    """Executa um UPDATE para cada linha do lote."""
    sql = """
        UPDATE [academico].[dbo].[MD_TBL_CURSO_MATRIZ_24072026]
        SET FORMULA_EQUIV_GA = ?
        WHERE CURSO = ?
          AND CURRICULO = ?
          AND SERIE = ?
          AND DISCIPLINA = ?
          AND TURNO = ?
          AND FORMULA_EQUIV_GA = ?
    """
    for curso, curriculo, serie, disciplina, turno, original, novo_valor in lotes:
        cursor.execute(sql, (novo_valor, curso, curriculo, serie, disciplina, turno, original))


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================
def main():
    print("🔍 Detectando driver ODBC...")
    driver = get_driver()
    print(f"✅ Usando driver: {driver}")

    # String de conexão com autenticação Windows
    # O nome do driver pode ser usado sem chaves (o pyodbc aceita)
    conn_str = (
        f'DRIVER={driver};'
        f'SERVER={SERVER};'
        f'DATABASE={DATABASE};'
        f'Trusted_Connection=yes;'
    )

    print(f"🔗 Conectando ao servidor '{SERVER}'...")
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # Buscar todas as linhas com fórmula não vazia
    print("📊 Buscando registros com FORMULA_EQUIV_GA <> '' ...")
    select_sql = """
        SELECT CURSO, CURRICULO, SERIE, DISCIPLINA, TURNO, FORMULA_EQUIV_GA
        FROM [academico].[dbo].[MD_TBL_CURSO_MATRIZ_24072026]
        WHERE FORMULA_EQUIV_GA <> ''
    """
    rows = cursor.execute(select_sql).fetchall()
    total = len(rows)
    print(f"📝 Total de linhas a processar: {total}")

    if total == 0:
        print("ℹ️ Nenhuma linha para processar. Encerrando.")
        cursor.close()
        conn.close()
        return

    # Processar cada linha
    print("⚙️ Processando fórmulas...")
    updates = []
    for idx, row in enumerate(rows, start=1):
        curso, curriculo, serie, disciplina, turno, original = row
        novo_valor = processar_formula(original)
        updates.append((curso, curriculo, serie, disciplina, turno, original, novo_valor))

        if idx % 1000 == 0:
            print(f"   Processados {idx}/{total}")

    print(f"✅ {len(updates)} linhas prontas para atualização.")

    # Atualizar em lotes
    print(f"🔄 Atualizando em lotes de {BATCH_SIZE}...")
    total_updates = len(updates)
    for i in range(0, total_updates, BATCH_SIZE):
        lote = updates[i:i + BATCH_SIZE]
        try:
            conn.autocommit = False
            atualizar_lote(cursor, lote)
            conn.commit()
            print(f"   ✅ Lote {i//BATCH_SIZE + 1} atualizado ({len(lote)} linhas).")
        except Exception as e:
            conn.rollback()
            print(f"   ❌ Erro no lote {i//BATCH_SIZE + 1}: {e}")
            print("   ⚠️ Transação desfeita para este lote. Interrompendo.")
            break
        finally:
            conn.autocommit = True

    print("🎉 Processamento concluído!")
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()