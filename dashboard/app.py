import dash
import dash_bootstrap_components as dbc
from dash import Dash, html

from components.panel_filtros import PanelFiltros
from configuracion import configuracion
from servicios.repositorio_resenas import repositorio

app = Dash(__name__, use_pages=True, external_stylesheets=[configuracion.tema],
           title=configuracion.titulo, suppress_callback_exceptions=True)

app.index_string = app.index_string.replace("</head>", """
<style>
  body { background: #F4F6F8; }
  .tarjeta-kpi { border-left: 4px solid #18BC9C !important; }
  .navbar-brand { font-weight: 700; letter-spacing: .3px; }
  .nav-link.active { font-weight: 700; border-bottom: 2px solid #18BC9C; }
</style>
</head>""")

barra_navegacion = dbc.NavbarSimple(
    [dbc.NavItem(dbc.NavLink(pagina["name"], href=pagina["relative_path"], active="exact"))
     for pagina in dash.page_registry.values()],
    brand="Insatisfacción del lector · Amazon Books", color="primary", dark=True, className="mb-3",
)

app.layout = html.Div([
    barra_navegacion,
    dbc.Container([
        PanelFiltros(repositorio).display(),     
        dash.page_container,                    
        html.Div("Fuente: Amazon Books Reviews (Kaggle) · reseñas únicas sin duplicados · Proyecto Big Data",
                 className="text-center text-muted small my-3"),
    ], fluid=True),
])

if __name__ == "__main__":
    app.run(port=configuracion.puerto, debug=False)