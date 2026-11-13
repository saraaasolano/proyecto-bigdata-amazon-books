import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from dash import Input, Output, callback, dcc, html

from configuracion import COLORES, estilo
from servicios.repositorio_resenas import Filtros, repositorio

dash.register_page(__name__, path="/comparacion", name="Comparación", order=3)


def layout(**kwargs):
    categorias = repositorio.categorias
    return html.Div([
        dbc.Card(dbc.CardBody(dbc.Row([
            dbc.Col([html.Label("Categoría A", className="fw-semibold small"),
                     dcc.Dropdown(id="comp-a", options=categorias, value="Computers", clearable=False)], md=6),
            dbc.Col([html.Label("Categoría B", className="fw-semibold small"),
                     dcc.Dropdown(id="comp-b", options=categorias, value="Juvenile Fiction", clearable=False)], md=6),
        ])), className="shadow-sm border-0 mb-3"),
        dbc.Row(id="comp-kpis", className="mb-1"),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("% de reseñas negativas por año", className="fw-bold"),
                dcc.Graph(id="comp-serie", config={"displayModeBar": False})]),
                className="shadow-sm border-0"), lg=7, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Distribución de estrellas", className="fw-bold"),
                dcc.Graph(id="comp-estrellas", config={"displayModeBar": False})]),
                className="shadow-sm border-0"), lg=5, className="mb-3"),
        ]),
    ])


@callback(Output("comp-kpis", "children"), Output("comp-serie", "figure"), Output("comp-estrellas", "figure"),
          Input("comp-a", "value"), Input("comp-b", "value"), Input("filtro-anios", "value"))
def actualizar_comparacion(cat_a, cat_b, anios):
    colores = {cat_a: COLORES["negativo"], cat_b: COLORES["positivo"]}
    tarjetas, series, estrellas = [], [], []
    for categoria in (cat_a, cat_b):
        f = Filtros(int(anios[0]), int(anios[1]), (categoria,))
        k = repositorio.kpis(f)
        tarjetas.append(dbc.Col(dbc.Card(dbc.CardBody([
            html.Div(categoria, className="fw-bold", style={"color": colores[categoria]}),
            html.Div([html.Span(f"{k['pct_negativas']:.2f} %", className="h4 fw-bold me-2"),
                      html.Span("reseñas negativas", className="small text-muted")]),
            html.Div(f"{k['resenas']:,} reseñas · {k['score']:.2f} estrellas en promedio".replace(",", "."),
                     className="small text-muted"),
        ]), className="shadow-sm border-0 mb-3"), md=6))
        s = repositorio.serie_anual(f).assign(categoria=categoria)
        series.append(s[s["resenas"] >= 100])
        estrellas.append(repositorio.distribucion_estrellas(f).assign(categoria=categoria))

    fig_serie = px.line(pd.concat(series), x="anio", y="pct_negativas", color="categoria", markers=True,
                        color_discrete_map=colores, custom_data=["resenas"])
    fig_serie.update_traces(line_width=3,
                            hovertemplate="%{x}: %{y:.1f} % negativas (%{customdata[0]:,} reseñas)<extra></extra>")
    fig_serie.update_layout(xaxis_title="Año", yaxis_title="% negativas", legend=dict(orientation="h", y=1.12))
    estilo(fig_serie)

    fig_estrellas = px.bar(pd.concat(estrellas), x="estrellas", y="pct", color="categoria", barmode="group",
                           color_discrete_map=colores)
    fig_estrellas.update_traces(hovertemplate="%{x} estrellas: %{y:.1f} %<extra></extra>")
    fig_estrellas.update_layout(xaxis_title="Estrellas", yaxis_title="% de reseñas",
                                legend=dict(orientation="h", y=1.12))
    estilo(fig_estrellas)
    return tarjetas, fig_serie, fig_estrellas