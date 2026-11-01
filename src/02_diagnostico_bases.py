"""Diagnostica a estrutura dos arquivos DFP consolidados da CVM.

Execute a partir de qualquer diretório com o Python do ambiente virtual:
    .venv/Scripts/python.exe src/02_diagnostico_bases.py

O script apenas lê os CSVs em data/raw/csv. Não altera os arquivos originais.
"""

from __future__ import annotations

import csv
from pathlib import Path


# A raiz do projeto é calculada a partir da localização deste script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = PROJECT_ROOT / "data" / "raw" / "csv"

# Tentamos primeiro as codificações mais comuns para arquivos CSV atuais.
ENCODINGS_TO_TRY = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
POSSIBLE_DELIMITERS = ";,\t|"
SAMPLE_BYTES = 100_000
SAMPLE_ROWS_TO_DISPLAY = 2


def detect_encoding(file_path: Path) -> str:
    """Retorna a primeira codificação que consegue decodificar a amostra."""
    with file_path.open("rb") as file:
        sample = file.read(SAMPLE_BYTES)

    for encoding in ENCODINGS_TO_TRY:
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    # latin-1 consegue decodificar qualquer sequência de bytes.
    return "latin-1"


def detect_delimiter(file_path: Path, encoding: str) -> str:
    """Detecta o separador usando uma amostra do arquivo."""
    with file_path.open("r", encoding=encoding, newline="") as file:
        sample = file.read(SAMPLE_BYTES)

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=POSSIBLE_DELIMITERS)
        return dialect.delimiter
    except csv.Error:
        # Os arquivos DFP da CVM normalmente utilizam ponto e vírgula.
        return ";"


def inspect_csv(file_path: Path) -> None:
    """Exibe metadados, cabeçalho, amostra e consistência das linhas."""
    encoding = detect_encoding(file_path)
    delimiter = detect_delimiter(file_path, encoding)

    total_rows = 0
    empty_rows = 0
    inconsistent_rows = 0
    sample_rows: list[list[str]] = []

    with file_path.open("r", encoding=encoding, newline="") as file:
        reader = csv.reader(file, delimiter=delimiter)

        try:
            header = next(reader)
        except StopIteration:
            print(f"\nArquivo vazio: {file_path.name}")
            return

        # Remove espaços laterais dos nomes das colunas para facilitar a leitura.
        header = [column.strip() for column in header]
        expected_columns = len(header)

        for row in reader:
            if not row:
                empty_rows += 1
                continue

            total_rows += 1

            if len(row) != expected_columns:
                inconsistent_rows += 1

            if len(sample_rows) < SAMPLE_ROWS_TO_DISPLAY:
                sample_rows.append(row)

    file_size_mb = file_path.stat().st_size / (1024 * 1024)

    print("\n" + "=" * 88)
    print(f"ARQUIVO: {file_path.name}")
    print(f"Tamanho: {file_size_mb:.2f} MB")
    print(f"Codificação detectada: {encoding}")
    print(f"Separador detectado: {delimiter!r}")
    print(f"Quantidade de colunas: {expected_columns}")
    print(f"Quantidade de registros (sem cabeçalho): {total_rows:,}")
    print(f"Linhas vazias: {empty_rows:,}")
    print(f"Linhas com quantidade de campos diferente do cabeçalho: {inconsistent_rows:,}")

    print("\nCOLUNAS:")
    for position, column in enumerate(header, start=1):
        print(f"  {position:02d}. {column}")

    print("\nAMOSTRA (até 2 registros; exibindo até 8 campos por registro):")
    for sample_number, row in enumerate(sample_rows, start=1):
        sample_dict = {
            header[index]: value
            for index, value in enumerate(row[:8])
            if index < len(header)
        }
        print(f"  Registro {sample_number}: {sample_dict}")


def main() -> None:
    """Localiza e diagnostica os nove CSVs esperados."""
    if not CSV_DIR.exists():
        raise FileNotFoundError(
            f"Pasta não encontrada: {CSV_DIR}\n"
            "Confirme se os arquivos foram extraídos em data/raw/csv."
        )

    csv_files = sorted(CSV_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"Nenhum arquivo CSV encontrado em: {CSV_DIR}"
        )

    print("DIAGNÓSTICO DAS BASES DFP — CVM")
    print(f"Pasta analisada: {CSV_DIR}")
    print(f"Arquivos CSV encontrados: {len(csv_files)}")

    for csv_file in csv_files:
        inspect_csv(csv_file)

    print("\n" + "=" * 88)
    print(f"Diagnóstico concluído: {len(csv_files)} arquivo(s) analisado(s).")
    print("Nenhum arquivo original foi alterado.")


if __name__ == "__main__":
    main()
