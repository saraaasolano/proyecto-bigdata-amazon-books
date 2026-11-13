import dash_bootstrap_components as dbc
from dash import html


class TarjetaKpi:
    """Tarjeta con un indicador: título, valor destacado y una nota corta."""

    def __init__(self, titulo: str, id_valor: str, nota: str = "", color: str = "primary"):
        self.titulo = titulo
        self.id_valor = id_valor
        self.nota = nota
        self.color = color

    def display(self):
        return dbc.Card(dbc.CardBody([
            html.Div(self.titulo, className="text-muted small text-uppercase fw-semibold"),
            html.H3("—", id=self.id_valor, className=f"text-{self.color} my-1 fw-bold"),
            html.Div(self.nota, className="small text-muted"),
        ]), className="h-100 shadow-sm border-0 tarjeta-kpi")