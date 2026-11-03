
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PASTA_DRE = ROOT / "data" / "raw" / "csv"
PASTA_PROCESSADA = ROOT / "data" / "processed"

# Ticker: código CVM da companhia correspondente
EMPRESAS = {
    "WEG3": "005410",
    "EMBR3": "020087",
    "VALE3": "004170",
    "GGBR4": "003980",
    "KLBN11": "012653",
    "SUZB3": "013986",
    "PETR4": "009512",
    "EGIE3": "017329",
    "ITUB4": "019348",
    "ABEV3": "023264",
    "JBSS3": "020575",
    "LREN3": "008133",
}


def carregar_empresas():
    arquivos = sorted(
        PASTA_DRE.glob("dfp_cia_aberta_DRE_con_*.csv")
    )

    if not arquivos:
        raise FileNotFoundError("Nenhum arquivo DRE foi encontrado.")

    partes = []

    for arquivo in arquivos:
        df = pd.read_csv(
            arquivo,
            sep=";",
            encoding="cp1252",
            dtype=str,
            usecols=["CD_CVM", "CNPJ_CIA", "DENOM_CIA"],
        )

        df["CD_CVM"] = df["CD_CVM"].str.strip().str.zfill(6)
        partes.append(df)

    return pd.concat(partes, ignore_index=True).drop_duplicates()


def main():
    cadastro = carregar_empresas()
    resultado = []

    for ticker, codigo_cvm in EMPRESAS.items():
        empresas = cadastro[
            cadastro["CD_CVM"] == codigo_cvm
        ][["CD_CVM", "CNPJ_CIA", "DENOM_CIA"]].drop_duplicates()

        if empresas.empty:
            raise ValueError(
                f"{ticker}: código CVM {codigo_cvm} não encontrado."
            )

        cnpjs = empresas["CNPJ_CIA"].unique()

        if len(cnpjs) > 1:
            raise ValueError(
                f"{ticker}: o código CVM {codigo_cvm} "
                "está associado a mais de um CNPJ."
            )

        # Usa a denominação mais recente encontrada no cadastro.
        empresa = empresas.iloc[-1]

        resultado.append({
            "TICKER": ticker,
            "CD_CVM": codigo_cvm,
            "CNPJ_CIA": empresa["CNPJ_CIA"],
            "DENOM_CIA": empresa["DENOM_CIA"],
        })

    mapa = pd.DataFrame(resultado)

    PASTA_PROCESSADA.mkdir(parents=True, exist_ok=True)

    destino = PASTA_PROCESSADA / "empresas_selecionadas.csv"

    mapa.to_csv(
        destino,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )

    print("\nEMPRESAS SELECIONADAS")
    print("=" * 80)
    print(mapa.to_string(index=False))
    print(f"\nTotal de empresas: {len(mapa)}")
    print(f"Arquivo salvo em: {destino.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
