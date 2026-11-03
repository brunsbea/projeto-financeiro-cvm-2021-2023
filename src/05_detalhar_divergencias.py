
"""
Detalha os registros com valores diferentes encontrados na investigação.

Lê os relatórios e os CSVs originais da CVM.
Não modifica nem exclui registros.
"""

from pathlib import Path
import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]

PASTA_RAW = RAIZ / "data" / "raw" / "csv"
PASTA_DIAGNOSTICO = RAIZ / "data" / "processed" / "diagnostico"

ARQUIVO_GRUPOS = (
    PASTA_DIAGNOSTICO / "04_grupos_chave_repetida.csv"
)

COLUNAS_CHAVE = [
    "CNPJ_CIA",
    "CD_CVM",
    "DT_REFER",
    "GRUPO_DFP",
    "ORDEM_EXERC",
    "DT_FIM_EXERC",
    "CD_CONTA",
]

COLUNAS_ANALISE = [
    "CNPJ_CIA",
    "DENOM_CIA",
    "CD_CVM",
    "DT_REFER",
    "VERSAO",
    "MOEDA",
    "ESCALA_MOEDA",
    "GRUPO_DFP",
    "ORDEM_EXERC",
    "DT_INI_EXERC",
    "DT_FIM_EXERC",
    "CD_CONTA",
    "DS_CONTA",
    "VL_CONTA",
    "ST_CONTA_FIXA",
]


def main():

    if not ARQUIVO_GRUPOS.exists():
        print("Relatório de grupos não encontrado.")
        return

    grupos = pd.read_csv(
        ARQUIVO_GRUPOS,
        encoding="utf-8-sig",
        dtype="string",
    )

    # Seleciona somente os grupos com valores financeiros diferentes.
    grupos = grupos[
        pd.to_numeric(
            grupos["valores_distintos"],
            errors="coerce",
        ) > 1
    ].copy()

    if grupos.empty:
        print("Nenhum grupo divergente encontrado.")
        return

    resultados = []

    print("DETALHAMENTO DOS REGISTROS DIVERGENTES")
    print(f"Grupos encontrados: {len(grupos)}")
    print("Nenhum dado original será modificado.")

    # Analisa um arquivo original por vez.
    for nome_arquivo, grupos_arquivo in grupos.groupby("arquivo"):

        caminho = PASTA_RAW / nome_arquivo

        df = pd.read_csv(
            caminho,
            sep=";",
            encoding="cp1252",
            dtype="string",
            low_memory=False,
        )

        chave = [
            coluna
            for coluna in COLUNAS_CHAVE
            if coluna in df.columns
            and coluna in grupos_arquivo.columns
        ]

        # Na DRE também precisamos considerar a data inicial do exercício.
        if (
            "DT_INI_EXERC" in df.columns
            and "DT_INI_EXERC" in grupos_arquivo.columns
        ):
            chave.append("DT_INI_EXERC")

        chaves_diferentes = (
            grupos_arquivo[chave]
            .drop_duplicates()
        )

        # Recupera todas as linhas originais correspondentes aos grupos.
        encontrados = df.merge(
            chaves_diferentes,
            on=chave,
            how="inner",
        )

        encontrados.insert(0, "ARQUIVO", nome_arquivo)

        colunas_disponiveis = [
            coluna
            for coluna in COLUNAS_ANALISE
            if coluna in encontrados.columns
        ]

        encontrados = encontrados[
            ["ARQUIVO"] + colunas_disponiveis
        ]

        resultados.append(encontrados)

        print(f"\n{nome_arquivo}")
        print(f"Grupos investigados: {len(grupos_arquivo)}")
        print(f"Registros recuperados: {len(encontrados)}")

        print(
            encontrados.to_string(
                index=False,
                max_rows=100,
            )
        )

    if resultados:

        resultado_final = pd.concat(
            resultados,
            ignore_index=True,
        )

        destino = (
            PASTA_DIAGNOSTICO
            / "05_detalhamento_valores_divergentes.csv"
        )

        resultado_final.to_csv(
            destino,
            index=False,
            encoding="utf-8-sig",
        )

        print("\n" + "=" * 70)
        print("Investigação concluída.")
        print(f"Registros detalhados: {len(resultado_final)}")
        print(f"Relatório salvo em: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
