import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain.chat_models import ChatOpenAI
from langchain.agents.agent_types import AgentType
import numpy as np
import re
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import gspread
from google.oauth2 import service_account
from urllib.parse import urlparse, parse_qs

# Cargar variables de entorno
load_dotenv()

def read_excel_file(file):
    """
    Lee un archivo Excel y maneja diferentes formatos
    """
    file_name = file.name.lower()
    try:
        if file_name.endswith('.xlsx'):
            return pd.read_excel(file, engine='openpyxl')
        elif file_name.endswith('.xls'):
            st.warning("Nota: Para mejor compatibilidad, recomendamos usar archivos en formato .xlsx")
            try:
                return pd.read_excel(file, engine='openpyxl')
            except Exception:
                return pd.read_excel(file)
        else:
            raise Exception("Formato de archivo no soportado. Use .xlsx o .xls")
    except Exception as e:
        if "xlrd" in str(e):
            raise Exception("Error con el formato .xls - Por favor, guarda tu archivo en formato .xlsx y vuelve a intentarlo")
        raise Exception(f"Error al leer el archivo: {str(e)}")

def read_from_api(url, pagination_type="none", total_records=None, page_size=1000):
    """
    Lee datos desde una API JSON con soporte para paginación
    Args:
        url: URL base de la API
        pagination_type: Tipo de paginación ('page', 'offset', 'none')
        total_records: Número total de registros a extraer (None para todos)
        page_size: Tamaño de cada página
    """
    try:
        all_data = []
        current_page = 1
        offset = 0
        
        while True:
            # Construir URL con parámetros de paginación
            if pagination_type == "page":
                paginated_url = f"{url}{'&' if '?' in url else '?'}page={current_page}&limit={page_size}"
            elif pagination_type == "offset":
                paginated_url = f"{url}{'&' if '?' in url else '?'}offset={offset}&limit={page_size}"
            else:
                paginated_url = url
            
            # Realizar la petición
            response = requests.get(paginated_url)
            response.raise_for_status()
            data = response.json()
            
            # Extraer datos según la estructura
            if isinstance(data, list):
                page_data = data
            elif isinstance(data, dict):
                # Buscar la lista de datos en el diccionario
                for key, value in data.items():
                    if isinstance(value, list):
                        page_data = value
                        break
                else:
                    page_data = []
            else:
                raise Exception("Formato JSON no soportado")
            
            # Si no hay más datos, terminar
            if not page_data:
                break
                
            all_data.extend(page_data)
            
            # Verificar si hemos alcanzado el total de registros deseado
            if total_records and len(all_data) >= total_records:
                all_data = all_data[:total_records]
                break
                
            # Preparar siguiente página
            if pagination_type == "page":
                current_page += 1
            elif pagination_type == "offset":
                offset += len(page_data)
            else:
                break  # Si no hay paginación, solo hacer una petición
            
            # Mostrar progreso
            st.write(f"Registros obtenidos: {len(all_data)}")
            
        # Convertir a DataFrame
        df = pd.DataFrame(all_data)
        st.write(f"Total de registros obtenidos: {len(df)}")
        return df
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error al obtener datos de la API: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Error al decodificar JSON: {str(e)}")
    except Exception as e:
        raise Exception(f"Error al procesar datos de la API: {str(e)}")

def read_google_sheet(url):
    """
    Lee datos desde una hoja de cálculo de Google Sheets
    Args:
        url: URL de la hoja de cálculo de Google Sheets
    Returns:
        DataFrame de pandas con los datos
    """
    try:
        # Extraer el ID de la hoja de cálculo de la URL
        parsed_url = urlparse(url)
        
        # Diferentes patrones de URL de Google Sheets
        if 'spreadsheets/d/' in url:
            # Formato: https://docs.google.com/spreadsheets/d/[ID]/edit#gid=[GID]
            path_parts = parsed_url.path.split('/')
            try:
                sheet_id = path_parts[path_parts.index('d') + 1]
            except ValueError:
                # Intentar encontrar el ID después de "/spreadsheets/d/"
                for part in path_parts:
                    if len(part) > 20:  # Los IDs de Google Sheets suelen ser largos
                        sheet_id = part
                        break
                else:
                    raise Exception("No se pudo extraer el ID de la hoja de cálculo de la URL")
        elif 'docs.google.com/spreadsheets' in url and 'key=' in url:
            # Formato antiguo: https://docs.google.com/spreadsheets/ccc?key=[ID]
            sheet_id = parse_qs(parsed_url.query).get('key', [''])[0]
        else:
            # Si es solo el ID
            sheet_id = url.strip()
        
        # Extraer el gid (ID de la pestaña) si está presente
        gid = None
        if 'gid=' in url:
            query_params = parse_qs(parsed_url.fragment if parsed_url.fragment else parsed_url.query)
            gid = query_params.get('gid', ['0'])[0]
        
        st.write(f"Intentando acceder a la hoja de cálculo con ID: {sheet_id}")
        if gid:
            st.write(f"Pestaña (gid): {gid}")
        
        # Verificar si existe un archivo de credenciales
        creds_file = os.path.join(os.getcwd(), 'credentials.json')
        
        if os.path.exists(creds_file):
            # Usar credenciales de servicio si existen
            credentials = service_account.Credentials.from_service_account_file(
                creds_file, 
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            gc = gspread.authorize(credentials)
            
            # Abrir la hoja de cálculo con credenciales
            try:
                spreadsheet = gc.open_by_key(sheet_id)
            except gspread.exceptions.APIError as e:
                if "The caller does not have permission" in str(e):
                    raise Exception("No tienes permisos para acceder a esta hoja de cálculo. Asegúrate de que sea pública o que tengas acceso.")
                else:
                    raise e
            
            # Seleccionar la pestaña correcta
            if gid:
                worksheet = None
                for sheet in spreadsheet.worksheets():
                    if sheet.id == int(gid):
                        worksheet = sheet
                        break
                if worksheet is None:
                    worksheet = spreadsheet.sheet1  # Default to first sheet if gid not found
            else:
                worksheet = spreadsheet.sheet1  # Default to first sheet if no gid specified
            
            # Obtener todos los valores como lista de listas
            data = worksheet.get_all_values()
            
            if not data:
                raise Exception("La hoja de cálculo está vacía")
            
            # Convertir a DataFrame
            headers = data[0]
            if len(data) > 1:
                df = pd.DataFrame(data[1:], columns=headers)
                
                # Intentar convertir columnas numéricas
                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col])
                    except:
                        pass  # Si no se puede convertir, dejar como string
                
                return df
            else:
                return pd.DataFrame(columns=headers)
        else:
            # Si no hay credenciales, intentar acceder directamente sin mostrar advertencia
            try:
                # Usar requests para obtener los datos directamente con encoding UTF-8
                response = requests.get(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid or 0}")
                response.raise_for_status()
                
                # Asegurar que el contenido se decodifique correctamente con UTF-8
                response.encoding = 'utf-8'
                
                # Convertir CSV a DataFrame con encoding UTF-8
                df = pd.read_csv(
                    pd.io.common.StringIO(response.text),
                    encoding='utf-8',
                    encoding_errors='replace'  # Reemplazar caracteres que no se puedan decodificar
                )
                
                # Intentar convertir columnas numéricas
                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col])
                    except:
                        pass  # Si no se puede convertir, dejar como string
                
                return df
            except requests.exceptions.RequestException as e:
                # Solo mostrar advertencia si hay un error al acceder
                st.warning("""
                No se encontró un archivo de credenciales. Para acceder a hojas de cálculo privadas, necesitas:
                1. Crear un proyecto en Google Cloud Console
                2. Habilitar la API de Google Sheets
                3. Crear credenciales de servicio
                4. Descargar el archivo JSON y guardarlo como 'credentials.json' en la carpeta del proyecto
                
                Por ahora, solo se puede acceder a hojas de cálculo públicas.
                """)
                
                if "404" in str(e):
                    raise Exception("Hoja de cálculo no encontrada o no es accesible públicamente.")
                else:
                    raise Exception(f"Error al acceder a la hoja de cálculo: {str(e)}")
            
    except gspread.exceptions.SpreadsheetNotFound:
        raise Exception("Hoja de cálculo no encontrada. Verifica la URL.")
    except Exception as e:
        raise Exception(f"Error al leer la hoja de cálculo: {str(e)}")

def extract_filters_from_question(question, df):
    """
    Extrae filtros de la pregunta en lenguaje natural
    """
    filters = {}
    question_lower = question.lower()
    
    # Buscar patrones como "en [columna] de [valor]" o "[valor] en [columna]"
    patterns = [
        r'en\s+(\w+)\s+de\s+(\w+)',
        r'(\w+)\s+en\s+(\w+)',
        r'de\s+(\w+)\s+(\w+)',
        r'en\s+la\s+(\w+)\s+de\s+(\w+)',  # Para "en la FACULTAD de MEDICINA"
        r'en\s+el\s+(\w+)\s+de\s+(\w+)',  # Para "en el NIVEL de ESPECIALIDAD"
        r'en\s+la\s+(\w+)\s+(\w+)',  # Para "en la FACULTAD MEDICINA"
        r'en\s+el\s+(\w+)\s+(\w+)',  # Para "en el NIVEL ESPECIALIDAD"
        r'para\s+el\s+(\w+)\s+de\s+(\w+)',  # Para "para el NIVEL de PREGRADO"
        r'para\s+la\s+(\w+)\s+de\s+(\w+)',  # Para "para la FACULTAD de MEDICINA"
        r'para\s+el\s+(\w+)\s+(\w+)',  # Para "para el NIVEL de PREGRADO"
        r'para\s+la\s+(\w+)\s+(\w+)',  # Para "para la FACULTAD de MEDICINA"
        r'filtra\s+el\s+(\w+)\s+de\s+(\w+)',  # Para "filtra el NIVEL de PREGRADO"
        r'filtra\s+la\s+(\w+)\s+de\s+(\w+)',  # Para "filtra la FACULTAD de MEDICINA"
        r'(\w+)\s+de\s+(\w+)',  # Para "FACULTAD de MEDICINA"
    ]
    
    # Primero buscar filtros de FACULTAD
    for pattern in patterns:
        matches = re.finditer(pattern, question_lower)
        for match in matches:
            if len(match.groups()) >= 1:  # Cambiado para manejar patrones con un solo grupo
                # Si el patrón tiene un solo grupo (ej: "solo con PREGRADO")
                if len(match.groups()) == 1:
                    value = match.group(1)
                    # Buscar en todas las columnas si este valor existe
                    for col in df.columns:
                        if value.upper() in [str(val).upper() for val in df[col].unique()]:
                            exact_col = col
                            exact_value = next(str(val) for val in df[col].unique() if str(val).upper() == value.upper())
                            filters[exact_col] = exact_value
                            break
                else:
                    # Para patrones con dos o más grupos
                    col_name, value = match.group(1), match.group(2)
                    if col_name.upper() == 'FACULTAD':
                        exact_col = next(col for col in df.columns if col.upper() == 'FACULTAD')
                        if value.upper() in [str(val).upper() for val in df[exact_col].unique()]:
                            exact_value = next(str(val) for val in df[exact_col].unique() if str(val).upper() == value.upper())
                            filters[exact_col] = exact_value
                            break
    
    # Luego buscar otros filtros, excluyendo PROGRAMA si ya hay un filtro de FACULTAD
    for pattern in patterns:
        matches = re.finditer(pattern, question_lower)
        for match in matches:
            if len(match.groups()) >= 1:  # Cambiado para manejar patrones con un solo grupo
                # Si el patrón tiene un solo grupo
                if len(match.groups()) == 1:
                    continue  # Ya procesado arriba
                else:
                    # Para patrones con dos o más grupos
                    col_name, value = match.group(1), match.group(2)
                    if col_name.upper() in [col.upper() for col in df.columns]:
                        exact_col = next(col for col in df.columns if col.upper() == col_name.upper())
                        # No aplicar filtro de PROGRAMA si ya hay un filtro de FACULTAD
                        if exact_col.upper() == 'PROGRAMA' and 'FACULTAD' in filters:
                            continue
                        if value.upper() in [str(val).upper() for val in df[exact_col].unique()]:
                            exact_value = next(str(val) for val in df[exact_col].unique() if str(val).upper() == value.upper())
                            filters[exact_col] = exact_value
                            break
    
    return filters

def apply_filters(df, filters):
    """
    Aplica filtros al DataFrame
    """
    filtered_df = df.copy()
    for col, value in filters.items():
        if value:
            filtered_df = filtered_df[filtered_df[col].astype(str) == str(value)]
    return filtered_df

def process_question_free(df, question):
    """
    Procesa una pregunta usando análisis básico de datos
    """
    try:
        # Extraer filtros de la pregunta
        filters = extract_filters_from_question(question, df)
        
        # Aplicar filtros si existen
        if filters:
            df = apply_filters(df, filters)
            st.write("Filtros aplicados:")
            for col, value in filters.items():
                st.write(f"- {col}: {value}")

        # Convertir pregunta a minúsculas para facilitar el análisis
        question_lower = question.lower()
        response = ""
        filtered_data = None

        # Si la pregunta pide listar categorías
        if "dime" in question_lower or "muéstrame" in question_lower or "lista" in question_lower:
            # Buscar la columna mencionada
            for col in df.columns:
                if col.lower() in question_lower:
                    # Obtener valores únicos de la columna
                    unique_values = df[col].unique()
                    response = f"Lista de {col}:\n"
                    for val in sorted(unique_values):
                        response += f"- {val}\n"
                    return response, None
        
        # Verificar si la pregunta solicita operaciones específicas
        if "promedio" in question_lower or "media" in question_lower:
            # Buscar promedios de columnas numéricas
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Promedios encontrados:\n"
            for col in numeric_cols:
                response += f"- Promedio de {col}: {df[col].mean():.2f}\n"
            
            return response, None
        
        elif "máximo" in question_lower or "maximo" in question_lower:
            # Buscar valores máximos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Valores máximos encontrados:\n"
            for col in numeric_cols:
                response += f"- Máximo de {col}: {df[col].max()}\n"
            
            return response, None
        
        elif "mínimo" in question_lower or "minimo" in question_lower:
            # Buscar valores mínimos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Valores mínimos encontrados:\n"
            for col in numeric_cols:
                response += f"- Mínimo de {col}: {df[col].min()}\n"
            
            return response, None
        
        elif "resumen" in question_lower or "información general" in question_lower or "estadísticas" in question_lower:
            # Información general
            response = "Información general del dataset:\n"
            response += f"- Total de registros: {len(df)}\n"
            response += f"- Columnas disponibles: {', '.join(df.columns)}\n"
            response += "\nEstadísticas básicas:\n"
            for col in df.select_dtypes(include=[np.number]).columns:
                response += f"\n{col}:\n"
                response += f"- Promedio: {df[col].mean():.2f}\n"
                response += f"- Máximo: {df[col].max()}\n"
                response += f"- Mínimo: {df[col].min():.2f}\n"
                response += f"- Conteo: {df[col].count()}\n"
            
            return response, None
        
        # Por defecto, asumir que se pregunta por la cantidad de registros
        else:
            # Contar registros totales después de aplicar filtros
            total_registros = len(df)
            response = f"Total de registros: {total_registros}\n\n"
            
            # Verificar si la pregunta menciona "por" seguido de una columna
            if "por" in question_lower:
                # Buscar la columna mencionada después de "por"
                for col in df.columns:
                    if col.lower() in question_lower.split("por")[-1]:
                        # Mostrar distribución por la columna especificada
                        value_counts = df[col].value_counts().sort_index()
                        response += f"Distribución por {col}:\n"
                        
                        # Crear un diccionario ordenado para almacenar los datos
                        plot_data = {
                            'col': col,
                            'labels': [],
                            'values': []
                        }
                        
                        # Generar tanto la respuesta como los datos del gráfico
                        for val, count in value_counts.items():
                            response += f"- {val}: {count} registros\n"
                            plot_data['labels'].append(str(val))
                            plot_data['values'].append(count)
                        
                        return response, plot_data
            
            # Si no se especifica "por", pero se menciona una columna, mostrar distribución para esa columna
            elif any(col.lower() in question_lower for col in df.columns):
                for col in df.columns:
                    if col.lower() in question_lower:
                        # Mostrar distribución por la columna mencionada
                        value_counts = df[col].value_counts().sort_index()
                        response += f"Distribución por {col}:\n"
                        
                        # Crear un diccionario ordenado para almacenar los datos
                        plot_data = {
                            'col': col,
                            'labels': [],
                            'values': []
                        }
                        
                        # Generar tanto la respuesta como los datos del gráfico
                        for val, count in value_counts.items():
                            response += f"- {val}: {count} registros\n"
                            plot_data['labels'].append(str(val))
                            plot_data['values'].append(count)
                        
                        return response, plot_data
            
            # Si no se menciona ninguna columna específica, mostrar distribución para una columna relevante
            else:
                # Intentar encontrar una columna categórica con pocos valores únicos (ideal para visualización)
                categorical_cols = []
                for col in df.columns:
                    if df[col].nunique() < 20 and df[col].nunique() > 1:  # Columnas con entre 2 y 20 valores únicos
                        categorical_cols.append((col, df[col].nunique()))
                
                if categorical_cols:
                    # Ordenar por número de valores únicos (ascendente)
                    categorical_cols.sort(key=lambda x: x[1])
                    best_col = categorical_cols[0][0]
                    
                    # Mostrar distribución por la columna seleccionada
                    value_counts = df[best_col].value_counts().sort_index()
                    response += f"Distribución por {best_col}:\n"
                    
                    # Crear un diccionario ordenado para almacenar los datos
                    plot_data = {
                        'col': best_col,
                        'labels': [],
                        'values': []
                    }
                    
                    # Generar tanto la respuesta como los datos del gráfico
                    for val, count in value_counts.items():
                        response += f"- {val}: {count} registros\n"
                        plot_data['labels'].append(str(val))
                        plot_data['values'].append(count)
                    
                    return response, plot_data
            
            # Si no hay columnas categóricas adecuadas, solo devolver el total
            return response, None

    except Exception as e:
        raise Exception(f"Error al procesar la pregunta: {str(e)}")

def process_question_openai(df, question):
    """
    Procesa una pregunta sobre el DataFrame usando OpenAI
    """
    try:
        if not os.getenv("OPENAI_API_KEY"):
            raise Exception("No se encontró la API key de OpenAI. Por favor, configura la variable OPENAI_API_KEY en el archivo .env")

        # Extraer filtros de la pregunta
        filters = extract_filters_from_question(question, df)
        
        # Aplicar filtros si existen
        if filters:
            df = apply_filters(df, filters)
            st.write("Filtros aplicados:")
            for col, value in filters.items():
                st.write(f"- {col}: {value}")

        agent = create_pandas_dataframe_agent(
            ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613"),
            df,
            verbose=True,
            agent_type=AgentType.OPENAI_FUNCTIONS
        )

        mensaje = f"""
        Analiza los datos y responde la siguiente pregunta: {question}
        
        Instrucciones adicionales:
        1. Si la respuesta incluye números, formatea los números de manera legible
        2. Si es relevante, incluye un breve contexto
        3. Responde en español
        """

        return agent.run(mensaje)

    except Exception as e:
        raise Exception(f"Error al procesar la pregunta con OpenAI: {str(e)}")

def main():
    st.set_page_config(
        page_title="ExcelGPT - Consulta Inteligente de Datos",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 ExcelGPT - Consulta Inteligente de Datos")
    st.write("Carga tu archivo Excel o ingresa una URL de API JSON y haz preguntas sobre tus datos")
    st.write("💡 Recomendación: Para mejor compatibilidad, usa archivos en formato .xlsx")

    # Selección del modelo
    model_type = st.sidebar.radio(
        "Selecciona el modelo a usar:",
        ["Análisis Básico (Sin API)", "OpenAI (requiere API key)"]
    )

    # Selección de fuente de datos
    data_source = st.radio(
        "Selecciona la fuente de datos:",
        ["Archivo Excel", "Google Sheets", "API JSON"]
    )

    df = None
    if data_source == "Archivo Excel":
        # Subida de archivo
        uploaded_file = st.file_uploader("Elige un archivo Excel", type=['xlsx', 'xls'])
        if uploaded_file is not None:
            try:
                df = read_excel_file(uploaded_file)
            except Exception as e:
                st.error(f"Error al procesar el archivo: {str(e)}")
    elif data_source == "Google Sheets":
        # Entrada para la URL de Google Sheets
        sheets_url = st.text_input(
            "Ingresa la URL de la hoja de cálculo de Google Sheets:",
            placeholder="https://docs.google.com/spreadsheets/d/..."
        )
        
        if sheets_url:
            try:
                with st.spinner("Obteniendo datos de Google Sheets..."):
                    df = read_google_sheet(sheets_url)
            except Exception as e:
                st.error(f"Error al obtener datos de Google Sheets: {str(e)}")
    else:
        # Configuración de la API
        api_url = st.text_input("Ingresa la URL de la API JSON:")
        
        # Opciones de paginación
        pagination_type = st.selectbox(
            "Tipo de paginación",
            ["none", "page", "offset"],
            help="Selecciona el tipo de paginación que usa la API"
        )
        
        total_records = st.number_input(
            "Número total de registros a extraer (0 para todos)",
            min_value=0,
            value=1000,
            help="Ingresa el número total de registros que deseas extraer"
        )
        
        page_size = st.number_input(
            "Registros por página",
            min_value=1,
            value=1000,
            help="Número de registros a obtener en cada petición"
        )
        
        if api_url:
            try:
                with st.spinner("Obteniendo datos de la API..."):
                    df = read_from_api(
                        api_url,
                        pagination_type=pagination_type,
                        total_records=total_records if total_records > 0 else None,
                        page_size=page_size
                    )
            except Exception as e:
                st.error(f"Error al obtener datos de la API: {str(e)}")

    if df is not None:
        try:
            # Mostrar información básica
            st.write("### Vista previa de los datos")
            st.dataframe(df.head())
            
            st.write("### Información del dataset")
            st.write(f"- Número de filas: {df.shape[0]}")
            st.write(f"- Número de columnas: {df.shape[1]}")
            st.write(f"- Columnas disponibles: {', '.join(df.columns.tolist())}")
            
            # Campo para preguntas
            st.write("### Haz preguntas sobre tus datos")
            st.write("Ejemplos de preguntas que puedes hacer:")
            st.write("- ¿Cuántos registros hay por NIVEL en la FACULTAD de MEDICINA?")
            st.write("- ¿Cuál es el promedio de edad en la FACULTAD de INGENIERÍA?")
            st.write("- En la FACULTAD de MEDICINA, para el NIVEL de PREGRADO ¿Cuántos registros hay por PROGRAMA?")
            
            user_question = st.text_input("Escribe tu pregunta aquí:")
            
            if user_question:
                with st.spinner("Analizando tu pregunta..."):
                    try:
                        if model_type == "Análisis Básico (Sin API)":
                            response, plot_data = process_question_free(df, user_question)
                            st.success("Respuesta:")
                            st.write(response)
                            
                            # Mostrar el gráfico solo si hay datos para visualizar
                            if plot_data is not None:
                                st.write("\n### Visualización de la distribución")
                                
                                # Invertir el orden de las etiquetas y valores para mostrar la gráfica en orden inverso
                                plot_data['labels'] = plot_data['labels'][::-1]
                                plot_data['values'] = plot_data['values'][::-1]
                                
                                fig = go.Figure(data=[
                                    go.Bar(
                                        x=plot_data['values'],
                                        y=plot_data['labels'],
                                        text=plot_data['values'],
                                        textposition='auto',
                                        orientation='h'
                                    )
                                ])
                                fig.update_layout(
                                    title=f'Distribución por {plot_data["col"]}',
                                    xaxis_title='Cantidad de registros',
                                    yaxis_title=plot_data["col"],
                                    showlegend=False,
                                    height=max(500, len(plot_data['labels']) * 30),
                                    yaxis={'type': 'category'},
                                    margin=dict(l=200)
                                )
                                st.plotly_chart(fig, use_container_width=True)
                        else:
                            response = process_question_openai(df, user_question)
                            st.success("Respuesta:")
                            st.write(response)
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        if "API key" in str(e) and model_type != "Análisis Básico (Sin API)":
                            st.warning("Para usar OpenAI, necesitas configurar tu API key en el archivo .env")
                
        except Exception as e:
            st.error(f"Error al procesar los datos: {str(e)}")
            st.write("Sugerencias:")
            st.write("1. Verifica que los datos tengan el formato correcto")
            st.write("2. Asegúrate de que las columnas mencionadas en las preguntas existan")
            st.write("3. Revisa que los valores en los datos sean consistentes")

if __name__ == "__main__":
    main()