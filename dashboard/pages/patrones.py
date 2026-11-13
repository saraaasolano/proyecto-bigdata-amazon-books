import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from configuracion import COLORES, configuracion, estilo
from servicios.repositorio_resenas import leer_filtros, repositorio

dash.register_page(__name__, path="/patrones", name="Votos y utilidad", order=2)


def tarjeta(titulo, nota, id_grafico):
    return dbc.Card(dbc.CardBody([
        html.H6(titulo, className="fw-bold"),
        html.Div(nota, className="small text-muted"),
        dcc.Graph(id=id_grafico, config={"displayModeBar": False}),
    ]), className="shadow-sm border-0 h-100")


def layout(**kwargs):
    return html.Div([
        dbc.Alert([
            html.B("Hallazgo principal del proyecto. "),
            "Las reseñas negativas reciben muchos más votos que las positivas, pero esos votos dicen que "
            "no fueron útiles: los lectores que disfrutaron el libro las votan en contra. Los votos se "
            "acumulan después de publicar la reseña, así que explican la insatisfacción pero no la anticipan.",
        ], color="light", className="small shadow-sm border-0"),
        dbc.Row([
            dbc.Col(tarjeta("% de reseñas negativas según los votos recibidos",
                            "Línea punteada: promedio del filtro.", "patron-votos"), lg=6, className="mb-3"),
            dbc.Col(tarjeta("% de reseñas negativas según la proporción de utilidad",
                            "Utilidad = votos útiles / votos totales. Línea punteada: promedio del filtro.",
                            "patron-utilidad"), lg=6, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(tarjeta("Votos × utilidad: % de reseñas negativas",
                            f"Solo reseñas con al menos un voto. Las celdas con menos de "
                            f"{configuracion.minimo_resenas_patron} reseñas se dejan en blanco.",
                            "patron-cruce"), lg=12, className="mb-3"),
        ]),
    ])


def barras(t, columna, titulo_x, promedio):
    colores = [COLORES["negativo"] if v > promedio else COLORES["positivo"] for v in t["pct_negativas"]]
    fig = go.Figure(go.Bar(
        x=t[columna], y=t["pct_negativas"], marker_color=colores,
        text=t["pct_negativas"].map("{:.1f}%".format), textposition="outside",
        customdata=t[["resenas", "pct_resenas"]],
        hovertemplate=("%{x}: %{y:.1f} % negativas<br>%{customdata[0]:,} reseñas "
                       "(%{customdata[1]:.1f} % del total)<extra></extra>")))
    fig.add_hline(y=promedio, line_dash="dot", line_color=COLORES["positivo"])
    fig.update_layout(xaxis_title=titulo_x, yaxis_title="% negativas",
                      yaxis_range=[0, max(t["pct_negativas"].max() * 1.15, promedio * 1.3)])
    return estilo(fig, alto=340)


@callback(Output("patron-votos", "figure"), Output("patron-utilidad", "figure"), Output("patron-cruce", "figure"),
          Input("filtro-anios", "value"), Input("filtro-categorias", "value"))
def actualizar_patrones(anios, categorias):
    f = leer_filtros(anios, categorias)
    promedio = repositorio.kpis(f)["pct_negativas"]

    fig_votos = barras(repositorio.tasa_por_tramo(f, "tramo_votos"), "tramo_votos", "Votos totales", promedio)
    fig_util = barras(repositorio.tasa_por_tramo(f, "tramo_utilidad"), "tramo_utilidad",
                      "Proporción de utilidad", promedio)

    pct, n = repositorio.votos_por_utilidad(f)
    fig_cruce = go.Figure(go.Heatmap(
        z=pct.values, x=list(pct.columns), y=list(pct.index), colorscale="Reds", zmin=0, zmax=100,
        text=pct.map(lambda v: "" if v != v else f"{v:.0f}%").values, texttemplate="%{text}",
        customdata=n.fillna(0).values,
        hovertemplate=("Votos: %{x}<br>Utilidad: %{y}<br>%{z:.1f} % negativas<br>"
                       "%{customdata:,} reseñas<extra></extra>"),
        colorbar=dict(title="% negativas")))
    fig_cruce.update_layout(xaxis_title="Votos totales", yaxis_title="Proporción de utilidad")
    estilo(fig_cruce, alto=380)
    fig_cruce.update_xaxes(type="category")
    fig_cruce.update_yaxes(type="category", gridcolor="rgba(0,0,0,0)")

    return fig_votos, fig_util, fig_cruce