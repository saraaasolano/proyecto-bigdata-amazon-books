import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html

from components.mapa_datashader import MapaDatashader
from configuracion import configuracion
from servicios.repositorio_resenas import leer_filtros, repositorio

dash.register_page(__name__, path="/mapa", name="Mapa de reseñas", order=1)

mapa = MapaDatashader(*configuracion.resolucion_mapa, configuracion.minimo_resenas_celda)


def layout(**kwargs):
    return dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("¿Qué muestra el mapa?", className="fw-bold"),
            html.P("Cada reseña es un punto según la longitud de su texto (eje horizontal) y los votos "
                   "que recibió (eje vertical). Datashader agrega todos los puntos en el servidor y solo "
                   "envía la cuadrícula al navegador.", className="small"),
            html.Label("Colorear por", className="fw-semibold small mt-2"),
            dbc.RadioItems(id="mapa-metrica", value="concentracion", className="small",
                           options=[{"label": "Concentración de reseñas", "value": "concentracion"},
                                    {"label": "% de reseñas negativas", "value": "negativas"},
                                    {"label": "Utilidad promedio", "value": "utilidad"}]),
            html.Hr(),
            html.Div(id="mapa-resumen", className="small"),
            html.Div(f"Celdas con menos de {configuracion.minimo_resenas_celda} reseñas no se colorean "
                     "en los modos de porcentaje.", className="small text-muted mt-2"),
        ]), className="shadow-sm border-0 h-100"), lg=3, className="mb-3"),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Mapa de concentración de reseñas (Datashader)", className="fw-bold"),
            dcc.Loading(dcc.Graph(id="grafico-mapa", config={"displayModeBar": False})),
        ]), className="shadow-sm border-0"), lg=9, className="mb-3"),
    ])


@callback(Output("grafico-mapa", "figure"), Output("mapa-resumen", "children"),
          Input("filtro-anios", "value"), Input("filtro-categorias", "value"), Input("mapa-metrica", "value"))
def actualizar_mapa(anios, categorias, metrica):
    puntos = repositorio.puntos_filtrados(leer_filtros(anios, categorias))
    fig = mapa.figura(puntos, metrica)
    celdas = configuracion.resolucion_mapa[0] * configuracion.resolucion_mapa[1]
    resumen = [html.Div([html.B(f"{len(puntos):,}".replace(",", ".")), " reseñas rasterizadas"]),
               html.Div([html.B(f"{celdas:,}".replace(",", ".")), " celdas enviadas al navegador"])]
    return fig, resumen