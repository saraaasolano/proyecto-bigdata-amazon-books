import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from components.tarjerta_kpi import TarjetaKpi
from configuracion import COLORES, COLORES_ESTRELLAS, configuracion, estilo
from servicios.repositorio_resenas import leer_filtros, repositorio

dash.register_page(__name__, path="/", name="Inicio", order=0)


def layout(**kwargs):
    indicadores = [
        TarjetaKpi("Reseñas analizadas", "kpi-resenas", "únicas, sin duplicados"),
        TarjetaKpi("Reseñas negativas", "kpi-negativas", "1 o 2 estrellas", "danger"),
        TarjetaKpi("Calificación media", "kpi-score", "de 5 estrellas", "success"),
        TarjetaKpi("Libros reseñados", "kpi-libros", "títulos distintos", "info"),
        TarjetaKpi("Reseñas anónimas", "kpi-anonimas", "sin identificador", "secondary"),
    ]
    return html.Div([
        dbc.Row([dbc.Col(i.display(), lg=True, md=4, xs=6, className="mb-3") for i in indicadores]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Evolución anual de las reseñas negativas", className="fw-bold"),
                dcc.Graph(id="grafico-serie", config={"displayModeBar": False})]),
                className="shadow-sm border-0 h-100"), lg=7, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Distribución de estrellas", className="fw-bold"),
                dcc.Graph(id="grafico-estrellas", config={"displayModeBar": False})]),
                className="shadow-sm border-0 h-100"), lg=5, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("% de reseñas negativas por categoría", className="fw-bold"),
                html.Div("Categorías con al menos 2.000 reseñas. Línea punteada: promedio del filtro.",
                         className="small text-muted"),
                dcc.Graph(id="grafico-categorias", config={"displayModeBar": False})]),
                className="shadow-sm border-0 h-100"), lg=6, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Libros en alerta", className="fw-bold"),
                html.Div(f"Mayor % de reseñas negativas (mínimo {configuracion.minimo_resenas_libro} reseñas).",
                         className="small text-muted mb-2"),
                dash_table.DataTable(
                    id="tabla-alerta",
                    columns=[{"name": "Libro", "id": "libro"}, {"name": "Autor", "id": "autor"},
                             {"name": "Reseñas", "id": "resenas"}, {"name": "% negativas", "id": "pct_negativas"},
                             {"name": "Estrellas", "id": "estrellas"}],
                    style_cell={"fontFamily": "inherit", "fontSize": 13, "textAlign": "left",
                                "whiteSpace": "normal", "height": "auto", "padding": "6px"},
                    style_header={"fontWeight": "bold", "backgroundColor": "#2C3E50", "color": "white"},
                    style_data_conditional=[{"if": {"column_id": "pct_negativas"},
                                             "color": COLORES["negativo"], "fontWeight": "bold"}],
                    page_size=10)]),
                className="shadow-sm border-0 h-100"), lg=6, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([
                html.H6("Autores con mayor % de reseñas negativas", className="fw-bold"),
                html.Div(f"Autores con al menos {configuracion.minimo_resenas_autor} reseñas en el filtro "
                         "(sin contar \"Desconocido\"). Línea punteada: promedio del filtro.",
                         className="small text-muted"),
                dcc.Graph(id="grafico-autores", config={"displayModeBar": False})]),
                className="shadow-sm border-0"), lg=12, className="mb-3"),
        ]),
    ])


@callback(
    Output("kpi-resenas", "children"), Output("kpi-negativas", "children"), Output("kpi-score", "children"),
    Output("kpi-libros", "children"), Output("kpi-anonimas", "children"),
    Output("grafico-serie", "figure"), Output("grafico-estrellas", "figure"),
    Output("grafico-categorias", "figure"), Output("tabla-alerta", "data"),
    Output("grafico-autores", "figure"),
    Input("filtro-anios", "value"), Input("filtro-categorias", "value"))
def actualizar_inicio(anios, categorias):
    f = leer_filtros(anios, categorias)
    k = repositorio.kpis(f)

    serie = repositorio.serie_anual(f)
    fig_serie = go.Figure()
    fig_serie.add_bar(x=serie["anio"], y=serie["resenas"], name="Reseñas", yaxis="y2",
                      marker_color="#D5DBDB", hovertemplate="%{x}: %{y:,} reseñas<extra></extra>")
    fig_serie.add_scatter(x=serie["anio"], y=serie["pct_negativas"], name="% negativas", mode="lines+markers",
                          line=dict(color=COLORES["negativo"], width=3),
                          hovertemplate="%{x}: %{y:.1f} % negativas<extra></extra>")
    fig_serie.update_layout(yaxis=dict(title="% negativas", rangemode="tozero"),
                            yaxis2=dict(title="Reseñas", overlaying="y", side="right", showgrid=False),
                            legend=dict(orientation="h", y=1.12))
    estilo(fig_serie)

    estrellas = repositorio.distribucion_estrellas(f)
    fig_estrellas = px.bar(estrellas, x="estrellas", y="pct", text=estrellas["pct"].map("{:.1f}%".format),
                           color="estrellas", color_discrete_sequence=COLORES_ESTRELLAS)
    fig_estrellas.update_traces(marker_color=COLORES_ESTRELLAS[:len(estrellas)], showlegend=False,
                                hovertemplate="%{x} estrellas: %{y:.1f} %<extra></extra>")
    fig_estrellas.update_layout(xaxis_title="Estrellas", yaxis_title="% de reseñas", coloraxis_showscale=False)
    estilo(fig_estrellas)

    cat = repositorio.por_categoria(f)
    fig_cat = px.bar(cat, x="pct_negativas", y="categoria", orientation="h",
                     color="pct_negativas", color_continuous_scale="Reds",
                     custom_data=["resenas"])
    fig_cat.update_traces(hovertemplate="%{y}: %{x:.1f} % negativas<br>%{customdata[0]:,} reseñas<extra></extra>")
    fig_cat.add_vline(x=k["pct_negativas"], line_dash="dot", line_color=COLORES["positivo"])
    fig_cat.update_layout(xaxis_title="% negativas", yaxis_title="", coloraxis_showscale=False)
    estilo(fig_cat, alto=max(320, 22 * len(cat)))

    alerta = repositorio.libros_en_alerta(f).to_dict("records")

    autores = repositorio.autores_negativos(f)
    fig_autores = px.bar(autores, x="pct_negativas", y="autor", orientation="h",
                         text=autores["pct_negativas"].map("{:.1f}%".format),
                         color="pct_negativas", color_continuous_scale="Reds", custom_data=["resenas"],
                         range_color=(0, autores["pct_negativas"].max() if len(autores) else 1))
    fig_autores.update_traces(textposition="outside",
                              hovertemplate="%{y}: %{x:.1f} % negativas<br>%{customdata[0]:,} reseñas<extra></extra>")
    fig_autores.add_vline(x=k["pct_negativas"], line_dash="dot", line_color=COLORES["positivo"])
    fig_autores.update_layout(xaxis_title="% negativas", yaxis_title="", coloraxis_showscale=False)
    estilo(fig_autores, alto=360)

    return (f"{k['resenas']:,}".replace(",", "."), f"{k['pct_negativas']:.2f} %", f"{k['score']:.2f} ★",
            f"{k['libros']:,}".replace(",", "."), f"{k['pct_anonimas']:.1f} %",
            fig_serie, fig_estrellas, fig_cat, alerta, fig_autores)