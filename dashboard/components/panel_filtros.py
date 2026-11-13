import dash_bootstrap_components as dbc
from dash import dcc, html


class PanelFiltros:

    def __init__(self, repositorio):
        self.anios = repositorio.anios
        self.categorias = repositorio.categorias

    def display(self):
        return dbc.Card(dbc.CardBody(dbc.Row([
            dbc.Col([
                html.Label("Años de la reseña", className="fw-semibold small"),
                dcc.RangeSlider(id="filtro-anios", min=self.anios[0], max=self.anios[-1], step=1,
                                value=[self.anios[0], self.anios[-1]],
                                marks={a: str(a) for a in self.anios if a % 3 == 0 or a == self.anios[-1]},
                                tooltip={"placement": "bottom"}),
            ], lg=7),
            dbc.Col([
                html.Label("Categorías (vacío = todas)", className="fw-semibold small"),
                dcc.Dropdown(id="filtro-categorias", options=self.categorias, multi=True,
                             placeholder="Todas las categorías"),
            ], lg=5),
        ])), className="shadow-sm border-0 mb-3")