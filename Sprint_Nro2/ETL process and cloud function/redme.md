# Descripción de Archivos

A continuación, se describen los archivos incluidos en esta carpeta y su propósito dentro del proyecto:

1. **Actualizar_la_carga_inicial**  
   Este archivo contiene un script utilizado para actualizar la carga inicial de datos en Google Cloud Storage. Se encarga de procesar y cargar datos previamente almacenados de forma manual o automática en los buckets de datos, garantizando que toda la información necesaria esté correctamente estructurada y lista para su análisis.

2. **cloudfunction**  
   Este archivo corresponde a una función en la nube (Cloud Function) diseñada para automatizar la transformación y carga de nuevos datos. Cada vez que un nuevo archivo es subido a un bucket designado, esta función se activa automáticamente, limpia el archivo y lo concatena con los datos existentes. De esta manera, aseguramos que los datos estén siempre actualizados sin intervención manual.

3. **TRATAMIENTO_DE_DATOS_GOOGLE**  
   En este archivo se definen las transformaciones necesarias para procesar y estructurar los datos obtenidos desde Google (por ejemplo, Google Maps y Google Reviews). El objetivo principal es validar y preparar los datos crudos para su análisis o almacenamiento en bases de datos como BigQuery, permitiendo un acceso eficiente a grandes volúmenes de información.

