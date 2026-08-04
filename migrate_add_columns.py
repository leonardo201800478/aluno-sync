from core.database import execute_query

columns_to_add = [
    "ddi_fone NVARCHAR(10)",
    "ddi_fone_celular NVARCHAR(10)",
    "ddi_fone_comercial NVARCHAR(10)",
    "dt_criacao NVARCHAR(30)",
    "loc_dif_residenc NVARCHAR(50)",
    "loc_zona_residenc NVARCHAR(50)",
    "povo_indigena NVARCHAR(100)",
    "resp_e_mail NVARCHAR(255)"
]

for col in columns_to_add:
    try:
        sql = f"ALTER TABLE LY_PESSOA ADD {col}"
        execute_query(sql, database_name='lyceum')
        print(f"Coluna {col} adicionada com sucesso.")
    except Exception as e:
        print(f"Erro ao adicionar {col}: {e}")