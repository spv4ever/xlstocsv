# main.py
import csv
import os

def transformar_csv(entrada, salida):
    with open(entrada, mode='r', encoding='utf-8') as infile, open(salida, mode='w', encoding='utf-8', newline='') as outfile:
        reader = csv.reader(infile, delimiter=',')
        writer = csv.writer(outfile, delimiter=';')

        for fila in reader:
            writer.writerow(fila)

if __name__ == '__main__':
    entrada = 'original.csv'
    salida = 'transformado.csv'

    if not os.path.exists(entrada):
        print(f"❌ No se encuentra el archivo '{entrada}' en la ruta actual.")
    else:
        transformar_csv(entrada, salida)
        print(f"✅ Archivo transformado correctamente y guardado como '{salida}'.")
