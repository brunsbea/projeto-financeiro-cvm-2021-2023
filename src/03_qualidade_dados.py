
"""
Diagnostica a qualidade dos CSVs DFP consolidados da CVM.

Execute na raiz do projeto:
    .venv/Scripts/python.exe src/03_qualidade_dados.py

O script não altera os CSVs originais e não exclui registros.
Os relatórios são gravados em data/processed/diagnostico/.
"""

from pathlib import Path
import re

import pandas as pd


# Localiza as pastas a partir deste arquivo, sem caminhos absolutos do computador.
RAIZ_PROJETO = Path(__file__).resolve().parents[1]
PASTA_ENTRADA = RAIZ_PROJETO / "data" / "raw" / "csv"
PASTA_SAIDA = RAIZ_PROJETO / "data" / "processed" / "diagnostico"

CODIFICACAO = "cp1252"
SEPARADOR = ";"
COLUNAS_DATA = ["DT_REFER", "DT_INI_EXERC", "DT_FIM_EXERC"]

# Chave candidata para investigar registros repetidos.
# Não é uma regra de exclusão.
COLUNAS_CHAVE = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "GRUPO_DFP",
    "ORDEM_EXERC", "DT_FIM_EXERC", "CD_CONTA",
]


def identificar_arquivo(nome: str) -> tuple[str, str]:
    """Retorna o tipo de demonstração (BPA, BPP ou DRE) e o ano."""
    resultado = re.search(r"_(BPA|BPP|DRE)_con_(20\d{2})\.csv$", nome)

    if resultado:
        return resultado.group(1), resultado.group(2)

    return "NAO_IDENTIFICADO", "NAO_IDENTIFICADO"


def analisar_arquivo(caminho: Path, relatorios: dict) -> dict:
    """Lê um CSV, calcula indicadores de qualidade e alimenta os relatórios."""

    df = pd.read_csv(
        caminho,
        sep=SEPARADOR,
        encoding=CODIFICACAO,
        dtype="string",
        keep_default_na=True,
        low_memory=False,
    )

    demonstracao, ano = identificar_arquivo(caminho.name)
    linhas, colunas = df.shape

    # 1. Valores ausentes e campos preenchidos somente com espaços.
    for coluna in df.columns:
        serie = df[coluna].astype("string")
        ausentes = int(serie.isna().sum())

        somente_espacos = int(
            (serie.notna() & serie.str.strip().eq("")).sum()
        )

        relatorios["ausentes"].append({
            "arquivo": caminho.name,
            "demonstracao": demonstracao,
            "ano": ano,
            "coluna": coluna,
            "valores_ausentes": ausentes,
            "percentual_ausente": round(
                ausentes / linhas * 100, 4
            ) if linhas else 0,
            "valores_com_somente_espacos": somente_espacos,
        })

    # 2. Duplicidades exatas e repetições de uma chave candidata.
    duplicadas_exatas = int(df.duplicated().sum())

    chave = [c for c in COLUNAS_CHAVE if c in df.columns]

    if "DT_INI_EXERC" in df.columns:
        chave.append("DT_INI_EXERC")

    duplicadas_chave = (
        int(df.duplicated(subset=chave, keep=False).sum())
        if chave else 0
    )

    # 3. Datas preenchidas que não puderam ser interpretadas.
    datas_invalidas = {}

    for coluna in COLUNAS_DATA:
        if coluna in df.columns:
            original = df[coluna].astype("string").str.strip()
            preenchidas = original.notna() & original.ne("")

            convertidas = pd.to_datetime(
                original,
                format="%Y-%m-%d",
                errors="coerce",
            )

            datas_invalidas[coluna] = int(
                (preenchidas & convertidas.isna()).sum()
            )

    # 4. Conversão numérica exploratória da coluna VL_CONTA.
    # A coluna original não é modificada.
    valores_invalidos = 0
    negativos = 0
    zeros = 0
    amostra_valores = []

    if "VL_CONTA" in df.columns:
        valores_originais = df["VL_CONTA"].astype("string").str.strip()
        preenchidos = valores_originais.notna() & valores_originais.ne("")

        valores_numericos = pd.to_numeric(
            valores_originais,
            errors="coerce",
        )

        valores_invalidos = int(
            (preenchidos & valores_numericos.isna()).sum()
        )

        negativos = int((valores_numericos < 0).sum())
        zeros = int((valores_numericos == 0).sum())

        amostra_valores = valores_originais.dropna().head(5).tolist()

    # 5. Distribuição das versões e identificação de períodos com várias versões.
    if "VERSAO" in df.columns:

        for versao, quantidade in df["VERSAO"].value_counts(
            dropna=False
        ).items():

            relatorios["versoes"].append({
                "arquivo": caminho.name,
                "demonstracao": demonstracao,
                "ano": ano,
                "versao": "(ausente)" if pd.isna(versao) else str(versao),
                "quantidade_registros": int(quantidade),
            })

        colunas_periodo = [
            c for c in [
                "CNPJ_CIA",
                "CD_CVM",
                "DT_REFER",
                "GRUPO_DFP",
                "ORDEM_EXERC",
                "DT_INI_EXERC",
                "DT_FIM_EXERC",
            ] if c in df.columns
        ]

        if colunas_periodo:

            pares = df[
                colunas_periodo + ["VERSAO"]
            ].drop_duplicates()

            por_periodo = (
                pares.groupby(
                    colunas_periodo,
                    dropna=False,
                )["VERSAO"]
                .agg(
                    lambda serie: sorted(
                        serie.dropna().unique().tolist()
                    )
                )
                .reset_index(name="versoes_encontradas")
            )

            por_periodo["quantidade_versoes"] = (
                por_periodo["versoes_encontradas"].str.len()
            )

            por_periodo = por_periodo[
                por_periodo["quantidade_versoes"] > 1
            ]

            for registro in por_periodo.to_dict(orient="records"):

                registro["versoes_encontradas"] = ", ".join(
                    registro["versoes_encontradas"]
                )

                relatorios["multiplas_versoes"].append({
                    "arquivo": caminho.name,
                    "demonstracao": demonstracao,
                    "ano": ano,
                    **registro,
                })

    # 6. Catálogo de contas contábeis encontradas.
    if {"CD_CONTA", "DS_CONTA"}.issubset(df.columns):

        contas = df[
            ["CD_CONTA", "DS_CONTA"]
        ].drop_duplicates()

        for codigo, descricao in contas.itertuples(
            index=False,
            name=None,
        ):

            relatorios["contas"].append({
                "arquivo": caminho.name,
                "demonstracao": demonstracao,
                "ano": ano,
                "codigo_conta": codigo,
                "descricao_conta": descricao,
            })

    # 7. Catálogo de companhias e quantidade de registros por companhia.
    colunas_empresa = [
        c for c in ["CNPJ_CIA", "CD_CVM", "DENOM_CIA"]
        if c in df.columns
    ]

    if colunas_empresa:
        empresas = (
            df.groupby(
                colunas_empresa,
                dropna=False,
            )
            .size()
            .reset_index(name="quantidade_registros")
        )
    else:
        empresas = pd.DataFrame()

    for registro in empresas.to_dict(orient="records"):
        relatorios["companhias"].append({
            "arquivo": caminho.name,
            "demonstracao": demonstracao,
            "ano": ano,
            **registro,
        })

    # 8. Resumo geral do arquivo.
    resumo = {
        "arquivo": caminho.name,
        "demonstracao": demonstracao,
        "ano": ano,
        "linhas": int(linhas),
        "colunas": int(colunas),
        "celulas_ausentes": int(df.isna().sum().sum()),
        "linhas_duplicadas_exatas": duplicadas_exatas,
        "linhas_repetidas_chave_candidata": duplicadas_chave,
        "chave_candidata_utilizada": ", ".join(chave),
        "companhias_identificadas": (
            int(df["CD_CVM"].nunique())
            if "CD_CVM" in df.columns else 0
        ),
        "contas_identificadas": (
            int(df["CD_CONTA"].nunique())
            if "CD_CONTA" in df.columns else 0
        ),
        "VL_CONTA_nao_numericos": valores_invalidos,
        "VL_CONTA_negativos": negativos,
        "VL_CONTA_iguais_zero": zeros,
        **{
            f"datas_invalidas_{c}": n
            for c, n in datas_invalidas.items()
        },
    }

    # 9. Resultado resumido no terminal.
    print("\n" + "=" * 75)
    print(f"{caminho.name} — {linhas:,} linhas x {colunas} colunas")
    print(f"Células ausentes: {resumo['celulas_ausentes']:,}")
    print(f"Duplicadas exatas: {duplicadas_exatas:,}")
    print(f"Linhas repetidas pela chave candidata: {duplicadas_chave:,}")
    print(f"Companhias (CD_CVM): {resumo['companhias_identificadas']:,}")
    print(f"Contas (CD_CONTA): {resumo['contas_identificadas']:,}")
    print(f"VL_CONTA não numéricos: {valores_invalidos:,}")

    colunas_com_ausentes = [
        item["coluna"]
        for item in relatorios["ausentes"]
        if (
            item["arquivo"] == caminho.name
            and item["valores_ausentes"] > 0
        )
    ]

    print(
        "Colunas com valores ausentes:",
        colunas_com_ausentes or "nenhuma",
    )

    for coluna in [
        "VERSAO",
        "ORDEM_EXERC",
        "ESCALA_MOEDA",
        "MOEDA",
    ]:

        if coluna in df.columns:
            print(f"\nDistribuição de {coluna}:")
            print(
                df[coluna].value_counts(dropna=False).to_string()
            )

    if amostra_valores:
        print("\nAmostra de VL_CONTA como veio da CVM:")
        print(amostra_valores)

    return resumo


def main() -> int:
    """Executa a análise dos CSVs e salva seis relatórios."""

    if not PASTA_ENTRADA.exists():
        print(f"ERRO: pasta não encontrada: {PASTA_ENTRADA}")
        print("Execute primeiro src/01_extrair_cvm.py.")
        return 1

    arquivos = sorted(PASTA_ENTRADA.glob("*.csv"))

    if not arquivos:
        print(f"ERRO: nenhum CSV encontrado em: {PASTA_ENTRADA}")
        return 1

    relatorios = {
        "ausentes": [],
        "versoes": [],
        "multiplas_versoes": [],
        "contas": [],
        "companhias": [],
    }

    resumos = []

    print("DIAGNÓSTICO DE QUALIDADE — DFP/CVM")
    print(f"Pasta analisada: {PASTA_ENTRADA}")
    print(f"Arquivos encontrados: {len(arquivos)}")
    print(
        f"Leitura: {CODIFICACAO}, separador '{SEPARADOR}', "
        "colunas como texto"
    )
    print(
        "Os arquivos originais não serão alterados; "
        "nenhuma linha será excluída."
    )

    for arquivo in arquivos:
        try:
            resumos.append(
                analisar_arquivo(arquivo, relatorios)
            )

        except (
            UnicodeDecodeError,
            pd.errors.ParserError,
            OSError,
            ValueError,
        ) as erro:

            print(f"\nERRO ao analisar {arquivo.name}: {erro}")

    if not resumos:
        print("Nenhum arquivo foi analisado com sucesso.")
        return 1

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    tabelas = {
        "resumo_qualidade_arquivos.csv": pd.DataFrame(resumos),

        "valores_ausentes_por_coluna.csv": pd.DataFrame(
            relatorios["ausentes"]
        ),

        "distribuicao_versoes.csv": pd.DataFrame(
            relatorios["versoes"]
        ),

        "companhias_com_multiplas_versoes.csv": pd.DataFrame(
            relatorios["multiplas_versoes"]
        ),

        "catalogo_contas.csv": pd.DataFrame(
            relatorios["contas"]
        ).drop_duplicates(),

        "catalogo_companhias.csv": pd.DataFrame(
            relatorios["companhias"]
        ).drop_duplicates(),
    }

    for nome, tabela in tabelas.items():
        tabela.to_csv(
            PASTA_SAIDA / nome,
            index=False,
            encoding="utf-8-sig",
        )

    print("\n" + "=" * 75)
    print(
        f"Diagnóstico concluído: {len(resumos)} arquivo(s) analisado(s)."
    )

    print(
        "Relatórios gravados em:",
        PASTA_SAIDA.relative_to(RAIZ_PROJETO),
    )

    print("Arquivos gerados:")

    for nome in tabelas:
        print(" -", nome)

    print(
        "Nenhum CSV original foi modificado e nenhuma linha foi excluída."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
