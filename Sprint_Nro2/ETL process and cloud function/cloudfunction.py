from google.cloud import storage
from google.cloud import bigquery
import functions_framework
import pandas as pd
import time
import ast
import warnings
import re
import os
from datetime import datetime

warnings.simplefilter(action='ignore', category=FutureWarning)

@functions_framework.cloud_event
def process_file(cloud_event):
    try:
        event_data = cloud_event.data
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        
        if not bucket_name or not file_name:
            print("Bucket name or file name is missing from the event data.")
            return

        gcs_uri = f'gs://{bucket_name}/{file_name}'
        print(f"Procesando el archivo {file_name} desde el bucket {bucket_name}")

        new_data = get_read_parquet(gcs_uri)

        if new_data is not None:
            detect_and_process(new_data, file_name)
        else:
            print(f"Error al leer el archivo {file_name}.")
    except Exception as e:
        print(f"Error en process_file: {str(e)}")

def detect_and_process(df, file_name):
    try:
        metadatos_columns = {"name", "address", "gmap_id", "description", "latitude", "longitude", 
                             "category", "avg_rating", "num_of_reviews", "price", "hours", 
                             "MISC", "state", "relative_results", "url"}
        reviews_columns = {"user_id", "name", "time", "rating", "text", "pics", "resp", "gmap_id"}
        business_columns = {'business_id', 'name', 'address', 'city', 'state', 'postal_code',
                            'latitude', 'longitude', 'stars', 'review_count', 'is_open',
                             'category', 'hours'}
                             
                             

        if business_columns.issubset(df.columns):
            print("Archivo de business detectado. Aplicando transformaciones de business...")
            process_business(df, file_name)
        elif reviews_columns.issubset(df.columns):
            print("Archivo de reseñas detectado. Aplicando transformaciones de reseñas...")
            process_reviews(df, file_name)
        elif metadatos_columns.issubset(df.columns):
            print("Archivo de metadatos detectado. Aplicando transformaciones de metadatos...")
            process_metadata(df, file_name)    
        else:
            print(f"Estructura del archivo {file_name} no coincidente.")
    except Exception as e:
        print(f"Error en detect_and_process: {str(e)}")

def get_read_parquet(file_path):
    try:
        storage_client = storage.Client()
        bucket_name = re.search(r'gs://(.+?)/', file_path).group(1)
        file_name = file_path.split('/')[-1]
        bucket = storage_client.get_bucket(bucket_name)
        blob = bucket.blob(file_name)

        with blob.open("rb") as f:
            df = pd.read_parquet(f)
            print(f"Archivo {file_name} leído exitosamente")
            return df
    except Exception as e:
        print(f"Error leyendo el archivo {file_name}: {str(e)}")
        return None

def load_to_bigquery(gcs_uri, dataset_id, table_id):
    try:
        client = bigquery.Client()
        table_ref = client.dataset(dataset_id).table(table_id)

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND
        )

        load_job = client.load_table_from_uri(gcs_uri, table_ref, job_config=job_config)
        load_job.result()

        print(f"Datos cargados exitosamente a {dataset_id}.{table_id}")
    except Exception as e:
        print(f"Error cargando datos a BigQuery: {str(e)}")

def add_version_and_timestamp(df, current_version):
    df.loc[:, 'version'] = current_version
    df.loc[:, 'fecha_ingreso'] = datetime.now()

    return df

def process_business(businesscruda, file_name):
    try:
        # Leer el dataset de business existentes en el bucket de datos limpios
        existing_business = get_read_parquet('gs://g1_datos_limpios/business.parquet')

        if existing_business is not None:
            # Identificar los business_id que ya existen en los datos limpios
            existing_bus_ids = set(existing_business['business_id'].unique())                        
            
            # Filtrar los nuevos registros que NO están en los business ya existentes
            businesscruda['business_id'] = businesscruda['business_id'].astype(str)
            new_business = businesscruda[~businesscruda['business_id'].isin(existing_bus_ids)]
    
            # Aplicar filtros geográficos y de categorías aquí...
            # Definir los límites de latitud y longitud para cada estado
            state_filters = {
            'CA': (34.0, 34.6, -120.0, -119.0),  # California
            'FL': (27.0, 29.0, -83.0, -82.0),   # Florida
            'IL': (36.9, 42.5, -91.5, -87.0),   # Illinois
            'NY': (40.5, 45, -79.8, -71.8)      # New York
                             }

            # Aplicar filtro geográfico por estados y asignar la abreviatura del estado
            for state, (lat_min, lat_max, long_min, long_max) in state_filters.items():
                new_business.loc[
                    (new_business['latitude'].between(lat_min, lat_max)) &
                    (new_business['longitude'].between(long_min, long_max)),
                    'state'] = state

            # Filtrar por categorías de interés
            categories = ['restaurant', 'coffee', 'ice cream', 'cocktail bars', 'wine bars',
                      'sushi bars', 'tea', 'bakery', 'food', 'diner', 'tortilla',
                      'vegetarian', 'tofu', 'pie', 'soup', 'salad', 'cake', 'donut',
                      'sandwiches', 'pizza', 'burger', 'hot dog', 'breakfast & brunch', 'restaurants', 'barbecue']
            categories_regex = '|'.join(categories)
            new_business = new_business[new_business['category'].str.contains(categories_regex, case=False, na=False)]
            
            # Definir la versión actual para los datos nuevos
            current_version = existing_business['version'].max() + 1 if 'version' in existing_business.columns else 1
            new_business = add_version_and_timestamp(new_business, current_version)
                    
            # Definir las columnas esperadas según el esquema de BigQuery
            expected_columns = ['business_id', 'name', 'address', 'city', 'state', 'postal_code',
             'latitude', 'longitude', 'stars', 'review_count', 'is_open', 'category',
                    'hours']

            # Filtrar el DataFrame para que solo contenga las columnas esperadas
            new_business = new_business[expected_columns]
            
            
            # Guardar los datos transformados en GCS y cargarlos en BigQuery
            save_to_bucket(new_business, 'g1_carga_incremental', 'business_incremental.parquet')
            gcs_uri = f'gs://g1_carga_incremental/business_incremental.parquet'
            load_to_bigquery(gcs_uri, 'Tablas_Yelp_Google', 'business_yelp_table')

            # Concatenar los nuevos datos con los existentes y guardar el resultado combinado en datos limpios
            if not new_business.empty:
                concatenated_business = pd.concat([existing_business, new_business], ignore_index=True)
                save_to_bucket(concatenated_business, 'g1_datos_limpios', 'business.parquet')
                print("business concatenados y actualizados correctamente en data limpia.")
            
        
            #################################################################################################        
            # Procesar categorías
            print("Aplicando transformaciones a categories...")

            # Paso 1: Expandir y contar las categorías únicas
            flat_categories_list = concatenated_business['category'].str.split(', ').explode()
            category_counts = flat_categories_list.value_counts()

            # Paso 2: Filtrar categorías que aparecen suficientemente a menudo (umbral 500)
            frequent_categories = category_counts[category_counts >= 500]

            # Paso 3: Crear un DataFrame de categorías frecuentes con un ID único para cada una
            df_categories = pd.DataFrame({
                'category_id': range(1, len(frequent_categories) + 1),
                'category': frequent_categories.index})
            # Realizar una copia de df_categories
            df_categories2 = df_categories.copy()    

            # Paso 4: Crear una tabla vinculada entre 'business_id' y 'category_id'
            dataframes_list = []
            for index, row in concatenated_business.iterrows():
                business_id = row['business_id']
                categories = row['category'].split(', ')

                # Vinculando cada categoría con el business_id correspondiente
                for category in categories:
                    if category in frequent_categories.index:
                        category_id = df_categories.loc[df_categories['category'] == category, 'category_id'].values[0]
                        dataframes_list.append(pd.DataFrame({
                            'business_id': [business_id],
                            'category_id': [category_id]
                        }))

            # Concatenar todos los DataFrames para crear una tabla vinculada
            df_business_categories = pd.concat(dataframes_list, ignore_index=True)
            
            
            # Eliminar duplicados si existen
            df_business_categories.drop_duplicates(inplace=True)
            df_business_categories2=df_business_categories.copy()
            

            # Guardar los registros  df_business_categories como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(df_business_categories2, 'g1_carga_incremental', 'business_categories_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/business_categories_incremental.parquet', 'Tablas_Yelp_Google', 'business_categories_yelp_table')
            
            # Guardar los registros df_categories como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(df_categories2, 'g1_carga_incremental', 'categories_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/categories_incremental.parquet', 'Tablas_Yelp_Google', 'categories_yelp_table')
            
            
            # Guardar los registros como archivo Parquet para data limpia
            save_to_bucket(df_business_categories, 'g1_datos_limpios', 'business_categories.parquet')
            # Guardar los registros df_categories como archivo Parquet para data limpia
            save_to_bucket(df_categories2, 'g1_datos_limpios', 'categories.parquet')
            print("df_categories guardados en data limpia") 
             

            print("Categorías procesadas y guardadas correctamente en data limpia y carga incremental.")
            #################################################################################################
            # Procesar 'hours'
            print("Aplicando transformaciones a hours...")

            # Paso 1: Convertir la columna 'hours' de string a diccionario
            def parse_hours(x):
                try:
                    # Convertir de bytes si es necesario y evaluar la cadena para convertirla en diccionario
                    if isinstance(x, bytes):
                        x = x.decode('utf-8')
                    x = x.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                    return ast.literal_eval(x)
                except:
                    return {}

            concatenated_business['hours_dict'] = concatenated_business['hours'].apply(parse_hours)

            # Paso 2: Crear un nuevo DataFrame 'df_hours' con los días de la semana como columnas
            df_hours = concatenated_business[['business_id']].copy()

            # Los días de la semana para asegurar que todas las columnas estén presentes incluso si falta algún día en los datos
            days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

            # Expandir los diccionarios de horas en columnas separadas para cada día
            for day in days_of_week:
                df_hours[day] = concatenated_business['hours_dict'].apply(lambda x: x.get(day, ''))

            # Guardar los registros nuevos de hours como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(df_hours, 'g1_carga_incremental', 'hours_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/hours_incremental.parquet', 'Tablas_Yelp_Google', 'hours_yelp_table')

            # Guardar los registros como archivo Parquet para data limpia
            save_to_bucket(df_hours, 'g1_datos_limpios', 'hours.parquet')

            print("Horas procesadas y guardadas correctamente en data limpia y carga incremental.")
            
            #################################################################################################
            # Procesar reseñas
            print("Procesando reseñas...")
            
            # Extraer el archivo reviews
            review = get_read_parquet('gs://g1_datos_limpios/review.parquet')

            # Convertir la columna 'date' a tipo DateTime
            review['date'] = pd.to_datetime(review['date'])
            # Actualizar la columna 'date' para que solo contenga la fecha
            review['date'] = review['date'].dt.date
            # Fecha mínima con la que vamos a trabajar
            fecha_referencia = pd.to_datetime('2016-01-01').date()
            # Filtramos 'review' para obtener todas las fechas superiores a la de la referencia 
            review_filtrado = review[review['date'] > fecha_referencia]
            review_filtrado = review_filtrado.reindex()

            # Realizar el merge entre review_filtrado y concatenated_business por la columna 'business_id'
            review_final = pd.merge(review_filtrado, concatenated_business[['business_id', 'latitude', 'longitude','state','name', 'review_count', 'category']], 
                            on='business_id', how='inner')
            # Reasignar los índices y eliminar duplicados
            review_final = review_final.reindex()
            review_final.drop_duplicates(subset='business_id', inplace=True)
            
            # Guardar los registros de review como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(review_final, 'g1_carga_incremental', 'review_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/review_incremental.parquet', 'Tablas_Yelp_Google', 'review_filtrado_yelp_table')

            # Guardar los registros como archivo Parquet para data limpia
            save_to_bucket(review_final, 'g1_datos_limpios', 'review_filtrado.parquet') 
            
            #################################################################################################
            # Procesar tip
            print("Procesando tip...")
            
            # Extraer el archivo tip
            tip = get_read_parquet('gs://g1_datos_limpios/tip.parquet')
            
            # Eliminación de registros duplicados
            tip.drop_duplicates(inplace=True)
            # Filtrando tip
            tip_filtrado = tip[tip["business_id"].isin(concatenated_business["business_id"])]
            
            # Eliminar duplicados 
            tip_filtrado = tip_filtrado.drop_duplicates(subset=['user_id', 'business_id', 'date'])
            # Eliminar columnas que no se usarán
            tip_filtrado = tip_filtrado.drop(columns=['compliment_count'])
                        
            # Guardar los registros de tip como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(tip_filtrado, 'g1_carga_incremental', 'tip_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/tip_incremental.parquet', 'Tablas_Yelp_Google', 'tip_filtrado_yelp_table')
            print("Registros tip guardados en bigquery")

            # Guardar los registros como archivo Parquet para data limpia
            save_to_bucket(tip_filtrado, 'g1_datos_limpios', 'tip_filtrado.parquet') 
            
            #################################################################################################
            # Procesar review con tip para ML
            print("Procesando datos para Machine Learning...")
            # Cambiar nombre
            tip_filtrado.rename(columns={'text':'text_tip'}, inplace=True)
            # Realizar el merge entre review_final y tip_filtrado en la columna 'business_id'
            review_ml = pd.merge(review_final, tip_filtrado[['business_id', 'text_tip']], 
                     on='business_id', how='inner')
            # Eliminar duplicados
            review_ml.drop_duplicates(subset='business_id', inplace=True)
            
            # Guardar los registros de review_ml como archivo Parquet para ser enviados a BigQuery
            save_to_bucket(review_ml, 'g1_carga_incremental', 'review_ml_incremental.parquet')
            load_to_bigquery(f'gs://g1_carga_incremental/review_ml_incremental.parquet', 'Tablas_Yelp_Google', 'review_mach_learn_table')
            print("Registros review_ml guardados en bigquery")

            # Guardar los registros como archivo Parquet para data limpia
            save_to_bucket(review_ml, 'g1_datos_limpios', 'review_mach_learn.parquet')
            print("Registros review_ml guardados en data limpia") 
                                                                                                                       
        else:
            print("Error al leer los business existentes en datos limpios.")
    except Exception as e:
        print(f"Error en process_business: {str(e)}")

##########################fin process_business################


def process_metadata(metadatacruda, file_name):
    try:
        print("Aplicando transformaciones a metadatos...")
        existing_metadata = get_read_parquet('gs://g1_datos_limpios/metadata_filtrada_final.parquet')

        if existing_metadata is not None:
            existing_gmap_ids = set(existing_metadata['google_map_id'].unique())
            metadatacruda['gmap_id'] = metadatacruda['gmap_id'].astype(str)
            new_metadata = metadatacruda[~metadatacruda['gmap_id'].isin(existing_gmap_ids)]

            # Definir la versión actual para los datos nuevos
            current_version = existing_metadata['version'].max() + 1 if 'version' in existing_metadata.columns else 1
            new_metadata = add_version_and_timestamp(new_metadata, current_version)

            # Filtrar las categorías de interés
            categories = ['restaurant', 'coffee', 'ice cream', 'cocktail bars', 'wine bars', 
                          'sushi bars', 'tea', 'bakery', 'food', 'diner', 'tortilla', 'vegetarian', 
                          'tofu', 'pie', 'soup', 'salad', 'cake', 'donut', 'sandwiches', 'pizza', 
                          'burger', 'hot dog', 'breakfast & brunch', 'restaurants', 'barbecue']

            # Convertir 'category' de string a lista si es necesario y filtrar por las categorías
            new_metadata['category'] = new_metadata['category'].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)
            new_metadata = new_metadata[new_metadata['category'].notnull()]
            new_metadata = new_metadata[new_metadata['category'].apply(lambda cat_list: any(category.lower() in [cat.lower() for cat in cat_list] for category in categories))]

            # Eliminar duplicados y valores nulos en columnas importantes
            new_metadata.drop_duplicates(subset=[col for col in new_metadata.columns if col != 'category'], inplace=True)
            new_metadata.dropna(subset=['category', 'latitude', 'longitude'], inplace=True)
            new_metadata['avg_rating'].fillna(new_metadata['avg_rating'].mean(), inplace=True)

            # Ajustar los nombres de columnas para que coincidan con el esquema de BigQuery
            new_metadata.columns = new_metadata.columns.str.lower().str.replace(' ', '_')
            new_metadata.rename(columns={'gmap_id': 'google_map_id', 'avg_rating': 'average_rating'}, inplace=True)

            # Asegurarse de que los tipos de datos coincidan con el esquema de BigQuery
            new_metadata['name'] = new_metadata['name'].astype(str)
            new_metadata['address'] = new_metadata['address'].astype(str)
            new_metadata['google_map_id'] = new_metadata['google_map_id'].astype(str)
            new_metadata['latitude'] = new_metadata['latitude'].astype(float)
            new_metadata['longitude'] = new_metadata['longitude'].astype(float)
            new_metadata['average_rating'] = new_metadata['average_rating'].astype(float)
            new_metadata['num_of_reviews'] = new_metadata['num_of_reviews'].astype(int)
            new_metadata['version'] = new_metadata['version'].astype(int)
            new_metadata['fecha_ingreso'] = pd.to_datetime(new_metadata['fecha_ingreso'])

            # Convertir 'category' en una cadena de texto separada por comas
            new_metadata['category'] = new_metadata['category'].apply(lambda x: ', '.join(x) if isinstance(x, list) else str(x))

            if 'description' in new_metadata.columns:
                new_metadata = new_metadata.drop(columns=['description'])

            # Definir las columnas esperadas según el esquema de BigQuery
            expected_columns = [
                'name', 'address', 'google_map_id', 'latitude', 'longitude', 
                'category', 'average_rating', 'num_of_reviews', 'version', 'fecha_ingreso'
            ]

            # Filtrar el DataFrame para que solo contenga las columnas esperadas
            new_metadata = new_metadata[expected_columns]

            # Guardar los datos transformados en GCS y cargarlos en BigQuery
            save_to_bucket(new_metadata, 'g1_carga_incremental', 'metadata_incremental.parquet')
            gcs_uri = f'gs://g1_carga_incremental/metadata_incremental.parquet'
            load_to_bigquery(gcs_uri, 'Tablas_Yelp_Google', 'metadata_table')

            # Concatenar los nuevos datos con los existentes y guardar el resultado combinado
            if not new_metadata.empty:
                concatenated_metadata = pd.concat([existing_metadata, new_metadata], ignore_index=True)
                save_to_bucket(concatenated_metadata, 'g1_datos_limpios', 'metadata_filtrada_final.parquet')
                print("Metadatos concatenados y actualizados correctamente en data limpia.")
            else:
                print("No hay nuevos metadatos para agregar.")
        else:
            print("Error al leer los metadatos existentes en datos limpios.")
    except Exception as e:
        print(f"Error en process_metadata: {str(e)}")


def process_reviews(reviews, file_name):
    try:
        print("Aplicando transformaciones a reseñas...")
        existing_metadata = get_read_parquet('gs://g1_datos_limpios/metadata_filtrada_final.parquet')

        if existing_metadata is not None:
            existing_gmap_ids = set(existing_metadata['google_map_id'].unique())
            reviews['gmap_id'] = reviews['gmap_id'].astype(str)
            valid_reviews = reviews[(reviews['gmap_id'].isin(existing_gmap_ids)) & (pd.to_datetime(reviews['time'], unit='ms') >= '2016-01-01')]

            new_negocios_con_texto = valid_reviews[valid_reviews['text'].notnull()]
            new_negocios_sin_texto = valid_reviews[valid_reviews['text'].isnull()]

            existing_reviews_con_texto = get_read_parquet('gs://g1_datos_limpios/reviews_negocios_con_texto_filtrados.parquet')
            existing_reviews_sin_texto = get_read_parquet('gs://g1_datos_limpios/reviews_negocios_sin_texto_filtrados.parquet')

            current_version = 1
            if existing_reviews_con_texto is not None and 'version' in existing_reviews_con_texto.columns:
                current_version = max(existing_reviews_con_texto['version'].max(), current_version)
            if existing_reviews_sin_texto is not None and 'version' in existing_reviews_sin_texto.columns:
                current_version = max(existing_reviews_sin_texto['version'].max(), current_version)
            current_version += 1

            new_negocios_con_texto = add_version_and_timestamp(new_negocios_con_texto, current_version)
            new_negocios_sin_texto = add_version_and_timestamp(new_negocios_sin_texto, current_version)

            save_to_bucket(new_negocios_con_texto, 'g1_carga_incremental', 'new_negocios_con_texto_incremental.parquet')
            save_to_bucket(new_negocios_sin_texto, 'g1_carga_incremental', 'new_negocios_sin_texto_incremental.parquet')

            load_to_bigquery(f'gs://g1_carga_incremental/new_negocios_con_texto_incremental.parquet', 'Tablas_Yelp_Google', 'reviews_with_text_table')
            load_to_bigquery(f'gs://g1_carga_incremental/new_negocios_sin_texto_incremental.parquet', 'Tablas_Yelp_Google', 'reviews_without_text_table')

            if not valid_reviews.empty:
                negocios_con_texto = pd.concat([existing_reviews_con_texto, new_negocios_con_texto], ignore_index=True) if existing_reviews_con_texto is not None else new_negocios_con_texto
                negocios_sin_texto = pd.concat([existing_reviews_sin_texto, new_negocios_sin_texto], ignore_index=True) if existing_reviews_sin_texto is not None else new_negocios_sin_texto

                save_to_bucket(negocios_con_texto, 'g1_datos_limpios', 'reviews_negocios_con_texto_filtrados.parquet')
                save_to_bucket(negocios_sin_texto, 'g1_datos_limpios', 'reviews_negocios_sin_texto_filtrados.parquet')

                print("Reseñas concatenadas y guardadas correctamente en data limpia.")
            else:
                print("No se encontraron reseñas válidas para negocios existentes o posteriores al 2016.")
        else:
            print("Error al leer los metadatos existentes en datos limpios.")
    except Exception as e:
        print(f"Error en process_reviews: {str(e)}")





def save_to_bucket(df, bucket_name, destination_file_name):
    try:
        client = storage.Client()
        bucket = client.get_bucket(bucket_name)
        blob = bucket.blob(destination_file_name)
        
        local_file_path = f'/tmp/{destination_file_name}'
        df.to_parquet(local_file_path)
        
        with open(local_file_path, "rb") as f:
            blob.upload_from_file(f)
        
        os.remove(local_file_path)
        print(f"Archivo {destination_file_name} guardado en el bucket {bucket_name}.")
    except Exception as e:
        print(f"Error guardando el archivo {destination_file_name} en el bucket {bucket_name}: {str(e)}")
