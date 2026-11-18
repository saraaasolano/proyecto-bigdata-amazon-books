import os
import sys
import glob
import time
import datetime
import pandas as pd
import dask.dataframe as dd
from prefect import task, flow


def carpeta_proyecto():
    actual = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.isdir(os.path.join(actual, "data", "raw")):
            return actual
        padre = os.path.dirname(actual)
        if padre == actual:
            raise FileNotFoundError("No se encontró la carpeta data/raw del proyecto")
        actual = padre


RAIZ = carpeta_proyecto()
RUTA_DATOS = os.path.join(RAIZ, "data", "raw")                    # CSV originales
RUTA_DATOS_PARQUET = os.path.join(RAIZ, "data", "raw_parquet")    # los mismos datos crudos en Parquet
RUTA_RESULTADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "archivos_csv")
os.makedirs(RUTA_RESULTADOS, exist_ok=True)

COLUMNAS_RESENIAS = ["Title", "User_id", "review/score", "review/time", "review/summary", "review/text"]
COLUMNAS_LIBROS = ["Title", "authors", "publishedDate", "categories"]
COLUMNAS_TEXTO = ["Id", "Title", "User_id", "profileName", "review/helpfulness", "review/summary", "review/text"]
REPETICIONES = 3


def peso_mb(ruta):
    if os.path.isdir(ruta):
        return sum(os.path.getsize(f) for f in glob.glob(os.path.join(ruta, "*"))) / 1e6
    return os.path.getsize(ruta) / 1e6


# ---------------------------------------------------------------------------
# 1. Conversión de los datos crudos a Parquet (sin limpiar)
# ---------------------------------------------------------------------------
def parquet_listo():
    return (bool(glob.glob(os.path.join(RUTA_DATOS_PARQUET, "Books_rating*")))
            and os.path.exists(os.path.join(RUTA_DATOS_PARQUET, "books_data.parquet")))


def convertir_a_parquet():
    """Guarda los mismos datos crudos en Parquet para que la única diferencia sea el formato."""
    os.makedirs(RUTA_DATOS_PARQUET, exist_ok=True)
    inicio = time.perf_counter()

    for archivo in sorted(glob.glob(os.path.join(RUTA_DATOS, "Books_rating*.csv"))):
        destino = os.path.join(RUTA_DATOS_PARQUET, os.path.splitext(os.path.basename(archivo))[0])
        dd.read_csv(archivo, blocksize="64MB", dtype={c: "string" for c in COLUMNAS_TEXTO}) \
          .to_parquet(destino, write_index=False)
        print(f"{os.path.basename(archivo)}: {peso_mb(archivo):,.0f} MB en CSV -> {peso_mb(destino):,.0f} MB en Parquet")

    libros_csv = os.path.join(RUTA_DATOS, "books_data.csv")
    libros_pq = os.path.join(RUTA_DATOS_PARQUET, "books_data.parquet")
    libros = pd.read_csv(libros_csv)
    texto = libros.select_dtypes(exclude="number").columns
    libros[texto] = libros[texto].astype("string")
    libros.to_parquet(libros_pq, index=False)
    print(f"books_data.csv: {peso_mb(libros_csv):,.0f} MB en CSV -> {peso_mb(libros_pq):,.0f} MB en Parquet")

    segundos = time.perf_counter() - inicio
    print(f"Conversión terminada en {segundos:.1f} s")
    return segundos


# ---------------------------------------------------------------------------
# 2. Flujo de Prefect (7 tareas)
# ---------------------------------------------------------------------------
def nombre_corrida():
    # Nombre NO aleatorio para cada corrida, con el formato de lectura
    from prefect.runtime import flow_run
    formato = flow_run.parameters.get("formato", "csv")
    return f"analitica-resenias-{formato}-{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}"


@task(name="extraer_resenias", task_run_name="extraer-resenias-{formato}")
def extraer_resenias(formato="csv"):
    # Lee TODOS los archivos de reseñas con la misma estructura (Books_rating*).
    # Si llegan más datos, basta con dejarlos en data/raw y volver a ejecutar el flujo.
    if formato == "parquet":
        archivos = sorted(glob.glob(os.path.join(RUTA_DATOS_PARQUET, "Books_rating*")))
        if not archivos:
            raise FileNotFoundError("No hay datos en Parquet: ejecute primero 'python etl_proyecto.py convertir'")
        resenias = dd.read_parquet(archivos, columns=COLUMNAS_RESENIAS)      # solo lee estas columnas
    else:
        archivos = sorted(glob.glob(os.path.join(RUTA_DATOS, "Books_rating*.csv")))
        if not archivos:
            raise FileNotFoundError(f"No hay archivos Books_rating*.csv en {RUTA_DATOS}")
        resenias = dd.read_csv(archivos, usecols=COLUMNAS_RESENIAS, blocksize="64MB", dtype={"User_id": "str"})
    print(f"Archivos de reseñas ({formato}): {[os.path.basename(a) for a in archivos]}")
    return resenias.rename(columns={"Title": "title", "User_id": "user_id", "review/score": "score",
                                    "review/time": "review_time", "review/summary": "summary",
                                    "review/text": "text"})


@task(name="extraer_libros", task_run_name="extraer-catalogo-libros-{formato}")
def extraer_libros(formato="csv"):
    if formato == "parquet":
        libros = pd.read_parquet(os.path.join(RUTA_DATOS_PARQUET, "books_data.parquet"), columns=COLUMNAS_LIBROS)
    else:
        libros = pd.read_csv(os.path.join(RUTA_DATOS, "books_data.csv"), usecols=COLUMNAS_LIBROS)
    return libros.rename(columns={"Title": "title", "publishedDate": "published_date"})


@task(name="limpiar_resenias", task_run_name="limpiar-resenias")
def limpieza_resenias(resenias):
    resenias["review_time"] = resenias["review_time"].where(resenias["review_time"] > 0)
    resenias["review_year"] = dd.to_datetime(resenias["review_time"], unit="s").dt.year
    resenias["is_negative"] = (resenias["score"] <= 2).astype("int8")      # variable objetivo
    resenias["title_norm"] = resenias["title"].str.lower().str.strip()
    resenias["text_len"] = resenias["text"].str.len()

    # Duplicados: la misma reseña repetida para varias ediciones del libro
    clave = ["user_id", "review_time", "score", "summary", "text_len"]
    resenias = resenias.drop(columns=["text"])
    return resenias.drop_duplicates(subset=clave, split_out=resenias.npartitions)


@task(name="limpiar_libros", task_run_name="limpiar-catalogo-libros")
def limpieza_libros(libros):
    patron = r"\[['\"](.+?)['\"][,\]]"
    libros["category"] = libros["categories"].str.extract(patron)[0].fillna("Desconocido")
    libros["author"] = libros["authors"].str.extract(patron)[0].fillna("Desconocido")
    libros["title_norm"] = libros["title"].str.lower().str.strip()
    libros["published_year"] = pd.to_numeric(libros["published_date"].str[:4], errors="coerce")
    libros.loc[libros["published_year"] == 1016, "published_year"] = 1996
    libros = libros.drop_duplicates(subset="title_norm", keep="first")
    return libros[["title_norm", "author", "category", "published_year"]]


@task(name="unir_tablas", task_run_name="unir-resenias-y-libros")
def union_tablas(resenias, libros):
    union = resenias.merge(dd.from_pandas(libros, npartitions=1), on="title_norm", how="left").compute()
    print(f"Reseñas únicas: {len(union):,}")
    return union


@task(name="libros_en_alerta", task_run_name="analitica-libros-en-alerta")
def libros_en_alerta(union, minimo_resenias=50, top=20):
    # Libros con mayor % de reseñas negativas (solo los que tienen suficientes reseñas)
    tasa_global = union["is_negative"].mean() * 100
    libros = (union.groupby(["title", "author", "category"], dropna=False)
                   .agg(n_resenas=("is_negative", "size"),
                        n_negativas=("is_negative", "sum"),
                        score_medio=("score", "mean"))
                   .reset_index())
    libros = libros[libros["n_resenas"] >= minimo_resenias]
    libros["pct_negativas"] = (libros["n_negativas"] / libros["n_resenas"] * 100).round(2)
    libros["veces_promedio"] = (libros["pct_negativas"] / tasa_global).round(1)
    libros["score_medio"] = libros["score_medio"].round(2)
    alerta = libros.sort_values(["pct_negativas", "n_resenas"], ascending=False).head(top)

    alerta.to_csv(os.path.join(RUTA_RESULTADOS, "libros_en_alerta.csv"), index=False)
    print(f"Promedio global de reseñas negativas: {tasa_global:.2f} %")
    print(alerta[["title", "n_resenas", "pct_negativas", "veces_promedio"]].head(10).to_string(index=False))
    return alerta


@task(name="negativas_por_anio_publicacion", task_run_name="analitica-negativas-por-anio-publicacion")
def negativas_por_anio_publicacion(union, minimo_resenias=1000):
    # Solo años de publicación plausibles y no posteriores a la reseña
    # (si es posterior, el año corresponde a una reedición, no a la edición reseñada)
    validas = union[union["published_year"].between(1800, 2013)
                    & (union["published_year"] <= union["review_year"])]
    print(f"Reseñas con año de publicación válido: {len(validas):,} de {len(union):,}")

    por_anio = (validas.groupby("published_year")
                       .agg(n_resenas=("is_negative", "size"),
                            n_negativas=("is_negative", "sum"),
                            score_medio=("score", "mean"))
                       .reset_index())
    por_anio = por_anio[por_anio["n_resenas"] >= minimo_resenias]
    por_anio["published_year"] = por_anio["published_year"].astype(int)
    por_anio["pct_negativas"] = (por_anio["n_negativas"] / por_anio["n_resenas"] * 100).round(2)
    por_anio["score_medio"] = por_anio["score_medio"].round(3)

    por_anio.to_csv(os.path.join(RUTA_RESULTADOS, "negativas_por_anio_publicacion.csv"), index=False)
    print(por_anio[["published_year", "n_resenas", "pct_negativas"]].tail(10).to_string(index=False))
    return por_anio


@flow(name="flujo_analitica", flow_run_name=nombre_corrida, log_prints=True)
def flujo_analitica(formato: str = "csv"):
    # formato = "csv" (archivos originales) o "parquet" (los mismos datos crudos convertidos a Parquet)
    if formato not in ("csv", "parquet"):
        raise ValueError("formato debe ser 'csv' o 'parquet'")
    resenias = extraer_resenias(formato)
    libros = extraer_libros(formato)
    resenias_limpias = limpieza_resenias(resenias)
    libros_limpios = limpieza_libros(libros)
    union = union_tablas(resenias_limpias, libros_limpios)
    alerta = libros_en_alerta(union)
    por_anio = negativas_por_anio_publicacion(union)
    return alerta, por_anio


# ---------------------------------------------------------------------------
# 3. Comparación CSV vs Parquet
# ---------------------------------------------------------------------------
def comparar_formatos(repeticiones=REPETICIONES):
    """Corre el flujo con ambos formatos, alternando el orden para evitar el efecto de la caché."""
    if not parquet_listo():
        convertir_a_parquet()

    filas, resultados = [], {}
    for rep in range(1, repeticiones + 1):
        orden = ["csv", "parquet"] if rep % 2 else ["parquet", "csv"]
        for formato in orden:
            inicio = time.perf_counter()
            alerta, por_anio = flujo_analitica(formato)
            segundos = time.perf_counter() - inicio
            filas.append({"formato": formato, "repeticion": rep, "segundos": round(segundos, 2)})
            resultados[formato] = (alerta.reset_index(drop=True), por_anio.reset_index(drop=True))
            print(f"==> {formato} | repetición {rep}: {segundos:.2f} s")

    tiempos = pd.DataFrame(filas)
    tiempos.to_csv(os.path.join(RUTA_RESULTADOS, "comparacion_formatos.csv"), index=False)

    resumen = (tiempos.groupby("formato")["segundos"]
                      .agg(promedio="mean", desviacion="std", minimo="min", maximo="max").round(2))
    print("\n", resumen)
    print(f"\nParquet fue {resumen.loc['csv', 'promedio'] / resumen.loc['parquet', 'promedio']:.1f} "
          f"veces más rápido que CSV")

    # Comprobación: el formato no debe cambiar los resultados de la analítica
    for i, nombre in enumerate(["libros_en_alerta", "negativas_por_anio_publicacion"]):
        iguales = resultados["csv"][i].equals(resultados["parquet"][i])
        print(f"{nombre}: {'mismos resultados' if iguales else 'RESULTADOS DISTINTOS'} con ambos formatos")
    return tiempos


if __name__ == "__main__":
    opcion = sys.argv[1] if len(sys.argv) > 1 else "comparar"
    if opcion == "convertir":
        convertir_a_parquet()
    elif opcion in ("csv", "parquet"):
        flujo_analitica(opcion)
    else:
        comparar_formatos()