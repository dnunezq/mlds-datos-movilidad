import pandas as pd
import folium
from folium.plugins import HeatMap, FastMarkerCluster
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import datetime
import requests # Para descargar datos desde URLs\

# --- 1. Cargar y preparar los datos desde URLs ---
# IMPORTANTE: Reemplaza estas URLs con las tuyas de GitHub Raw si cambian
URL_CSV = 'https://raw.githubusercontent.com/dnunezq/mlds-datos-movilidad/refs/heads/main/data/comparendo_2019_limpio_bogota.csv'
#URL_GEOJSON = 'https://raw.githubusercontent.com/dnunezq/mlds-datos-movilidad/main/data/poligonos-localidades.geojson'

try:
    df = pd.read_csv(URL_CSV)
    df['FECHA_HORA'] = pd.to_datetime(df['FECHA_HORA'], errors='coerce')
    df = df.rename(columns={'HORA_OCURRENCIA': 'hora_ocurrencia'})
    df['hora_ocurrencia'] = pd.to_datetime(df['hora_ocurrencia'], format='%H:%M:%S', errors='coerce').dt.time

    # Descargar y cargar el GeoJSON usando requests y json
    #response = requests.get(URL_GEOJSON)
    #response.raise_for_status() # Lanza un error si la descarga falla
    #geojson_localidades = response.json()

except Exception as e:
    print(f"Error al cargar los datos desde las URLs: {e}")
    exit()


df = df.rename(columns={
    'FECHA_HORA': 'fecha_hora', 'LATITUD': 'latitud', 'LONGITUD': 'longitud',
    'DES_INFRACCION': 'tipo_infraccion', 'TIPO_SERVICIO': 'tipo_servicio'
})

df.dropna(subset=['fecha_hora', 'hora_ocurrencia', 'latitud', 'longitud', 'INFRACCION', 'tipo_infraccion', 'CLASE_VEHICULO', 'LOCALIDAD', 'tipo_servicio'], inplace=True)

df['hora'] = df['hora_ocurrencia'].apply(lambda t: t.hour)
df['mes'] = df['fecha_hora'].dt.month
df['dia_semana_num'] = df['fecha_hora'].dt.dayofweek
dias_map = {0: 'Lunes', 1: 'Martes', 2: 'Miércoles', 3: 'Jueves', 4: 'Viernes', 5: 'Sábado', 6: 'Domingo'}
df['dia_semana_nombre'] = df['dia_semana_num'].map(dias_map)

df_infracciones_unicas = df.drop_duplicates(subset=['INFRACCION']).sort_values('INFRACCION')
opciones_infraccion = [{'label': f"{row['INFRACCION']} - {row['tipo_infraccion'].lower()}", 'value': row['INFRACCION']} for index, row in df_infracciones_unicas.iterrows()]
valores_iniciales_infraccion = df_infracciones_unicas['INFRACCION'].unique()[:5].tolist()

# --- 2. Inicializar la aplicación ---
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# --- 3. Layout del Dashboard ---
app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Dashboard de Infracciones de Tránsito en Bogotá", className="text-center text-primary mb-4"), width=12)),
    dbc.Row([
        dbc.Col([
            dbc.Card(
                dbc.CardBody([
                    html.H6("Total de Comparendos Filtrados", className="card-subtitle"),
                    html.H2(id='contador-comparendos', className="text-center text-primary")
                ]),
                className="mb-3", # Margen inferior para separarlo de los filtros
            ),
            dbc.Card(dbc.CardBody([
                html.H4("Filtros", className="card-title"),
                dbc.Label("Tipo de Visualización del Mapa:"),
                dbc.RadioItems(id='map-type-selector', options=[{'label': 'Mapa de Calor', 'value': 'heatmap'}, {'label': 'Clúster de Puntos', 'value': 'cluster'}], value='heatmap', inline=True, className="mb-3"),
                
                # --- NUEVO: Interruptor para la capa GeoJSON ---
                #dbc.Switch(id='switch-geojson', label="Mostrar Límite de Localidades", value=False, className="my-2"),
                
                html.Hr(),
                dcc.Dropdown(
                    id='filtro-infraccion',
                    options=opciones_infraccion,
                    value=valores_iniciales_infraccion,
                    multi=True,
                    placeholder="Seleccionar infracción...",
                    optionHeight=115
                ),
                dcc.Dropdown(id='filtro-vehiculo', options=[{'label': i, 'value': i} for i in sorted(df['CLASE_VEHICULO'].unique())], multi=True, placeholder="Seleccionar vehículo...", className="mt-3"),
                dcc.Dropdown(id='filtro-localidad', options=[{'label': i, 'value': i} for i in sorted(df['LOCALIDAD'].unique())], multi=True, placeholder="Seleccionar localidad...", className="mt-3"),
                html.Hr(),
                html.Label("Hora del día:", className="mt-3"),
                dcc.RangeSlider(id='slider-hora', min=0, max=23, step=1, value=[0, 23], marks={i: f'{i}h' for i in range(0, 24, 3)}),
                html.Label("Mes del año:", className="mt-3"),
                dcc.RangeSlider(id='slider-mes', min=1, max=12, step=1, value=[1, 12], marks={1: 'Ene', 3:'Mar', 6:'Jun', 9:'Sep', 12:'Dic'}),
            ])),
            dbc.Card(dcc.Graph(id='graph-distribucion-hora'), className="mt-3"),
            dbc.Card(dcc.Graph(id='graph-distribucion-dia'), className="mt-3"),
            dbc.Card(dcc.Graph(id='graph-top-localidades'), className="mt-3"),
            dbc.Card(dcc.Graph(id='graph-top-infracciones'), className="mt-3"),
            dbc.Card(dcc.Graph(id='graph-top-vehiculos'), className="mt-3"),
            dbc.Card(dcc.Graph(id='graph-top-servicio'), className="mt-3"),
        ], md=4),
        dbc.Col(html.Iframe(id='mapa', srcDoc=None, style={'width': '100%', 'height': '100vh', 'border': 'none'}), md=8)
    ])
], fluid=True)


# --- 4. Callback para actualizar todos los componentes ---
@app.callback(
    [Output('contador-comparendos', 'children'),
     Output('mapa', 'srcDoc'),
     Output('graph-top-infracciones', 'figure'),
     Output('graph-top-vehiculos', 'figure'),
     Output('graph-top-servicio', 'figure'),
     Output('graph-top-localidades', 'figure'),
     Output('graph-distribucion-hora', 'figure'),
     Output('graph-distribucion-dia', 'figure')],
    # --- NUEVO: Input del interruptor GeoJSON ---
    [Input('map-type-selector', 'value'),
     #Input('switch-geojson', 'value'),
     Input('filtro-infraccion', 'value'),
     Input('filtro-vehiculo', 'value'),
     Input('filtro-localidad', 'value'),
     Input('slider-hora', 'value'),
     Input('slider-mes', 'value')]
)
def update_dashboard(map_type, codigos_infraccion, clases_vehiculo, localidades, rango_horas, rango_meses):
    
    df_filtrado = df[
        (df['INFRACCION'].isin(codigos_infraccion if codigos_infraccion else df['INFRACCION'].unique())) &
        (df['CLASE_VEHICULO'].isin(clases_vehiculo if clases_vehiculo else df['CLASE_VEHICULO'].unique())) &
        (df['LOCALIDAD'].isin(localidades if localidades else df['LOCALIDAD'].unique())) &
        (df['hora'] >= rango_horas[0]) & (df['hora'] <= rango_horas[1]) &
        (df['mes'] >= rango_meses[0]) & (df['mes'] <= rango_meses[1])
    ]

    numero_comparendos = len(df_filtrado)
    texto_contador = f"{numero_comparendos:,}"

    map_center = [4.60971, -74.08175]
    if not df_filtrado.empty:
        map_center = [df_filtrado['latitud'].mean(), df_filtrado['longitud'].mean()]
    mapa_bogota = folium.Map(location=map_center, zoom_start=12, tiles="cartodbpositron")

    # --- NUEVO: Lógica condicional para dibujar la capa GeoJSON ---
    """
    if mostrar_geojson:
        gj = folium.GeoJson(
            geojson_localidades,
            name="Límites Localidades",
            style_function=lambda feature: {
                'fillColor': '#00000000',  # transparente real
                'color': '#007bff',        # azul
                'weight': 2,
                'dashArray': '5, 5'
            }
        ).add_to(mapa_bogota)

        # Solo si existe gj se ajusta el zoom
        mapa_bogota.fit_bounds(gj.get_bounds())

    """
    

    
    points = list(zip(df_filtrado['latitud'], df_filtrado['longitud']))
    if points:
        if map_type == 'heatmap': HeatMap(points, radius=15).add_to(mapa_bogota)
        elif map_type == 'cluster': 
            FastMarkerCluster(points).add_to(mapa_bogota)
    map_html = mapa_bogota._repr_html_()

    def crear_figura_vacia(titulo):
        fig = go.Figure()
        fig.update_layout(title_text=titulo, xaxis={'visible': False}, yaxis={'visible': False}, annotations=[{'text': 'No hay datos para esta selección', 'xref': 'paper', 'yref': 'paper', 'showarrow': False, 'font': {'size': 16}}])
        return fig

    if df_filtrado.empty:
        fig_infracciones, fig_vehiculos, fig_servicio, fig_localidades, fig_distribucion_hora, fig_distribucion_dia = [crear_figura_vacia(t) for t in ["Top 5 Infracciones", "Top 5 Vehículos", "Top 5 Servicio", "Top 5 Localidades", "Distribución Horaria", "Distribución por Día"]]
    else:
        top_5_infracciones = df_filtrado['INFRACCION'].value_counts().nlargest(5)
        fig_infracciones = px.bar(top_5_infracciones, x=top_5_infracciones.index, y=top_5_infracciones.values, title="Top 5 Infracciones", labels={'x': 'Código', 'y': 'Cantidad'})
        
        top_5_vehiculos = df_filtrado['CLASE_VEHICULO'].value_counts().nlargest(5)
        fig_vehiculos = px.bar(top_5_vehiculos, y=top_5_vehiculos.index, x=top_5_vehiculos.values, orientation='h', title="Top 5 Clases de Vehículo", labels={'y': 'Clase', 'x': 'Cantidad'})
        fig_vehiculos.update_layout(yaxis={'categoryorder':'total ascending'})

        top_5_servicio = df_filtrado['tipo_servicio'].value_counts().nlargest(5)
        fig_servicio = px.bar(top_5_servicio, x=top_5_servicio.index, y=top_5_servicio.values, title="Top 5 Tipos de Servicio", labels={'x': 'Tipo de Servicio', 'y': 'Cantidad'})

        top_5_localidades = df_filtrado['LOCALIDAD'].value_counts().nlargest(5)
        fig_localidades = px.bar(top_5_localidades, y=top_5_localidades.index, x=top_5_localidades.values, orientation='h', title="Top 5 Localidades con más Comparendos", labels={'y': 'Localidad', 'x': 'Cantidad'})
        fig_localidades.update_layout(yaxis={'categoryorder':'total ascending'})
        
        df_tiempo = df_filtrado.copy()
        df_tiempo['datetime_ocurrencia'] = df_tiempo['hora_ocurrencia'].apply(lambda t: datetime.datetime.combine(datetime.date.today(), t))
        df_tiempo['intervalo_tiempo'] = df_tiempo['datetime_ocurrencia'].dt.floor('30T').dt.time
        distribucion_hora = df_tiempo['intervalo_tiempo'].value_counts().sort_index()
        fig_distribucion_hora = px.bar(x=distribucion_hora.index.astype(str), y=distribucion_hora.values, title="Distribución por Hora de Ocurrencia", labels={'x': 'Intervalo de 30 min', 'y': 'Cantidad'})

        distribucion_dia = df_filtrado.groupby(['dia_semana_num', 'dia_semana_nombre']).size().reset_index(name='conteo').sort_values('dia_semana_num')
        fig_distribucion_dia = px.bar(distribucion_dia, x='dia_semana_nombre', y='conteo', title="Comparendos por Día de la Semana", labels={'dia_semana_nombre': 'Día de la Semana', 'conteo': 'Cantidad'})

    return texto_contador, map_html, fig_infracciones, fig_vehiculos, fig_servicio, fig_localidades, fig_distribucion_hora, fig_distribucion_dia