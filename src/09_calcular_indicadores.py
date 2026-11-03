
from pathlib import Path
import unicodedata

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PASTA = ROOT / "data" / "processed" / "base_selecionada"
PASTA_SAIDA = ROOT / "data" / "processed"

ANOS = [2021, 2022, 2023]
TICKER_FINANCEIRO = "ITUB4"

SETORES = {
    "WEG3": "Bens industriais",
    "EMBR3": "Aeroespacial",
    "VALE3": "Mineração",
    "GGBR4": "Siderurgia",
    "KLBN11": "Papel e celulose",
    "SUZB3": "Papel e celulose",
    "PETR4": "Petróleo e gás",
    "EGIE3": "Energia elétrica",
    "ITUB4": "Financeiro",
    "ABEV3": "Bebidas",
    "JBSS3": "Alimentos",
    "LREN3": "Varejo",
}


def normalizar(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def carregar_base(nome):
    caminho = PASTA / nome

    if not caminho.exists():
        raise FileNotFoundError(f"Base não encontrada: {caminho}")

    df = pd.read_csv(
        caminho,
        sep=";",
        encoding="utf-8-sig",
        dtype={"CD_CONTA": str, "TICKER": str},
    )

    df["CD_CONTA"] = df["CD_CONTA"].str.strip()
    df["TICKER"] = df["TICKER"].str.strip()
    df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce")
    df["VALOR_REAIS"] = pd.to_numeric(
        df["VALOR_REAIS"],
        errors="coerce",
    )

    if df["ANO"].isna().any() or df["VALOR_REAIS"].isna().any():
        raise ValueError(f"Há ano ou valor inválido em {nome}.")

    df["ANO"] = df["ANO"].astype(int)

    return df


def extrair_metrica(
    df,
    codigo,
    nome_coluna,
    descricao_contem=None,
    excluir_itau=False,
):
    """
    Extrai uma conta por empresa e ano.
    Usa somente a conta agregadora, evitando somar novamente
    seus subgrupos e provocar dupla contagem.
    """

    selecionado = df[
        df["CD_CONTA"].eq(codigo)
    ].copy()

    if descricao_contem:
        termo = normalizar(descricao_contem)

        selecionado = selecionado[
            selecionado["DS_CONTA"].map(normalizar).str.contains(
                termo,
                regex=False,
                na=False,
            )
        ]

    if excluir_itau:
        selecionado = selecionado[
            selecionado["TICKER"] != TICKER_FINANCEIRO
        ]

    chave = ["TICKER", "ANO"]

    duplicados = selecionado.duplicated(
        subset=chave,
        keep=False,
    )

    if duplicados.any():
        amostra = selecionado.loc[
            duplicados,
            ["TICKER", "ANO", "CD_CONTA", "DS_CONTA", "VALOR_REAIS"],
        ]

        raise ValueError(
            f"Mais de um registro encontrado para {nome_coluna}.\n"
            f"{amostra.to_string(index=False)}"
        )

    resultado = selecionado[
        ["TICKER", "ANO", "VALOR_REAIS"]
    ].rename(columns={"VALOR_REAIS": nome_coluna})

    return resultado


def extrair_patrimonio_liquido(bpp):
    """
    Nas bases selecionadas, o patrimônio líquido aparece
    nas contas agregadoras 2.03 ou 2.08.
    """

    selecionado = bpp[
        bpp["CD_CONTA"].isin(["2.03", "2.08"])
    ].copy()

    selecionado = selecionado[
        selecionado["DS_CONTA"].map(normalizar).str.contains(
            "patrimonio liquido",
            regex=False,
            na=False,
        )
    ]

    chave = ["TICKER", "ANO"]

    if selecionado.duplicated(subset=chave, keep=False).any():
        raise ValueError(
            "Foram encontrados vários registros de patrimônio líquido "
            "para a mesma empresa e ano. Verifique as contas."
        )

    resultado = selecionado[
        ["TICKER", "ANO", "CD_CONTA", "DS_CONTA", "VALOR_REAIS"]
    ].rename(columns={"VALOR_REAIS": "patrimonio_liquido"})

    print("\nContas utilizadas para patrimônio líquido:")
    print(
        resultado[["TICKER", "CD_CONTA", "DS_CONTA"]]
        .drop_duplicates()
        .sort_values("TICKER")
        .to_string(index=False)
    )

    return resultado[["TICKER", "ANO", "patrimonio_liquido"]]


def adicionar_metrica(base, df_origem, codigo, nome, **kwargs):
    metrica = extrair_metrica(
        df_origem,
        codigo,
        nome,
        **kwargs,
    )

    return base.merge(
        metrica,
        on=["TICKER", "ANO"],
        how="left",
        validate="one_to_one",
    )


def main():
    print("CÁLCULO DOS INDICADORES FINANCEIROS")
    print("=" * 80)

    mapa = pd.read_csv(
        PASTA_SAIDA / "empresas_selecionadas.csv",
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
    )

    tickers = mapa["TICKER"].tolist()

    bpa = carregar_base(
        "dfp_bpa_selecionadas_2021_2023.csv"
    )
    bpp = carregar_base(
        "dfp_bpp_selecionadas_2021_2023.csv"
    )
    dre = carregar_base(
        "dfp_dre_selecionadas_2021_2023.csv"
    )

    # Cria uma linha para cada empresa em cada exercício.
    indicadores = pd.MultiIndex.from_product(
        [tickers, ANOS],
        names=["TICKER", "ANO"],
    ).to_frame(index=False)

    # --------------------------------------------------
    # DRE — Demonstração do Resultado
    # --------------------------------------------------

    indicadores = adicionar_metrica(
        indicadores, dre, "3.01", "receita_liquida"
    )

    indicadores = adicionar_metrica(
        indicadores,
        dre,
        "3.03",
        "lucro_bruto",
        descricao_contem="Resultado Bruto",
        excluir_itau=True,
    )

    indicadores = adicionar_metrica(
        indicadores,
        dre,
        "3.05",
        "ebit",
        descricao_contem=(
            "Resultado Antes do Resultado Financeiro e dos Tributos"
        ),
        excluir_itau=True,
    )

    indicadores = adicionar_metrica(
        indicadores, dre, "3.11", "lucro_liquido"
    )

    # O Itaú apresenta o lucro líquido na conta 3.09,
    # enquanto as demais empresas utilizam a conta 3.11.
    dre_itau = dre[
        dre["TICKER"] == "ITUB4"
    ].copy()

    lucro_itau = extrair_metrica(
        dre_itau,
        "3.09",
        "lucro_liquido_itau",
        descricao_contem="Lucro/Prejuízo Consolidado do Período",
    )

    indicadores = indicadores.merge(
        lucro_itau,
        on=["TICKER", "ANO"],
        how="left",
        validate="one_to_one",
    )

    indicadores["lucro_liquido"] = (
        indicadores["lucro_liquido"]
        .fillna(indicadores["lucro_liquido_itau"])
    )

    indicadores = indicadores.drop(
        columns=["lucro_liquido_itau"]
    )

    # --------------------------------------------------
    # BPA — Balanço Patrimonial Ativo
    # --------------------------------------------------

    indicadores = adicionar_metrica(
        indicadores,
        bpa,
        "1.01",
        "ativo_circulante",
        descricao_contem="Ativo Circulante",
        excluir_itau=True,
    )

    indicadores = adicionar_metrica(
        indicadores,
        bpa,
        "1.01.01",
        "caixa_equivalentes",
        descricao_contem="Caixa e Equivalentes de Caixa",
        excluir_itau=True,
    )

    # --------------------------------------------------
    # BPP — Balanço Patrimonial Passivo
    # --------------------------------------------------

    indicadores = adicionar_metrica(
        indicadores,
        bpp,
        "2.01",
        "passivo_circulante",
        descricao_contem="Passivo Circulante",
        excluir_itau=True,
    )

    indicadores = adicionar_metrica(
        indicadores,
        bpp,
        "2.01.04",
        "divida_curto_prazo",
        descricao_contem="Empréstimos e Financiamentos",
        excluir_itau=True,
    )

    indicadores = adicionar_metrica(
        indicadores,
        bpp,
        "2.02.01",
        "divida_longo_prazo",
        descricao_contem="Empréstimos e Financiamentos",
        excluir_itau=True,
    )

    patrimonio = extrair_patrimonio_liquido(bpp)

    indicadores = indicadores.merge(
        patrimonio,
        on=["TICKER", "ANO"],
        how="left",
        validate="one_to_one",
    )

    # --------------------------------------------------
    # Indicadores e fórmulas
    # --------------------------------------------------

    indicadores["SETOR_ANALISE"] = indicadores["TICKER"].map(
        SETORES
    )

    # Crescimento da receita em relação ao ano anterior.
    receita_anterior = (
        indicadores.sort_values(["TICKER", "ANO"])
        .groupby("TICKER")["receita_liquida"]
        .shift(1)
    )

    indicadores["crescimento_receita_pct"] = np.where(
        receita_anterior > 0,
        (
            indicadores["receita_liquida"]
            / receita_anterior
            - 1
        ) * 100,
        np.nan,
    )

    # Margens de rentabilidade.
    indicadores["margem_bruta_pct"] = (
        indicadores["lucro_bruto"]
        / indicadores["receita_liquida"]
    ) * 100

    indicadores["margem_ebit_pct"] = (
        indicadores["ebit"]
        / indicadores["receita_liquida"]
    ) * 100

    indicadores["margem_liquida_pct"] = (
        indicadores["lucro_liquido"]
        / indicadores["receita_liquida"]
    ) * 100

    # ROE: lucro líquido / patrimônio líquido médio.
    indicadores = indicadores.sort_values(
        ["TICKER", "ANO"]
    ).copy()

    patrimonio_anterior = (
        indicadores.groupby("TICKER")["patrimonio_liquido"]
        .shift(1)
    )

    indicadores["patrimonio_liquido_medio"] = (
        indicadores["patrimonio_liquido"]
        + patrimonio_anterior
    ) / 2

    # Para 2021, usa-se o patrimônio líquido final como aproximação.
    indicadores.loc[
        indicadores["ANO"] == 2021,
        "patrimonio_liquido_medio",
    ] = indicadores.loc[
        indicadores["ANO"] == 2021,
        "patrimonio_liquido",
    ]

    indicadores["roe_pct"] = np.where(
        indicadores["patrimonio_liquido_medio"] > 0,
        (
            indicadores["lucro_liquido"]
            / indicadores["patrimonio_liquido_medio"]
        ) * 100,
        np.nan,
    )

    # Liquidez corrente.
    indicadores["liquidez_corrente"] = np.where(
        indicadores["passivo_circulante"] != 0,
        (
            indicadores["ativo_circulante"]
            / indicadores["passivo_circulante"]
        ),
        np.nan,
    )

    # Endividamento: usa as contas agregadoras.
    indicadores["divida_bruta"] = indicadores[
        ["divida_curto_prazo", "divida_longo_prazo"]
    ].sum(axis=1, min_count=2)

    indicadores["divida_liquida"] = (
        indicadores["divida_bruta"]
        - indicadores["caixa_equivalentes"]
    )

    # Identifica a instituição financeira, cujos índices
    # não são diretamente comparáveis aos das demais empresas.
    indicadores["OBSERVACAO"] = np.where(
        indicadores["TICKER"] == TICKER_FINANCEIRO,
        (
            "Instituição financeira: estrutura contábil e indicadores "
            "operacionais/de liquidez não comparáveis às demais empresas."
        ),
        "",
    )

    # Verificações finais.
    if indicadores.duplicated(["TICKER", "ANO"]).any():
        raise ValueError(
            "A tabela final possui empresas/anos duplicados."
        )

    if len(indicadores) != len(tickers) * len(ANOS):
        raise ValueError(
            "A quantidade de linhas da tabela final está incorreta."
        )

    indicadores = indicadores.sort_values(
        ["ANO", "TICKER"]
    )

    colunas_percentuais = [
        "crescimento_receita_pct",
        "margem_bruta_pct",
        "margem_ebit_pct",
        "margem_liquida_pct",
        "roe_pct",
    ]

    indicadores[colunas_percentuais] = indicadores[
        colunas_percentuais
    ].replace([np.inf, -np.inf], np.nan)

    destino = PASTA_SAIDA / "indicadores_financeiros_2021_2023.csv"

    indicadores.to_csv(
        destino,
        sep=";",
        index=False,
        encoding="utf-8-sig",
        float_format="%.4f",
    )

    print("\nCOBERTURA DOS INDICADORES")
    print("=" * 80)

    colunas_verificar = [
        "receita_liquida",
        "lucro_liquido",
        "patrimonio_liquido",
        "roe_pct",
        "margem_bruta_pct",
        "margem_ebit_pct",
        "liquidez_corrente",
        "divida_liquida",
    ]

    for coluna in colunas_verificar:
        quantidade = indicadores[coluna].notna().sum()
        print(f"{coluna}: {quantidade} de {len(indicadores)} registros")

    print("\nAMOSTRA DOS INDICADORES")
    print("=" * 110)

    colunas_amostra = [
        "TICKER",
        "ANO",
        "receita_liquida",
        "lucro_liquido",
        "roe_pct",
        "margem_ebit_pct",
        "liquidez_corrente",
        "divida_liquida",
    ]

    print(
        indicadores[colunas_amostra]
        .round(2)
        .to_string(index=False)
    )

    print(f"\nArquivo gerado: {destino.relative_to(ROOT)}")
    print(f"Total de registros: {len(indicadores)}")
    print("Cálculo dos indicadores concluído.")


if __name__ == "__main__":
    main()
