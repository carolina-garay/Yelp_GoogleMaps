import streamlit as st
import pandas as pd
import folium
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from google.cloud import bigquery
from google.oauth2 import service_account
from streamlit_folium import st_folium
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import openai
import time

# Mostrar el dashboard de Power BI
def mostrar_dashboard():
    st.title("Dashboard de Power BI")
    powerbi_url = "https://app.powerbi.com/view?r=eyJrIjoiZjI3NGVjZTgtZGE1Mi00NjgxLTgxYzItNTFiMzVmNjkxZmJhIiwidCI6IjZmM2UzMDQ4LTE0OWYtNGRiYy1hNjA2LTMyNWM4YjZjNjJjZiIsImMiOjR9"
    st.components.v1.iframe(src=powerbi_url, width=900, height=600)

# Barra lateral de navegación
st.sidebar.title("Navegación")
pagina = st.sidebar.selectbox("Seleccione una página", ["Dashboard de Power BI", "Sistema de Recomendación de Negocios"])



# Cargar la clave de la API de OpenAI desde secrets
#openai.api_key = st.secrets["openai"]["OPENAI_API_KEY"]

# Cargar credenciales y datos de BigQuery
@st.cache_data(show_spinner=False)
def cargar_datos_bigquery():
    # Cargar credenciales de Google Cloud desde secrets
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["google_cloud_credentials"])

    # Crear cliente de BigQuery usando las credenciales cargadas
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)

    query = """
        SELECT *
        FROM `data-avatar-435301-p6.Yelp.review_mach_learn_table`
    """
    df = client.query(query).to_dataframe()
    return df

# Optimización: Cargar los datos solo una vez
df = cargar_datos_bigquery()

# Definir los límites de latitud y longitud para cada estado
state_filters = {
    'CA': (34.0, 34.6, -120.0, -119.0),  # California
    'FL': (27.0, 29.0, -83.0, -82.0),    # Florida
    'IL': (38.0, 39.5, -91.0, -89.0),    # Illinois
    'NY': (38.5, 41.0, -76.0, -74.0)     # New York
    }

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
        st.write(f"Estado '{estado_cliente}' no reconocido.")
        return pd.DataFrame()  # Retornar DataFrame vacío si el estado no se reconoce

# Función para mostrar progreso
def mostrar_progreso(mensaje):
    with st.spinner(mensaje):
        time.sleep(1)


# Función para inicializar el analizador de sentimiento
sia = SentimentIntensityAnalyzer()


# Mostrar la interfaz de usuario
def mostrar_recomendacion():
    # Título de la aplicación en Streamlit
    st.markdown("""
    <style>
    .centered-title {
        text-align: center;
        font-family: 'Arial', sans-serif;
        font-size: 48px;
        color: #333333;
    }
    </style>
    <h1 class="centered-title">Sistema de Recomendación de Negocios</h1>
    """, unsafe_allow_html=True)

# Agregar imagen debajo del título
    st.image("kitchen_henry.png", width=200)
    st.write("Seleccione el estado y la categoría para obtener recomendaciones basadas en las reseñas de usuarios.")

    # Pedir al cliente que ingrese el estado y la categoría
    estado_cliente = st.selectbox("Seleccione el estado", ['CA', 'FL', 'IL', 'NY'], key="estado_recomendacion")
    categoria_cliente = st.text_input("Ingrese la categoría que desea buscar", key="categoria_recomendacion")

    if st.button('Buscar negocios', key="buscar_recomendacion"):
        mostrar_progreso("Cargando datos...")

        
        # Filtrar los datos por estado
        df_filtrado_estado = filtrar_por_estado(df, estado_cliente)

        if 'category' in df_filtrado_estado.columns:
            df_filtrado = df_filtrado_estado[df_filtrado_estado['category'].str.contains(categoria_cliente, case=False, na=False)]

            if df_filtrado.empty:
                st.write(f"No se encontraron negocios en {estado_cliente} para la categoría '{categoria_cliente}'")
            else:
                # Calcular el análisis de sentimiento
                df_filtrado['sentiment_score'] = df_filtrado['text'].apply(lambda x: sia.polarity_scores(x)['compound'])

                # Seleccionar los 5 mejores y 5 peores negocios
                df_pos = df_filtrado.nlargest(5, 'sentiment_score')
                df_neg = df_filtrado.nsmallest(5, 'sentiment_score')

                # Crear un mapa centrado en la ubicación promedio de los mejores negocios
                mapa = folium.Map(location=[df_pos['latitude'].mean(), df_pos['longitude'].mean()], zoom_start=12)

                # Añadir marcadores de los mejores negocios (en verde)
                for _, row in df_pos.iterrows():
                    folium.Marker(
                        [row['latitude'], row['longitude']],
                        popup=f"{row['name']} - {row['stars']} estrellas",
                        icon=folium.Icon(color='green')
                    ).add_to(mapa)

                # Añadir marcadores de los peores negocios (en rojo)
                for _, row in df_neg.iterrows():
                    folium.Marker(
                        [row['latitude'], row['longitude']],
                        popup=f"{row['name']} - {row['stars']} estrellas",
                        icon=folium.Icon(color='red')
                    ).add_to(mapa)

                # Añadir círculos azules con un radio de 500 metros alrededor de los 3 peores negocios
                for _, row in df_neg.head(5).iterrows():
                    folium.Circle(
                        location=[row['latitude'], row['longitude']],
                        radius=500,  # Radio en metros
                        color='blue',
                        fill=True,
                        fill_color='blue',
                        fill_opacity=0.1,
                    ).add_to(mapa)

                # Mostrar el mapa en Streamlit
                st_folium(mapa, width=700, height=500)

                # Mostrar las tablas de los mejores y peores negocios
                st.write("Mejores negocios:")
                st.write(df_pos[['name', 'sentiment_score', 'stars', 'latitude', 'longitude', 'state']])

                st.write("Peores negocios:")
                st.write(df_neg[['name', 'sentiment_score', 'stars', 'latitude', 'longitude', 'state']])

                # Generar nubes de palabras para los comentarios
                mejores_tips = ' '.join(df_pos['text'].dropna())
                peores_tips = ' '.join(df_neg['text'].dropna())

                # Mostrar nubes de palabras para sugerencias positivas y negativas
                st.write("Wordcloud positivas:")
                wordcloud_positivas = generar_nube_palabras(mejores_tips, "Greens")
                plt.figure(figsize=(10, 5))
                plt.imshow(wordcloud_positivas, interpolation="bilinear")
                plt.axis("off")
                st.pyplot(plt)

                st.write("Wordcloud negativas:")
                wordcloud_negativas = generar_nube_palabras(peores_tips, "Reds")
                plt.figure(figsize=(10, 5))
                plt.imshow(wordcloud_negativas, interpolation="bilinear")
                plt.axis("off")
                st.pyplot(plt)

                # Enviar las sugerencias de los usuarios a GPT-4 para generar recomendaciones
                prompt = f"""
                Sugerencias de los usuarios:
                Mejores negocios:
                {mejores_tips}

                Peores negocios:
                {peores_tips}

                Basado en estas sugerencias, por favor recomienda un plan de acción de 3 ítems bien resumidos para mejorar o implementar un nuevo negocio.
                """

                # Llamar a OpenAI GPT-4 para generar recomendaciones
                try:
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": "Eres un experto en negocios y marketing."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=3200  # Limitar la respuesta para que no sea demasiado larga
                    )

                    # Mostrar las recomendaciones generadas por GPT-4
                    st.write("Plan de acción recomendado para el nuevo negocio:")
                    st.write(response['choices'][0]['message']['content'])

                except openai.error.RateLimitError:
                    st.error("Error: Se ha superado el límite de solicitudes a la API de OpenAI.")

                except openai.error.InvalidRequestError as e:
                    st.error(f"Error en la solicitud: {str(e)}")

                except Exception as e:
                    st.error(f"Ocurrió un error inesperado: {str(e)}")

# Renderizar la página seleccionada
if pagina == "Dashboard de Power BI":
    mostrar_dashboard()

elif pagina == "Sistema de Recomendación de Negocios":
    mostrar_recomendacion()
