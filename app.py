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

        # Análisis básico según el tipo de pregunta
        if "cuántos" in question_lower or "cuantos" in question_lower or "total" in question_lower:
            # Si la pregunta menciona "por" seguido de una columna
            if "por" in question_lower:
                # Buscar la columna mencionada después de "por"
                for col in df.columns:
                    if col.lower() in question_lower.split("por")[-1]:
                        # Contar registros totales después de aplicar filtros
                        total_registros = len(df)
                        response = f"Total de registros: {total_registros}\n\n"
                        
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
                        break
            # Si la pregunta menciona directamente una columna
            elif any(col.lower() in question_lower for col in df.columns):
                # Contar registros totales
                response = f"Total de registros: {len(df)}\n"
                # Mostrar conteos para la columna mencionada
                for col in df.columns:
                    if col.lower() in question_lower:
                        value_counts = df[col].value_counts()
                        response += f"\nDistribución de {col}:\n"
                        for val, count in value_counts.items():
                            response += f"- {val}: {count} registros\n"
            else:
                # Contar registros totales
                response = f"Total de registros: {len(df)}\n"
        
        elif "promedio" in question_lower or "media" in question_lower:
            # Buscar promedios de columnas numéricas
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Promedios encontrados:\n"
            for col in numeric_cols:
                response += f"- Promedio de {col}: {df[col].mean():.2f}\n"
        
        elif "máximo" in question_lower or "maximo" in question_lower:
            # Buscar valores máximos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Valores máximos encontrados:\n"
            for col in numeric_cols:
                response += f"- Máximo de {col}: {df[col].max()}\n"
        
        elif "mínimo" in question_lower or "minimo" in question_lower:
            # Buscar valores mínimos
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            response = "Valores mínimos encontrados:\n"
            for col in numeric_cols:
                response += f"- Mínimo de {col}: {df[col].min()}\n"
        
        else:
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
    st.write("Carga tu archivo Excel y haz preguntas sobre tus datos")
    st.write("💡 Recomendación: Para mejor compatibilidad, usa archivos en formato .xlsx")

    # Selección del modelo
    model_type = st.sidebar.radio(
        "Selecciona el modelo a usar:",
        ["Análisis Básico (Sin API)", "OpenAI (requiere API key)"]
    )

    # Subida de archivo
    uploaded_file = st.file_uploader("Elige un archivo Excel", type=['xlsx', 'xls'])

    if uploaded_file is not None:
        try:
            # Leer el archivo Excel
            df = read_excel_file(uploaded_file)
            
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
                                fig = go.Figure(data=[
                                    go.Bar(
                                        x=plot_data['values'],
                                        y=plot_data['labels'],
                                        text=plot_data['values'],
                                        textposition='auto',
                                        orientation='h'  # Hacer el gráfico horizontal
                                    )
                                ])
                                fig.update_layout(
                                    title=f'Distribución por {plot_data["col"]}',
                                    xaxis_title='Cantidad de registros',
                                    yaxis_title=plot_data["col"],
                                    showlegend=False,
                                    height=max(500, len(plot_data['labels']) * 30),  # Ajustar altura según número de categorías
                                    yaxis={'type': 'category'},  # Mantener el orden exacto de las categorías
                                    margin=dict(l=200)  # Dar más espacio para etiquetas largas
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
            st.error(f"Error al procesar el archivo: {str(e)}")
            st.write("Sugerencias:")
            st.write("1. Guarda tu archivo en formato .xlsx y vuelve a intentarlo")
            st.write("2. Asegúrate de que el archivo no esté dañado o protegido")
            st.write("3. Verifica que puedas abrir el archivo en Excel normalmente")

if __name__ == "__main__":
    main()