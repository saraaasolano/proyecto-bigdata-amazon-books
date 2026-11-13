from dataclasses import dataclass
from pathlib import Path

import dash_bootstrap_components as dbc

# Carpeta raíz del proyecto (Proyecto_BigData), sin importar desde dónde se ejecute
RAIZ = Path(__file__).resolve().parent.parent
RUTA_PARQUET = (RAIZ / "data" / "silver" / "reviews_libros").as_posix() + "/*.parquet"


@dataclass(frozen=True)
class Configuracion:
    puerto: int = 8050
    tema: str = dbc.themes.FLATLY
    titulo: str = "Insatisfacción del lector · Big Data"
    resolucion_mapa: tuple = (320, 220)        # celdas de la cuadrícula de Datashader (ancho, alto)
    minimo_resenas_celda: int = 20             # celdas con menos reseñas no se colorean por porcentaje
    minimo_resenas_libro: int = 50             # libros con menos reseñas no entran en "libros en alerta"
    minimo_resenas_autor: int = 500            # autores con menos reseñas no entran en el gráfico de autores
    minimo_resenas_patron: int = 300           # celdas del mapa votos × utilidad con menos reseñas se ocultan


configuracion = Configuracion()
COLORES = {"negativo": "#C44E52", "positivo": "#2C3E50", "acento": "#18BC9C", "neutro": "#95A5A6"}
COLORES_ESTRELLAS = ["#C44E52", "#E67E22", "#F1C40F", "#52BE80", "#2C3E50"]


def estilo(fig, alto=320):
    """Estilo común de todos los gráficos de Plotly."""
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=alto, plot_bgcolor="white",
                      paper_bgcolor="rgba(0,0,0,0)", font=dict(size=12), legend_title_text="")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#ECF0F1")
    return fig