
"""
Investiga duplicidades, versões e exercícios nos CSVs DFP da CVM.

Execute na raiz do projeto:
.venv/Scripts/python.exe src/04_investigar_duplicidades.py

O script não exclui nem altera registros originais.
"""

from pathlib import Path
import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]
PASTA_ENTRADA = RAIZ / "data" / "raw" / "csv"
PASTA_SAIDA = RAIZ / "data" / "processed" / "diagnostico"

COLUNAS_EXIBICAO = [
    "CNPJ_CIA", "DENOM_CIA", "CD_CVM", "DT_REFER", "VERSAO",
    "GRUPO_DFP", "ORDEM_EXERC", "DT_FIM_EXERC", "CD_CONTA",
    "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


def main():
    arquivos = sorted(PASTA_ENTRADA.glob("*.csv"))

    if not arquivos:
        print("Nenhum CSV encontrado na pasta de entrada.")
        return

    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    resumos = []
    amostras_exatas = []
    grupos_chave = []
    documentos_multiversao = []
    distribuicao_exercicio = []

    print("INVESTIGAÇÃO DE DUPLICIDADES E VERSÕES — CVM/DFP")
    print("Nenhum arquivo original será alterado.")
    print("Nenhuma linha será excluída.")

    for caminho in arquivos:

        df = pd.read_csv(
            caminho,
            sep=";",
            encoding="cp1252",
            dtype="string",
            keep_default_na=True,
            low_memory=False,
        )

        # 1. Identifica duplicidades exatamente iguais.
        mascara_exata = df.duplicated(keep=False)
        linhas_exatas = df.loc[mascara_exata]
        quantidade_exata = int(df.duplicated().sum())

        colunas_amostra = [
            coluna for coluna in COLUNAS_EXIBICAO
            if coluna in df.columns
        ]

        if not linhas_exatas.empty:
            amostra = (
                linhas_exatas[colunas_amostra]
                .drop_duplicates()
                .head(12)
                .copy()
            )
            amostra.insert(0, "arquivo", caminho.name)
            amostras_exatas.extend(amostra.to_dict("records"))

        # 2. Investiga contas repetidas pela chave candidata.
        chave = [
    coluna for coluna in [
        "CNPJ_CIA",
        "CD_CVM",
        "DT_REFER",
        "GRUPO_DFP",
        "ORDEM_EXERC",
        "DT_FIM_EXERC",
        "CD_CONTA",
        "DT_INI_EXERC",
    ]
    if coluna in df.columns
]

        mascara_chave = df.duplicated(
            subset=chave,
            keep=False,
        )

        repetidos_chave = df.loc[mascara_chave]

        if not repetidos_chave.empty:

            grupos = (
                repetidos_chave
                .groupby(chave, dropna=False)
                .agg(
                    quantidade_linhas=("VL_CONTA", "size"),
                    versoes_distintas=("VERSAO", "nunique"),
                    valores_distintos=("VL_CONTA", "nunique"),
                    descricoes_distintas=("DS_CONTA", "nunique"),
                )
                .reset_index()
            )

            grupos.insert(0, "arquivo", caminho.name)
            grupos_chave.extend(grupos.to_dict("records"))

            grupos_valores_diferentes = int(
                (grupos["valores_distintos"] > 1).sum()
            )

            grupos_versoes_diferentes = int(
                (grupos["versoes_distintas"] > 1).sum()
            )

        else:
            grupos_valores_diferentes = 0
            grupos_versoes_diferentes = 0

        # 3. Investiga versões no nível do documento.
        colunas_documento = [
    coluna for coluna in [
        "CNPJ_CIA",
        "CD_CVM",
        "DT_REFER",
        "DT_INI_EXERC",
        "DT_FIM_EXERC",
        "GRUPO_DFP",
    ]
    if coluna in df.columns
]

        documentos = df[
            colunas_documento + ["VERSAO"]
        ].drop_duplicates()

        versoes_documento = (
            documentos
            .groupby(colunas_documento, dropna=False)["VERSAO"]
            .agg(
                lambda serie: sorted(
                    serie.dropna().astype(str).unique().tolist()
                )
            )
            .reset_index(name="versoes_encontradas")
        )

        versoes_documento["quantidade_versoes"] = (
            versoes_documento["versoes_encontradas"].map(len)
        )

        multiplas = versoes_documento[
            versoes_documento["quantidade_versoes"] > 1
        ].copy()

        if not multiplas.empty:
            multiplas["versoes_encontradas"] = (
                multiplas["versoes_encontradas"].map(
                    lambda valores: ", ".join(valores)
                )
            )
            multiplas.insert(0, "arquivo", caminho.name)
            documentos_multiversao.extend(
                multiplas.to_dict("records")
            )

        # 4. Relaciona ORDEM_EXERC com a data de encerramento.
        if {"ORDEM_EXERC", "DT_FIM_EXERC"}.issubset(df.columns):

            ordem = (
                df.groupby(
                    ["ORDEM_EXERC", "DT_FIM_EXERC"],
                    dropna=False,
                )
                .size()
                .reset_index(name="quantidade_registros")
            )

            ordem.insert(0, "arquivo", caminho.name)
            distribuicao_exercicio.extend(
                ordem.to_dict("records")
            )

        distribuicao_versoes = (
            df["VERSAO"].value_counts(dropna=False).to_dict()
        )

        texto_versoes = "; ".join(
            f"{versao}: {quantidade}"
            for versao, quantidade in distribuicao_versoes.items()
        )

        resumo = {
            "arquivo": caminho.name,
            "linhas": len(df),
            "copias_exatas_adicionais": quantidade_exata,
            "linhas_envolvidas_duplicidade_exata": len(linhas_exatas),
            "linhas_repetidas_chave_candidata": int(mascara_chave.sum()),
            "grupos_chave_com_valores_diferentes": grupos_valores_diferentes,
            "grupos_chave_com_versoes_diferentes": grupos_versoes_diferentes,
            "documentos_com_multiplas_versoes": len(multiplas),
            "distribuicao_versoes": texto_versoes,
        }

        resumos.append(resumo)

        # 5. Exibe os principais resultados no terminal.
        print("\n" + "=" * 75)
        print(caminho.name)
        print(f"Cópias exatas adicionais: {quantidade_exata:,}")
        print(f"Linhas envolvidas em duplicidades exatas: {len(linhas_exatas):,}")
        print(f"Linhas repetidas pela chave candidata: {int(mascara_chave.sum()):,}")
        print(f"Grupos com valores diferentes: {grupos_valores_diferentes:,}")
        print(f"Grupos com versões diferentes: {grupos_versoes_diferentes:,}")
        print(f"Documentos com múltiplas versões: {len(multiplas):,}")
        print(f"Distribuição de VERSAO: {texto_versoes}")

        if not linhas_exatas.empty:
            print("\nAmostra de duplicidades exatas:")
            print(
                linhas_exatas[colunas_amostra]
                .head(4)
                .to_string(index=False)
            )

        if not repetidos_chave.empty:
            print("\nAmostra de contas repetidas pela chave:")
            print(
                repetidos_chave[colunas_amostra]
                .head(6)
                .to_string(index=False)
            )

    # 6. Salva os relatórios auxiliares.
    relatorios = {
        "04_resumo_investigacao.csv": pd.DataFrame(resumos),
        "04_amostras_duplicadas_exatas.csv": pd.DataFrame(amostras_exatas),
        "04_grupos_chave_repetida.csv": pd.DataFrame(grupos_chave),
        "04_documentos_multiplas_versoes.csv": pd.DataFrame(documentos_multiversao),
        "04_distribuicao_ordem_exercicio.csv": pd.DataFrame(distribuicao_exercicio),
    }

    for nome, tabela in relatorios.items():
        tabela.to_csv(
            PASTA_SAIDA / nome,
            index=False,
            encoding="utf-8-sig",
        )

    print("\n" + "=" * 75)
    print("Investigação concluída.")
    print("Relatórios gerados:")

    for nome in relatorios:
        print(" -", nome)

    print("Nenhum registro original foi excluído ou alterado.")


if __name__ == "__main__":
    main()
