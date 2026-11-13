from dataclasses import dataclass

import duckdb
import pandas as pd

from configuracion import RUTA_PARQUET, configuracion


@dataclass(frozen=True)
class Filtros:
    anio_inicial: int
    anio_final: int
    categorias: tuple = ()           # vacío = todas las categorías


def leer_filtros(anios, categorias) -> Filtros:
    return Filtros(int(anios[0]), int(anios[1]), tuple(categorias or ()))


class RepositorioResenas:
    """Carga las reseñas una sola vez (desde la capa silver) y responde las consultas del tablero."""

    def __init__(self, ruta_parquet: str = RUTA_PARQUET):
        con = duckdb.connect()
        con.execute(f"CREATE OR REPLACE VIEW reviews AS SELECT * FROM read_parquet('{ruta_parquet}')")

        self.puntos = con.sql("""
            SELECT LOG10(text_len)                        AS x,
                   LOG10(votes_total + 1)                 AS y,
                   is_negative,
                   helpful_ratio,
                   CAST(review_year AS SMALLINT)          AS anio,
                   category_group                         AS categoria
            FROM reviews
            WHERE text_len > 0 AND review_year IS NOT NULL
        """).df()
        self.puntos = self.puntos.astype({"x": "float32", "y": "float32", "is_negative": "int8",
                                          "helpful_ratio": "float32", "categoria": "category"})

        self.cubo = con.sql("""
            SELECT category_group AS categoria, CAST(review_year AS INT) AS anio,
                   CAST(score AS INT) AS estrellas,
                   COUNT(*) AS resenas, SUM(is_negative) AS negativas,
                   SUM(es_anonimo::INT) AS anonimas
            FROM reviews WHERE review_year IS NOT NULL
            GROUP BY ALL
        """).df()

        self.libros = con.sql("""
            SELECT title AS libro, main_author AS autor, category_group AS categoria,
                   CAST(review_year AS INT) AS anio,
                   COUNT(*) AS resenas, SUM(is_negative) AS negativas, SUM(score) AS suma_estrellas
            FROM reviews WHERE review_year IS NOT NULL
            GROUP BY ALL
        """).df()
        # Reseñas agregadas por tramo de votos y de utilidad (para la página de patrones)
        self.patrones = con.sql("""
            SELECT category_group AS categoria, CAST(review_year AS INT) AS anio,
                   CASE WHEN votes_total = 0 THEN '0' WHEN votes_total <= 2 THEN '1-2'
                        WHEN votes_total <= 5 THEN '3-5' WHEN votes_total <= 10 THEN '6-10'
                        WHEN votes_total <= 20 THEN '11-20' WHEN votes_total <= 50 THEN '21-50'
                        ELSE '>50' END AS tramo_votos,
                   CASE WHEN helpful_ratio IS NULL THEN 'Sin votos'
                        WHEN helpful_ratio < 0.2 THEN '0-20%' WHEN helpful_ratio < 0.4 THEN '20-40%'
                        WHEN helpful_ratio < 0.6 THEN '40-60%' WHEN helpful_ratio < 0.8 THEN '60-80%'
                        ELSE '80-100%' END AS tramo_utilidad,
                   COUNT(*) AS resenas, SUM(is_negative) AS negativas
            FROM reviews WHERE review_year IS NOT NULL
            GROUP BY ALL
        """).df()
        con.close()

    # ---- propiedades generales ----
    @property
    def total(self) -> int:
        return len(self.puntos)

    @property
    def anios(self) -> list:
        return sorted(int(a) for a in self.cubo["anio"].unique())

    @property
    def categorias(self) -> list:
        orden = self.cubo.groupby("categoria")["resenas"].sum().sort_values(ascending=False)
        return list(orden.index)

    # ---- filtros ----
    @staticmethod
    def _filtrar(tabla, filtros: Filtros, col_categoria="categoria", col_anio="anio"):
        seleccion = tabla[col_anio].between(filtros.anio_inicial, filtros.anio_final)
        if filtros.categorias:
            seleccion &= tabla[col_categoria].isin(filtros.categorias)
        return tabla[seleccion]

    # ---- consultas ----
    def kpis(self, filtros: Filtros) -> dict:
        c = self._filtrar(self.cubo, filtros)
        n = int(c["resenas"].sum())
        if n == 0:
            return {"resenas": 0, "pct_negativas": 0, "score": 0, "pct_anonimas": 0, "libros": 0}
        libros = self._filtrar(self.libros, filtros)["libro"].nunique()
        return {"resenas": n,
                "pct_negativas": c["negativas"].sum() / n * 100,
                "score": (c["estrellas"] * c["resenas"]).sum() / n,
                "pct_anonimas": c["anonimas"].sum() / n * 100,
                "libros": libros}

    def serie_anual(self, filtros: Filtros) -> pd.DataFrame:
        c = self._filtrar(self.cubo, filtros).groupby("anio")[["resenas", "negativas"]].sum().reset_index()
        c["pct_negativas"] = c["negativas"] / c["resenas"] * 100
        return c

    def por_categoria(self, filtros: Filtros, minimo=2000) -> pd.DataFrame:
        c = self._filtrar(self.cubo, filtros).groupby("categoria")[["resenas", "negativas"]].sum().reset_index()
        c["pct_negativas"] = c["negativas"] / c["resenas"] * 100
        return c[c["resenas"] >= minimo].sort_values("pct_negativas")

    def distribucion_estrellas(self, filtros: Filtros) -> pd.DataFrame:
        c = self._filtrar(self.cubo, filtros).groupby("estrellas")["resenas"].sum().reset_index()
        c["pct"] = c["resenas"] / c["resenas"].sum() * 100
        return c

    def libros_en_alerta(self, filtros: Filtros, top=10) -> pd.DataFrame:
        l = self._filtrar(self.libros, filtros)
        l = l.groupby(["libro", "autor", "categoria"], dropna=False)[["resenas", "negativas", "suma_estrellas"]].sum()
        l = l[l["resenas"] >= configuracion.minimo_resenas_libro].reset_index()
        l["pct_negativas"] = (l["negativas"] / l["resenas"] * 100).round(1)
        l["estrellas"] = (l["suma_estrellas"] / l["resenas"]).round(2)
        return l.sort_values(["pct_negativas", "resenas"], ascending=False).head(top)

    def autores_negativos(self, filtros: Filtros, top=10) -> pd.DataFrame:
        a = self._filtrar(self.libros, filtros)
        a = a[a["autor"] != "Desconocido"]
        a = a.groupby("autor")[["resenas", "negativas"]].sum().reset_index()
        a = a[a["resenas"] >= configuracion.minimo_resenas_autor]
        a["pct_negativas"] = a["negativas"] / a["resenas"] * 100
        return a.sort_values("pct_negativas", ascending=False).head(top).sort_values("pct_negativas")

    ORDEN_VOTOS = ["0", "1-2", "3-5", "6-10", "11-20", "21-50", ">50"]
    ORDEN_UTILIDAD = ["Sin votos", "0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]

    def tasa_por_tramo(self, filtros: Filtros, columna: str) -> pd.DataFrame:
        orden = self.ORDEN_VOTOS if columna == "tramo_votos" else self.ORDEN_UTILIDAD
        p = self._filtrar(self.patrones, filtros).groupby(columna)[["resenas", "negativas"]].sum()
        p = p.reindex(orden).dropna().reset_index()
        p["pct_negativas"] = p["negativas"] / p["resenas"] * 100
        p["pct_resenas"] = p["resenas"] / p["resenas"].sum() * 100
        return p

    def votos_por_utilidad(self, filtros: Filtros):
        p = self._filtrar(self.patrones, filtros)
        p = p[p["tramo_votos"] != "0"]                         # sin votos no hay utilidad
        t = p.groupby(["tramo_utilidad", "tramo_votos"])[["resenas", "negativas"]].sum()
        n = t["resenas"].unstack().reindex(index=self.ORDEN_UTILIDAD[1:], columns=self.ORDEN_VOTOS[1:])
        pct = (t["negativas"] / t["resenas"] * 100).unstack().reindex_like(n)
        return pct.where(n >= configuracion.minimo_resenas_patron), n

    def puntos_filtrados(self, filtros: Filtros) -> pd.DataFrame:
        return self._filtrar(self.puntos, filtros)

repositorio = RepositorioResenas()
print(f"{repositorio.total:,} reseñas en memoria | {len(repositorio.categorias)} categorías | "
      f"años {repositorio.anios[0]}-{repositorio.anios[-1]}")