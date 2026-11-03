
from pathlib import Path
import unicodedata
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PASTA = ROOT / "data" / "processed" / "base_selecionada"

ARQUIVOS = {
    "BPA": "dfp_bpa_selecionadas_2021_2023.csv",
    "BPP": "dfp_bpp_selecionadas_2021_2023.csv",
    "DRE": "dfp_dre_selecionadas_2021_2023.csv",
}

PALAVRAS = {
    "BPA": [
        "ativo circulante",
        "caixa",
        "equivalentes",
        "aplicacoes financeiras",
        "disponibilidades",
    ],
    "BPP": [
        "passivo circulante",
        "passivo nao circulante",
        "patrimonio liquido",
        "emprestimos",
        "financiamentos",
        "debentures",
        "arrendamento",
    ],
    "DRE": [
        "receita",
        "custo",
        "resultado bruto",
        "resultado antes do resultado financeiro",
        "lucro",
        "prejuizo",
    ],
}


def normalizar(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize("NFKD", texto)

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def main():
    for tipo, nome_arquivo in ARQUIVOS.items():
        caminho = PASTA / nome_arquivo

        if not caminho.exists():
            raise FileNotFoundError(
                f"Arquivo não encontrado: {caminho}"
            )

        df = pd.read_csv(
            caminho,
            sep=";",
            encoding="utf-8-sig",
            dtype=str,
        )

        df["DESCRICAO_NORMALIZADA"] = (
            df["DS_CONTA"].map(normalizar)
        )

        padrao = "|".join(PALAVRAS[tipo])

        filtrado = df[
            df["DESCRICAO_NORMALIZADA"].str.contains(
                padrao,
                regex=True,
                na=False,
            )
        ]

        contas = (
            filtrado.groupby(
                ["CD_CONTA", "DS_CONTA"],
                as_index=False,
            )
            .agg(
                EMPRESAS=("TICKER", "nunique"),
                REGISTROS=("TICKER", "size"),
            )
            .sort_values("CD_CONTA")
        )

        print("\n" + "=" * 90)
        print(f"CONTAS IDENTIFICADAS — {tipo}")
        print("=" * 90)

        if contas.empty:
            print("Nenhuma conta encontrada.")
        else:
            print(contas.to_string(index=False))

    print("\nInspeção das contas concluída.")


if __name__ == "__main__":
    main()
