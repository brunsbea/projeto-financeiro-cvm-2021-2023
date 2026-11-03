
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PASTA_RAW = ROOT / "data" / "raw" / "csv"
PASTA_PROCESSADA = ROOT / "data" / "processed"
PASTA_SAIDA = PASTA_PROCESSADA / "base_selecionada"

ANOS = [2021, 2022, 2023]
TIPOS = ["BPA", "BPP", "DRE"]

# Converte os valores da CVM para reais.
FATORES_ESCALA = {
    "MIL": 1000,
    "UNIDADE": 1,
}


def carregar_mapa_empresas():
    caminho = PASTA_PROCESSADA / "empresas_selecionadas.csv"

    if not caminho.exists():
        raise FileNotFoundError(
            "Execute primeiro o script 06 de mapeamento das empresas."
        )

    mapa = pd.read_csv(
        caminho,
        sep=";",
        encoding="utf-8-sig",
        dtype=str,
    )

    mapa["CD_CVM"] = mapa["CD_CVM"].str.strip().str.zfill(6)

    if mapa["CD_CVM"].duplicated().any():
        raise ValueError("Há códigos CVM repetidos no mapa de empresas.")

    if len(mapa) != 12:
        raise ValueError(
            f"Esperadas 12 empresas, mas foram encontradas {len(mapa)}."
        )

    return mapa


def processar_arquivo(tipo, ano, mapa):
    nome = f"dfp_cia_aberta_{tipo}_con_{ano}.csv"
    caminho = PASTA_RAW / nome

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {nome}")

    df = pd.read_csv(
        caminho,
        sep=";",
        encoding="cp1252",
        dtype=str,
    )

    colunas_obrigatorias = [
        "CD_CVM",
        "DT_REFER",
        "VERSAO",
        "GRUPO_DFP",
        "ORDEM_EXERC",
        "DT_FIM_EXERC",
        "CD_CONTA",
        "VL_CONTA",
        "ESCALA_MOEDA",
        "MOEDA",
    ]

    if tipo == "DRE":
        colunas_obrigatorias.append("DT_INI_EXERC")

    faltantes = [
        coluna
        for coluna in colunas_obrigatorias
        if coluna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"{nome}: colunas ausentes: {faltantes}"
        )

    df["CD_CVM"] = df["CD_CVM"].str.strip().str.zfill(6)
    df["ORDEM_EXERC"] = df["ORDEM_EXERC"].str.strip().str.upper()

    # Mantém somente as 12 empresas e o exercício principal do arquivo.
    df = df[
        df["CD_CVM"].isin(mapa["CD_CVM"])
        & (df["ORDEM_EXERC"] == "ÚLTIMO")
    ].copy()

    # Identifica o ano pelo encerramento efetivo do exercício.
    df["ANO"] = pd.to_datetime(
        df["DT_FIM_EXERC"],
        errors="coerce",
    ).dt.year

    if df["ANO"].isna().any():
        raise ValueError(
            f"{nome}: existem datas de encerramento inválidas."
        )

    # Padroniza o valor numérico e a escala monetária.
    df["VL_CONTA_NUM"] = pd.to_numeric(
        df["VL_CONTA"],
        errors="coerce",
    )

    if df["VL_CONTA_NUM"].isna().any():
        raise ValueError(
            f"{nome}: existem valores de conta não numéricos."
        )

    df["ESCALA_MOEDA"] = df["ESCALA_MOEDA"].str.strip().str.upper()
    df["MOEDA"] = df["MOEDA"].str.strip().str.upper()

    if not df["MOEDA"].eq("REAL").all():
        raise ValueError(
            f"{nome}: há registros em moeda diferente de REAL."
        )

    df["FATOR_ESCALA"] = df["ESCALA_MOEDA"].map(FATORES_ESCALA)

    if df["FATOR_ESCALA"].isna().any():
        escalas = df.loc[
            df["FATOR_ESCALA"].isna(),
            "ESCALA_MOEDA",
        ].unique()

        raise ValueError(
            f"{nome}: escala monetária não reconhecida: {escalas}"
        )

    df["VALOR_REAIS"] = (
        df["VL_CONTA_NUM"] * df["FATOR_ESCALA"]
    )

    # Acrescenta o ticker correspondente ao código CVM.
    df = df.merge(
        mapa[["TICKER", "CD_CVM"]],
        on="CD_CVM",
        how="left",
        validate="many_to_one",
    )

    df["ARQUIVO_ORIGEM"] = nome

    # Remove somente cópias integralmente idênticas.
    duplicadas_exatas = int(df.duplicated().sum())
    df = df.drop_duplicates().copy()

    return df, duplicadas_exatas


def identificar_conflitos(df, tipo):
    chave = [
        "TICKER",
        "CD_CVM",
        "DT_REFER",
        "DT_FIM_EXERC",
        "GRUPO_DFP",
        "CD_CONTA",
    ]

    if "DT_INI_EXERC" in df.columns:
        chave.append("DT_INI_EXERC")

    quantidade_valores = (
        df.groupby(chave, dropna=False)["VALOR_REAIS"]
        .nunique()
        .reset_index(name="QTD_VALORES")
    )

    chaves_conflitantes = quantidade_valores[
        quantidade_valores["QTD_VALORES"] > 1
    ][chave]

    if chaves_conflitantes.empty:
        return pd.DataFrame()

    conflitos = df.merge(
        chaves_conflitantes,
        on=chave,
        how="inner",
    )

    conflitos.insert(0, "TIPO_DEMONSTRACAO", tipo)

    return conflitos


def main():
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    mapa = carregar_mapa_empresas()

    todos_conflitos = []

    print("PREPARAÇÃO DA BASE FINANCEIRA — CVM")
    print("=" * 75)
    print(f"Empresas selecionadas: {len(mapa)}")
    print(f"Período: {ANOS[0]} a {ANOS[-1]}")

    for tipo in TIPOS:
        partes = []
        total_duplicadas = 0

        print(f"\n{'=' * 75}")
        print(f"DEMONSTRAÇÃO: {tipo}")

        for ano in ANOS:
            df, duplicadas = processar_arquivo(tipo, ano, mapa)

            partes.append(df)
            total_duplicadas += duplicadas

            print(
                f"{ano}: {len(df):,} registros selecionados "
                f"| {duplicadas:,} cópias exatas removidas"
            )

        base = pd.concat(partes, ignore_index=True)

        conflitos = identificar_conflitos(base, tipo)

        if not conflitos.empty:
            todos_conflitos.append(conflitos)

        destino = (
            PASTA_SAIDA
            / f"dfp_{tipo.lower()}_selecionadas_2021_2023.csv"
        )

        base.to_csv(
            destino,
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )

        cobertura = (
            base[["TICKER", "ANO"]]
            .drop_duplicates()
            .pivot_table(
                index="TICKER",
                columns="ANO",
                aggfunc="size",
                fill_value=0,
            )
            .reindex(
                index=mapa["TICKER"],
                columns=ANOS,
                fill_value=0,
            )
        )

        print(f"\nTotal de registros após deduplicação exata: {len(base):,}")
        print(f"Duplicatas exatas removidas: {total_duplicadas:,}")
        print(f"Grupos com valores conflitantes: {len(conflitos.groupby(['TICKER', 'CD_CVM', 'DT_REFER', 'DT_FIM_EXERC', 'GRUPO_DFP', 'CD_CONTA'])) if not conflitos.empty else 0}")
        print("\nCobertura por empresa e ano:")
        print(cobertura.to_string())

        print(f"\nArquivo salvo: {destino.relative_to(ROOT)}")

    # Salva todos os conflitos encontrados na amostra.
    caminho_conflitos = PASTA_SAIDA / "conflitos_amostra.csv"

    if todos_conflitos:
        relatorio = pd.concat(todos_conflitos, ignore_index=True)
        relatorio.to_csv(
            caminho_conflitos,
            sep=";",
            index=False,
            encoding="utf-8-sig",
        )
        print(
            f"\nAtenção: conflitos encontrados. "
            f"Relatório salvo em {caminho_conflitos.relative_to(ROOT)}"
        )
    else:
        print("\nNenhum conflito de valores encontrado nas 12 empresas.")
        print("Não foi necessário gerar relatório de conflitos.")

    print("\nPreparação concluída.")
    print("Os CSVs originais da CVM não foram modificados.")


if __name__ == "__main__":
    main()
