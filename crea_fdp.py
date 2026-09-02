#!/usr/bin/env python3
"""
Procesa un archivo Excel (.xls/.xlsx) con columnas 'fdp_name' y 'Venta uds':
1. Elimina filas de pie de página (vacías, notas de "Filtros aplicados", fdp_name NaN).
2. Elimina la línea de totales.
3. Separa 'fdp_name' (ej: "502 MOVIL LIBRE") en:
     - fdp  -> parte numérica inicial (1 a 5 dígitos)
     - name -> el resto del texto
4. Deja solo las columnas 'fdp' y 'Venta uds'.
5. Elimina filas donde 'Venta uds' esté vacío,
   respetando filas con valores positivos, negativos o 0.
   Muestra por pantalla el detalle de las filas descartadas.

Uso:
    python procesar_xls.py archivo_entrada.xlsx -o resultado.csv
    python procesar_xls.py archivo_entrada.xls --sheet "Hoja1"
"""

import argparse
import re
import sys
import pandas as pd


def parse_args():
    parser = argparse.ArgumentParser(description="Procesa Excel de ventas por fdp.")
    parser.add_argument("archivo", help="Ruta al archivo Excel de entrada (.xls o .xlsx)")
    parser.add_argument("-o", "--output", default=None,
                         help="Ruta del archivo de salida (por defecto: <archivo>_procesado.csv)")
    parser.add_argument("--sheet", default=0,
                         help="Nombre o índice de la hoja a leer (por defecto la primera, índice 0)")
    parser.add_argument("--out-format", choices=["csv", "xlsx"], default="csv",
                         help="Formato del archivo de salida (por defecto csv)")
    parser.add_argument("--dump-descartadas", default=None,
                         help="Ruta opcional para guardar en CSV las filas descartadas "
                              "por 'Venta uds' vacío (ej: descartadas.csv)")
    return parser.parse_args()


def remove_footer_rows(df: pd.DataFrame, col: str = "fdp_name") -> pd.DataFrame:
    """
    Elimina filas de pie de página que no son datos reales:
    - Filas completamente vacías (todas las columnas NaN).
    - Filas donde fdp_name contiene notas tipo "Filtros aplicados".
    - Filas donde fdp_name es NaN (sin dato real, aunque otras columnas tengan algo).
    """
    df = df.copy()

    mask_vacia_total = df.isna().all(axis=1)
    mask_filtros = df[col].astype(str).str.contains(
        "filtros aplicados", case=False, na=False
    )
    mask_fdp_nan = df[col].isna()

    mask_footer = mask_vacia_total | mask_filtros | mask_fdp_nan
    n_removidas = mask_footer.sum()

    if n_removidas:
        print(f"[INFO] Se eliminaron {n_removidas} fila(s) de pie de página "
              f"(vacías / notas de filtros / fdp_name nulo):")
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(df.loc[mask_footer])

    return df.loc[~mask_footer].copy()


def remove_totals_row(df: pd.DataFrame, col: str = "fdp_name") -> pd.DataFrame:
    """Elimina filas cuya columna fdp_name contenga la palabra 'total'."""
    mask_total = df[col].astype(str).str.strip().str.lower().str.contains("total", na=False)
    n_removidas = mask_total.sum()
    if n_removidas:
        print(f"[INFO] Se eliminaron {n_removidas} fila(s) de totales.")
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(df.loc[mask_total])
    return df.loc[~mask_total].copy()


def split_fdp_name(df: pd.DataFrame, col: str = "fdp_name") -> pd.DataFrame:
    """
    Divide 'fdp_name' en 'fdp' (1 a 5 dígitos iniciales) y 'name' (resto).
    Ejemplo: '502 MOVIL LIBRE' -> fdp='502', name='MOVIL LIBRE'
    """
    extraido = df[col].astype(str).str.extract(r"^\s*(\d{1,5})\s+(.*)$")
    extraido.columns = ["fdp", "name"]

    n_sin_match = extraido["fdp"].isna().sum()
    if n_sin_match:
        print(f"[AVISO] {n_sin_match} fila(s) no coinciden con el patrón esperado "
              f"'NUMERO NOMBRE' y quedarán con fdp/name vacíos:")
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(df.loc[extraido["fdp"].isna(), [col]])

    df = df.copy()
    df["fdp"] = extraido["fdp"]
    df["name"] = extraido["name"]
    return df


def clean_venta_uds(df: pd.DataFrame, col: str = "Venta uds",
                     dump_path: str = None) -> pd.DataFrame:
    """
    Convierte 'Venta uds' a numérico y elimina filas donde quede vacío (NaN),
    conservando 0, positivos y negativos.
    Muestra por pantalla (y opcionalmente guarda en CSV) las filas descartadas
    con su valor ORIGINAL, antes de la conversión.
    """
    df = df.copy()

    # Guardamos el valor original tal cual venía en el Excel, antes de tocarlo
    valor_original = df[col].copy()

    def normaliza(v):
        if pd.isna(v):
            return v
        if isinstance(v, (int, float)):
            return v
        s = str(v).strip()
        if s == "":
            return None
        s = s.replace(".", "").replace(",", ".")  # miles '.' y decimal ','
        return s

    serie = df[col].apply(normaliza)
    serie_num = pd.to_numeric(serie, errors="coerce")
    df[col] = serie_num

    mask_vacio = df[col].isna()
    n_eliminadas = mask_vacio.sum()

    if n_eliminadas:
        print(f"[INFO] Se eliminaron {n_eliminadas} fila(s) con 'Venta uds' vacío.")
        print("[DETALLE] Filas descartadas (valores ORIGINALES antes de convertir):")

        # Reconstruimos un DataFrame de diagnóstico con fdp_name/fdp/name
        # (los que existan en ese momento) y el valor original de Venta uds
        columnas_diag = [c for c in ["fdp_name", "fdp", "name"] if c in df.columns]
        df_diag = df.loc[mask_vacio, columnas_diag].copy()
        df_diag["Venta uds (original)"] = valor_original.loc[mask_vacio]

        # Mostrar todas las filas sin truncar, aunque sean muchas
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(df_diag)

        if dump_path:
            df_diag.to_csv(dump_path, index=True, index_label="fila_original")
            print(f"[INFO] Detalle de filas descartadas guardado en: {dump_path}")
    else:
        print("[INFO] No se eliminó ninguna fila por 'Venta uds' vacío.")

    return df[~mask_vacio]


def main():
    args = parse_args()

    # Permite pasar el sheet como índice numérico si el usuario escribe "0", "1", etc.
    sheet = args.sheet
    if isinstance(sheet, str) and sheet.isdigit():
        sheet = int(sheet)

    try:
        df = pd.read_excel(args.archivo, sheet_name=sheet)
    except Exception as e:
        print(f"[ERROR] No se pudo leer el archivo '{args.archivo}': {e}", file=sys.stderr)
        sys.exit(1)

    columnas_requeridas = {"fdp_name", "Venta uds"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        print(f"[ERROR] Faltan columnas requeridas en el archivo: {faltantes}", file=sys.stderr)
        print(f"[INFO] Columnas encontradas: {list(df.columns)}", file=sys.stderr)
        sys.exit(1)

    n_original = len(df)
    print(f"[INFO] Filas leídas del Excel: {n_original}")

    # 1. Quitar filas de pie de página (vacías, notas de filtros, fdp_name NaN)
    df = remove_footer_rows(df, col="fdp_name")

    # 2. Quitar línea de totales
    df = remove_totals_row(df, col="fdp_name")

    # 3. Split de fdp_name -> fdp / name
    df = split_fdp_name(df, col="fdp_name")

    # 4. Limpiar Venta uds y quitar filas vacías (respetando 0, +, -)
    df = clean_venta_uds(df, col="Venta uds", dump_path=args.dump_descartadas)

    # 5. Dejar solo las columnas fdp y Venta uds
    df_final = df[["fdp", "Venta uds"]].copy()

    n_final = len(df_final)
    print(f"[RESUMEN] Filas originales: {n_original} | Filas finales: {n_final} "
          f"| Total descartadas: {n_original - n_final}")

    # Guardar resultado
    if args.output:
        salida = args.output
    else:
        base = re.sub(r"\.(xlsx|xls)$", "", args.archivo, flags=re.IGNORECASE)
        salida = f"{base}_procesado.{args.out_format}"

    if salida.lower().endswith(".xlsx") or args.out_format == "xlsx":
        if not salida.lower().endswith(".xlsx"):
            salida += ".xlsx"
        df_final.to_excel(salida, index=False)
    else:
        df_final.to_csv(salida, index=False)

    print(f"[OK] Archivo procesado guardado en: {salida}")
    print(df_final.head())


if __name__ == "__main__":
    main()
