<<<<<<< HEAD
=======
# Datatalk
Preguntale a los datos
>>>>>>> 165bf8fc9a9943323c100eae45bd0c2280d62178
# ExcelGPT - Consulta Inteligente de Datos

Aplicación web para análisis inteligente de datos Excel usando procesamiento de lenguaje natural.

## Características

- Carga de archivos Excel (.xlsx, .xls)
- Consultas en lenguaje natural
- Visualización de datos con gráficos interactivos
- Análisis básico sin API
- Integración opcional con OpenAI para análisis avanzado

## Requisitos

- Python 3.8+
- Las dependencias listadas en `requirements.txt`

## Instalación Local

1. Clonar el repositorio:
```bash
git clone <URL_DEL_REPOSITORIO>
cd datatalk
```

2. Crear un entorno virtual (opcional pero recomendado):
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
   - Copiar `.env.example` a `.env`
   - Agregar tu API key de OpenAI si deseas usar el modo avanzado

5. Ejecutar la aplicación:
```bash
streamlit run app.py
```

## Despliegue en Streamlit Cloud

1. Fork este repositorio a tu cuenta de GitHub
2. Visita [share.streamlit.io](https://share.streamlit.io)
3. Inicia sesión con tu cuenta de GitHub
4. Haz clic en "New app"
5. Selecciona el repositorio y la rama
6. Si usas OpenAI, configura la variable de entorno `OPENAI_API_KEY` en los secretos de la aplicación

## Uso

1. Accede a la aplicación web
2. Carga un archivo Excel
3. Escribe preguntas en lenguaje natural sobre tus datos
4. Obtén respuestas y visualizaciones automáticas

## Variables de Entorno

- `OPENAI_API_KEY`: Tu API key de OpenAI (opcional, solo para modo avanzado)

## Ejemplos de Preguntas

- "¿Cuántos registros hay por NIVEL en la FACULTAD de MEDICINA?"
- "¿Cuál es el promedio de edad en la FACULTAD de INGENIERÍA?"
<<<<<<< HEAD
- "En la FACULTAD de MEDICINA, para el NIVEL de PREGRADO ¿Cuántos registros hay por PROGRAMA?" 
=======
- "En la FACULTAD de MEDICINA, para el NIVEL de PREGRADO ¿Cuántos registros hay por PROGRAMA?"
>>>>>>> 165bf8fc9a9943323c100eae45bd0c2280d62178
