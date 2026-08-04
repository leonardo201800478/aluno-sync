#!/usr/bin/env python3
"""
Gerador de relatório de contatos de alunos.
Uso:
    python reports/generators/gerar_relatorio_contatos_completo.py
"""

import sys
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from core.logger import logger
from reports.exporters.excel_exporter import ExcelExporter
from reports.exporters.pdf_exporter import PDFExporter
from reports.queries.relatorio_contatos_filtros import get_dados_contatos_filtros


def gerar_relatorio_contatos_completo(anos, semestres, unidade, curso,
                                      ano_ingresso=None, sem_ingresso=None,
                                      output_dir=None):
    """
    Gera relatório de contatos nos formatos HTML, Excel e PDF.
    """
    logger.info("Iniciando geração completa do relatório de contatos...")

    dados = get_dados_contatos_filtros(
        anos, semestres, unidade, curso,
        ano_ingresso=ano_ingresso,
        sem_ingresso=sem_ingresso
    )

    if dados.empty:
        logger.warning("Nenhum dado encontrado para os filtros.")
        return None, None, None

    # Define diretório de saída
    if output_dir is None:
        output_dir = Path.cwd() / "relatorios"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f"contatos_{timestamp}"

    # --- HTML ---
    html_path = output_dir / f"{base_filename}.html"
    gerar_html(dados, html_path, anos, semestres, unidade, curso,
               ano_ingresso, sem_ingresso)

    # --- Excel ---
    excel_path = output_dir / f"{base_filename}.xlsx"
    ExcelExporter().export(dados, excel_path)

    # --- PDF ---
    pdf_path = output_dir / f"{base_filename}.pdf"

    colunas_exibir = {
        'cod_aluno': 'Cód. Aluno',
        'nome_aluno': 'Nome',
        'nome_curso': 'Curso',
        'ddd_fone_celular': 'DDD Cel',
        'celular': 'Celular',
        'ddd_fone': 'DDD Res',
        'fone': 'Telefone',
        'e_mail': 'E-mail',
        'sit_matricula': 'Sit. Matr.',
        'sit_aluno': 'Sit. Aluno'
    }
    colunas_existentes = {k: v for k, v in colunas_exibir.items() if k in dados.columns}
    dados_pdf = dados[list(colunas_existentes.keys())].rename(columns=colunas_existentes)

    filtros_texto = (
        f"Filtros: Anos {anos} | Semestres {semestres} | Unidade {unidade} | "
        f"Curso: {curso if curso else 'Todos'} | "
        f"Ano Ingresso: {ano_ingresso if ano_ingresso else 'Todos'} | "
        f"Semestre Ingresso: {sem_ingresso if sem_ingresso else 'Todos'}"
    )

    PDFExporter(
        titulo="Relatório de Contatos de Alunos",
        subtitulo=filtros_texto,
        orientacao="paisagem",
        font_size=6
    ).export(dados_pdf, pdf_path, filtros_texto=filtros_texto)

    logger.info(f"Relatórios gerados: {html_path}, {excel_path}, {pdf_path}")
    return html_path, excel_path, pdf_path


def gerar_html(dados, output_path, anos, semestres, unidade, curso,
               ano_ingresso=None, sem_ingresso=None):
    """Gera arquivo HTML com os dados agrupados por curso."""
    html_content = []
    html_content.append(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Relatório de Contatos dos Alunos</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #2980b9; margin-top: 30px; }}
            table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>Relatório de Contatos dos Alunos</h1>
        <p>Filtros aplicados: 
            Anos: {anos} | 
            Semestres: {semestres} | 
            Unidade: {unidade} | 
            Curso: {curso if curso else 'Todos'} |
            Ano Ingresso: {ano_ingresso if ano_ingresso else 'Todos'} |
            Semestre Ingresso: {sem_ingresso if sem_ingresso else 'Todos'}
        </p>
    """)

    for nome_curso, grupo in dados.groupby('nome_curso'):
        html_content.append(f"<h2>Curso: {nome_curso}</h2>")
        html_content.append("""
        <table>
            <tr>
                <th>Cód. Aluno</th>
                <th>Nome</th>
                <th>DDD Celular</th>
                <th>Celular</th>
                <th>DDD Fone</th>
                <th>Fone</th>
                <th>E-mail</th>
                <th>Situação</th>
            </tr>
        """)
        for _, row in grupo.iterrows():
            html_content.append(f"""
            <tr>
                <td>{row['cod_aluno']}</td>
                <td>{row['nome_aluno']}</td>
                <td>{row['ddd_fone_celular']}</td>
                <td>{row['celular']}</td>
                <td>{row['ddd_fone']}</td>
                <td>{row['fone']}</td>
                <td>{row['e_mail']}</td>
                <td>{row['sit_aluno']}</td>
            </tr>
            """)
        html_content.append("</table>")

    html_content.append("</body></html>")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(html_content))


# =========================================================
# Bloco principal para execução direta (exemplo)
# =========================================================
if __name__ == "__main__":
    # Defina aqui os filtros desejados
    # Exemplo com dados fictícios – ajuste conforme sua necessidade
    FILTROS = {
        "anos": [2026, 2025],
        "semestres": [21, 22, 23, 24],
        "unidade": "002",               # código da unidade
        "curso": None,                  # None = todos os cursos
        "ano_ingresso": None,           # None = todos
        "sem_ingresso": None,           # None = todos
        "output_dir": Path.cwd() / "relatorios"
    }

    html, excel, pdf = gerar_relatorio_contatos_completo(**FILTROS)
    print(f"HTML: {html}")
    print(f"Excel: {excel}")
    print(f"PDF: {pdf}")