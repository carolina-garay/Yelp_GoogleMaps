# <h1 align="center">**`YELP & GOOGLE MAPS - REVIEWS AND RECOMMENDATIONS 🍽️`**</h1> 

Este proyecto tiene como objetivo crear un sistema de recomendación de restaurantes basado en las reseñas de los usuarios, utilizando técnicas de Machine Learning y visualización de datos.

##  `Etapa de Analytics y Machine Learning`  🧠📊

## 📊 `Análisis de Datos y KPIs`:
- 🚀 **Power BI** se utilizó para generar Dashboards que presenten el análisis de datos, métricas clave y KPIs.


## `Modelo de Machine Learning` 🤖

El sistema de recomendación de restaurantes se creó utilizando una combinación de técnicas de Machine Learning y análisis de sentimientos para ofrecer recomendaciones personalizadas. A continuación, se detallan los principales componentes del modelo:



### 🔍 `Descripción de los Componentes`:

1. **Filtrado de Negocios por Estado y Categoría**:
   - Utilizamos un filtro para seleccionar negocios según el estado y la categoría de interés del usuario, basándonos en los límites de latitud y longitud de los estados: California, Florida, Illinois y Nueva York.
   - Esto permite que el sistema se centre en los negocios relevantes para el usuario y el área geográfica seleccionada.

2. **Generación de Nuevas Ubicaciones**:
   - Implementamos una función que genera nuevas ubicaciones dentro de un radio de 500 metros, lo cual es útil para identificar posibles lugares donde abrir nuevos negocios, basados en la evaluación de los peores negocios actuales en la zona.
   - Se utiliza un algoritmo aleatorio para desplazar ligeramente las coordenadas geográficas, simulando la búsqueda de nuevas ubicaciones potenciales.

3. **Análisis de Sentimientos**:
   - A través de **VADER Sentiment Analysis**, calculamos una puntuación de sentimiento para cada reseña textual. Esta puntuación indica si las reseñas son predominantemente positivas, negativas o neutrales.
   - Los negocios se clasifican en "mejores" (con un sentimiento positivo) y "peores" (con un sentimiento negativo).

4. **Mapas Interactivos**:
   - Los mejores y peores negocios, basados en el análisis de sentimientos, se muestran en un mapa interactivo utilizando **folium**. Los negocios más recomendados se marcan en verde, mientras que los negocios menos recomendados se marcan en rojo.
   - También se proponen nuevas ubicaciones para abrir negocios, marcadas en azul, basándose en la ubicación de los negocios menos exitosos.

5. **Vectorización de Características de Reseñas**:
   - Utilizamos **TfidfVectorizer** para extraer las características más relevantes de las reseñas positivas de los mejores negocios. Estas características pueden ser utilizadas para definir la propuesta de valor de un nuevo negocio en el área.
   - El vectorizador selecciona las 10 palabras más relevantes de los tips asociados a los mejores negocios, lo que proporciona una idea de las características clave que los clientes valoran.

### 🚀 Despliegue del Sistema de Recomendación:
- 🌐 **Despliegue del Sistema**: El sistema de recomendación de restaurantes fue desplegado a través de **Streamlit**, proporcionando una interfaz interactiva y accesible para los usuarios finales.

## `Herramientas Utilizadas` 🛠️
- **Power BI**: Para visualización de datos y análisis de KPIs.
- **Python**: Para el procesamiento de datos y construcción de los modelos de Machine Learning.
- **Streamlit**: Para la implementación y despliegue del sistema de recomendación.
- **Scikit-Learn**: Para implementar el modelo KNN con similitud del coseno.

## `Objetivos` 📈
- Aumentar el **crecimiento de nuevas reseñas** en un 20% en categorías con alta demanda.
- Disminuir el **Índice de Oportunidades de Mejora (IOM)** en 0.05 puntos mensuales.
- Aumentar la **densidad de opiniones favorables** en un 30% en áreas clave.
- Mejorar el **rating promedio** en un 10% en un plazo de 6 meses.


---

Gracias por visitar este proyecto. ¡Esperamos que disfrutes de las recomendaciones de restaurantes! 😄🍴
