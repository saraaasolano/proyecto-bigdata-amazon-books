import os
import glob
import datetime
import pandas as pd
import dask.dataframe as dd
from prefect import task, flow

# Rutas (relativas a esta carpeta flujo_analitica)
CARPETA = os.path.dirname(os.path.abspath(__file__))
RUTA_DATOS = os.path.join(CARPETA, "..", "data", "raw")        # CSV originales
RUTA_RESULTADOS = os.path.join(CARPETA, "archivos_csv")        # resultados de la analítica
os.makedirs(RUTA_RESULTADOS, exist_ok=True)


# Nombre NO aleatorio para cada corrida del flujo
def nombre_corrida():
    ahora = datetime.datetime.now()
    return f"analitica-resenias-{ahora:%Y-%m-%d_%H-%M}"


@task(name="extraer_resenias", task_run_name="extraer-resenias-csv")
def extraer_resenias():
    # Lee TODOS los archivos de reseñas con la misma estructura (Books_rating*.csv).
    # Si llegan más datos, basta con dejarlos en data/raw y volver a ejecutar el flujo.
    archivos = sorted(glob.glob(os.path.join(RUTA_DATOS, "Books_rating*.csv")))
    print(f"Archivos de reseñas: {[os.path.basename(a) for a in archivos]}")
    columnas = ["Title", "User_id", "review/score", "review/time", "review/summary", "review/text"]
    resenias = dd.read_csv(archivos, usecols=columnas, blocksize="64MB", dtype={"User_id": "str"})
    resenias = resenias.rename(columns={"Title": "title", "User_id": "user_id", "review/score": "score",
                                        "review/time": "review_time", "review/summary": "summary",
                                        "review/text": "text"})
    return resenias


@task(name="extraer_libros", task_run_name="extraer-catalogo-libros")
def extraer_libros():
    columnas = ["Title", "authors", "publishedDate", "categories"]
    libros = pd.read_csv(os.path.join(RUTA_DATOS, "books_data.csv"), usecols=columnas)
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
def flujo_analitica():
    resenias = extraer_resenias()
    libros = extraer_libros()
    resenias_limpias = limpieza_resenias(resenias)
    libros_limpios = limpieza_libros(libros)
    union = union_tablas(resenias_limpias, libros_limpios)
    alerta = libros_en_alerta(union)
    por_anio = negativas_por_anio_publicacion(union)
    return alerta, por_anio


if __name__ == "__main__":
    flujo_analitica()