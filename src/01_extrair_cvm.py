"""Extrai apenas BPA, BPP e DRE consolidados das bases anuais da CVM.

Uso: executar este arquivo a partir da raiz do projeto, por exemplo:
    .venv/Scripts/python.exe src/01_extrair_cvm.py

Os ZIPs originais permanecem intactos. Os CSVs selecionados são gravados em
 data/raw/csv/.
"""

from pathlib import Path
from shutil import copyfileobj
from zipfile import BadZipFile, ZipFile

ANOS = ("2021", "2022", "2023")
DEMONSTRACOES = ("BPA", "BPP", "DRE")

# A raiz do projeto é a pasta acima de src/.
RAIZ_PROJETO = Path(__file__).resolve().parent.parent
PASTA_DADOS_BRUTOS = RAIZ_PROJETO / "data" / "raw"
PASTA_SAIDA = PASTA_DADOS_BRUTOS / "csv"


def main() -> None:
    """Localiza os ZIPs e extrai os nove CSVs necessários."""
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)
    total_extraido = 0

    for ano in ANOS:
        caminho_zip = PASTA_DADOS_BRUTOS / f"dfp_cia_aberta_{ano}.zip"

        if not caminho_zip.is_file():
            print(f"AVISO: arquivo não encontrado: {caminho_zip}")
            continue

        try:
            with ZipFile(caminho_zip, "r") as arquivo_zip:
                nomes_no_zip = set(arquivo_zip.namelist())

                for demonstracao in DEMONSTRACOES:
                    nome_esperado = (
                        f"dfp_cia_aberta_{demonstracao}_con_{ano}.csv"
                    )

                    # O conjunto do ZIP usa nomes simples, sem subpastas.
                    if nome_esperado not in nomes_no_zip:
                        print(
                            f"AVISO: {nome_esperado} não foi encontrado "
                            f"em {caminho_zip.name}."
                        )
                        continue

                    destino = PASTA_SAIDA / nome_esperado
                    with arquivo_zip.open(nome_esperado, "r") as origem:
                        with destino.open("wb") as saida:
                            copyfileobj(origem, saida)

                    print(f"Extraído: {destino.relative_to(RAIZ_PROJETO)}")
                    total_extraido += 1

        except BadZipFile:
            print(f"ERRO: o arquivo ZIP está inválido: {caminho_zip}")

    print(f"\nConcluído: {total_extraido} de 9 arquivos extraídos.")
    if total_extraido != 9:
        print(
            "Confira os avisos acima antes de continuar. "
            "Os arquivos ZIP originais não foram modificados."
        )


if __name__ == "__main__":
    main()
