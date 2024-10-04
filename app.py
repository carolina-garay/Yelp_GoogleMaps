import streamlit as st
import pandas as pd
import folium
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_folium import folium_static
import openai
import time

# Mostrar el dashboard de Power BI
def mostrar_dashboard():
    st.title("Dashboard de Power BI")
    powerbi_url = "https://app.powerbi.com/view?r=eyJrIjoiZjI3NGVjZTgtZGE1Mi00NjgxLTgxYzItNTFiMzVmNjkxZmJhIiwidCI6IjZmM2UzMDQ4LTE0OWYtNGRiYy1hNjA2LTMyNWM4YjZjNjJjZiIsImMiOjR9"
    st.components.v1.iframe(src=powerbi_url, width=900, height=600)

# Barra lateral de navegación
st.sidebar.title("Navegación")
pagina = st.sidebar.selectbox("Selecciona una página", ["Recomendación de Negocios", "Dashboard de Power BI"])




# Cargar credenciales de Google Cloud desde secrets
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google_cloud_credentials"]
)

# Cargar la clave de la API de OpenAI desde secrets
openai.api_key = st.secrets["openai"]["OPENAI_API_KEY"]

# Crear cliente de BigQuery usando las credenciales cargadas
client = bigquery.Client(credentials=credentials, project=credentials.project_id)

# Definir los límites de latitud y longitud para cada estado
state_filters = {
    'CA': (34.0, 34.6, -120.0, -119.0),  # California
    'FL': (27.0, 29.0, -83.0, -82.0),    # Florida
    'IL': (38.0, 39.5, -91.0, -89.0),    # Illinois
    'NY': (38.5, 41.0, -76.0, -74.0)     # New York
}

# Cargar los datos desde BigQuery con caché
@st.cache_data(show_spinner=False)
def cargar_datos_bigquery():
    query = """
        SELECT *
        FROM `data-avatar-435301-p6.Yelp.review_mach_learn_table`
    """
    df = client.query(query).to_dataframe()
    return df

# Función para filtrar por estado
def filtrar_por_estado(df, estado_cliente):
    if estado_cliente in state_filters:
        lat_min, lat_max, long_min, long_max = state_filters[estado_cliente]
        df_filtrado = df[
            (df['latitude'].between(lat_min, lat_max)) & 
            (df['longitude'].between(long_min, long_max)) & 
            (df['state'] == estado_cliente)
        ]
        return df_filtrado.dropna(subset=['latitude', 'longitude'])  # Asegurarse de que no haya valores nulos
    else:
        return pd.DataFrame()

# Función para mostrar el progreso
def mostrar_progreso(mensaje):
    with st.spinner(mensaje):
        time.sleep(1)

# Función para generar propuestas con OpenAI
def generar_propuesta_nuevo_negocio(caracteristicas):
    prompt = f"""
    Las características de los mejores negocios son:
    {caracteristicas}

    Basado en estas sugerencias, por favor recomienda un plan de acción de 3 ítems para mejorar o implementar un nuevo negocio.
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en negocios y marketing."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300  # Limitar la respuesta para que no sea demasiado larga
        )
        return response['choices'][0]['message']['content']
    except openai.error.RateLimitError:
        return "Se ha superado el límite de solicitudes a la API de OpenAI."
    except Exception as e:
        return f"Error al generar propuesta: {str(e)}"

# Mostrar la interfaz de usuario
def mostrar_recomendacion():
    st.title('Sistema de Recomendación de Negocios')
    st.write("Seleccione el estado y la categoría para obtener recomendaciones basadas en las reseñas de Yelp.")

    # Pedir al cliente que ingrese el estado y la categoría
    estado_cliente = st.selectbox("Seleccione el estado", ['CA', 'FL', 'IL', 'NY'], key="estado_recomendacion")
    categoria_cliente = st.text_input("Ingrese la categoría que desea buscar", key="categoria_recomendacion")

    if st.button('Buscar negocios', key="buscar_recomendacion"):
        mostrar_progreso("Cargando datos...")

        # Cargar datos desde BigQuery
        df = cargar_datos_bigquery()

        # Filtrar los datos por estado
        df_filtrado_estado = filtrar_por_estado(df, estado_cliente)

        if 'category' in df_filtrado_estado.columns:
            df_filtrado = df_filtrado_estado[df_filtrado_estado['category'].str.contains(categoria_cliente, case=False, na=False)]

            if df_filtrado.empty:
                st.write(f"No se encontraron negocios en {estado_cliente} para la categoría '{categoria_cliente}'")
            else:
                # Calcular el análisis de sentimiento
                sia = SentimentIntensityAnalyzer()
                df_filtrado['sentiment_score'] = df_filtrado['text'].apply(lambda x: sia.polarity_scores(x)['compound'])
                df_pos = df_filtrado.nlargest(5, 'sentiment_score')

                # Generar una propuesta para el nuevo negocio
                mejores_tips = df_pos['text_tip'].dropna().tolist()
                mejores_caracteristicas = ' '.join(mejores_tips)
                propuesta_nuevo_negocio = generar_propuesta_nuevo_negocio(mejores_caracteristicas)

                # Mostrar la propuesta
                st.write("Propuesta generada para el nuevo negocio:")
                st.write(propuesta_nuevo_negocio)

                # Crear y mostrar el mapa con los negocios
                mapa = folium.Map(location=[df_pos['latitude'].mean(), df_pos['longitude'].mean()], zoom_start=12)
                for _, row in df_pos.iterrows():
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=f"{row['name']} - Sentimiento: {row['sentiment_score']}",
                        icon=folium.Icon(color='green')
                    ).add_to(mapa)
                folium_static(mapa)

        else:
            st.write("La columna 'category' no está disponible en los datos filtrados.")

# Renderizar la página seleccionada
if pagina == "Dashboard de Power BI":
    mostrar_dashboard()

elif pagina == "Recomendación de Negocios":
    mostrar_recomendacion()
