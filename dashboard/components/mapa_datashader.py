import datashader as ds
import numpy as np
import pandas as pd
import plotly.graph_objects as go


class MapaDatashader:
    """Rasteriza millones de reseñas con Datashader y las muestra como mapa de calor."""

    METRICAS = {
        "concentracion": ("Reseñas por celda", "Viridis"),
        "negativas": ("% reseñas negativas", "YlOrRd"),
        "utilidad": ("Utilidad promedio", "Viridis"),
    }
    RANGO_X = (0.0, 4.6)    
    RANGO_Y = (0.0, 4.1)    

    def __init__(self, ancho: int, alto: int, minimo_celda: int):
        self.canvas = ds.Canvas(plot_width=ancho, plot_height=alto,
                                x_range=self.RANGO_X, y_range=self.RANGO_Y)
        self.minimo_celda = minimo_celda

    def figura(self, puntos: pd.DataFrame, metrica: str) -> go.Figure:
        conteo = self.canvas.points(puntos, "x", "y", agg=ds.count())
        n = conteo.values.astype(float)
        if metrica == "concentracion":
            z = np.where(n > 0, np.log10(n), np.nan)
            texto = n
        else:
            columna = "is_negative" if metrica == "negativas" else "helpful_ratio"
            media = self.canvas.points(puntos, "x", "y", agg=ds.mean(columna)).values
            z = media * 100 if metrica == "negativas" else media
            z = np.where(n >= self.minimo_celda, z, np.nan)
            texto = z

        etiqueta, escala = self.METRICAS[metrica]
        x = 10 ** conteo.coords["x"].values
        y = 10 ** conteo.coords["y"].values         
        fig = go.Figure(go.Heatmap(
            z=z, x=x, y=y, colorscale=escala, customdata=np.stack([n, texto], axis=-1),
            hovertemplate=("Longitud: %{x:,.0f} caracteres<br>Votos + 1: %{y:,.0f}"
                           "<br>Reseñas en la celda: %{customdata[0]:,.0f}"
                           + ("" if metrica == "concentracion" else f"<br>{etiqueta}: %{{customdata[1]:.2f}}")
                           + "<extra></extra>"),
            colorbar=dict(title=etiqueta if metrica != "concentracion" else "Reseñas",
                          tickvals=None if metrica != "concentracion" else [0, 1, 2, 3, 4],
                          ticktext=None if metrica != "concentracion" else ["1", "10", "100", "1k", "10k"]),
            zmin=0 if metrica == "negativas" else None,
            zmax=60 if metrica == "negativas" else None,
        ))
        fig.update_xaxes(type="log", title="Longitud del texto (caracteres, escala log)")
        fig.update_yaxes(type="log", title="Votos recibidos + 1 (escala log)")
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=520,
                          plot_bgcolor="#F8F9FA", paper_bgcolor="rgba(0,0,0,0)")
        return fig