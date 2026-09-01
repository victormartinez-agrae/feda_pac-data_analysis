import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Explorador de Datos", layout="wide")

# ----------------------------------------------------
# 1. CONFIGURACIÓN: rutas a los CSV
# ----------------------------------------------------
DATA_DIR = Path("data")

@st.cache_data
def cargar_csv(nombre_archivo: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / nombre_archivo, sep=';',
                       index_col=False,
                       encoding='utf-8',
                       encoding_errors='backslashreplace')


# -----------------------------------------------------
# 2. PREPARACIÓN DE DATOS
# -----------------------------------------------------
st.title("📋 Visualización inicial")

@st.cache_data
def cargar_datos(archivos: list[str]) -> pd.DataFrame:
    lista_dfs = []
    for fichero in archivos:
        st.caption(f"Leyendo {fichero} ...")
        df_aux = cargar_csv(fichero)
        df_aux['CONVOCATORIA'] = int(fichero[-8:-4])
        lista_dfs.append(df_aux)

    datos_df = pd.concat(lista_dfs, ignore_index=True)
    orden_columnas = ["CONVOCATORIA"] + [c for c in datos_df.columns if c != "CONVOCATORIA"]
    datos_df = datos_df[orden_columnas]


    col_euros = ['FEAGA', 'FEADER', 'IMPORTECOFIN', 'FEADER_COFIN', 'IMPORTE_EUROS']
    for col in col_euros:
        datos_df[col] = datos_df[col].str.replace(',', '.').astype(float)

    col_fecha = ['FEC_INI', 'FEC_FIN']
    for col in col_fecha:
        datos_df[col] = pd.to_datetime(datos_df[col], format='%d/%m/%Y')

    return datos_df

# Carga de archivos
archivos_trabajo = ["TOP170k-Beneficiarios_municipio_ejercicio_financiero_2023.csv",
                    "TOP170k-Beneficiarios_municipio_ejercicio_financiero_2024.csv",
                    "TOP170k-Beneficiarios_municipio_ejercicio_financiero_2025.csv"]
'''
archivos_trabajo = ["Beneficiarios_municipio_ejercicio_financiero_2023.csv",
                    "Beneficiarios_municipio_ejercicio_financiero_2024.csv",
                    "Beneficiarios_municipio_ejercicio_financiero_2025.csv"]
'''

datos_df = cargar_datos(archivos_trabajo)

# -----------------------------------------------------
# 3. SELECCIÓN DE COLUMNAS A MOSTRAR
# -----------------------------------------------------
st.sidebar.header("⚙️ Opciones de visualización")

columnas_disponibles = list(datos_df.columns)
columnas_seleccionadas = st.sidebar.multiselect(
    "Columnas a mostrar",
    options=columnas_disponibles,
    default=columnas_disponibles,
)

# -----------------------------------------------------
# 4. FILTROS DINÁMICOS POR COLUMNA
# -----------------------------------------------------
st.sidebar.header("🔍 Filtros")

df_filtrado = datos_df.copy()

columnas_a_filtrar = st.sidebar.multiselect(
    "Elige columnas para filtrar",
    options=columnas_disponibles,
)

for col in columnas_a_filtrar:
    serie = datos_df[col]

    if pd.api.types.is_numeric_dtype(serie):
        min_val, max_val = float(serie.min()), float(serie.max())
        if min_val == max_val:
            st.sidebar.write(f"**{col}**: valor único ({min_val})")
            continue
        rango = st.sidebar.slider(
            f"Rango para '{col}'",
            min_value=min_val,
            max_value=max_val,
            value=(min_val, max_val),
        )
        df_filtrado = df_filtrado[
            (df_filtrado[col] >= rango[0]) & (df_filtrado[col] <= rango[1])
        ]

    elif pd.api.types.is_datetime64_any_dtype(serie):
        min_fecha, max_fecha = serie.min(), serie.max()
        rango_fechas = st.sidebar.date_input(
            f"Rango de fechas para '{col}'",
            value=(min_fecha, max_fecha),
        )
        if len(rango_fechas) == 2:
            inicio, fin = rango_fechas
            df_filtrado = df_filtrado[
                (df_filtrado[col] >= pd.to_datetime(inicio))
                & (df_filtrado[col] <= pd.to_datetime(fin))
            ]

    else:
        valores_unicos = sorted(serie.dropna().unique().tolist())
        seleccionados = st.sidebar.multiselect(
            f"Valores para '{col}'",
            options=valores_unicos,
            default=valores_unicos,
        )
        df_filtrado = df_filtrado[df_filtrado[col].isin(seleccionados)]

texto_busqueda = st.sidebar.text_input("Búsqueda libre (en todas las columnas)")
if texto_busqueda:
    mask = df_filtrado.apply(
        lambda row: row.astype(str).str.contains(texto_busqueda, case=False).any(),
        axis=1,
    )
    df_filtrado = df_filtrado[mask]

# -----------------------------------------------------
# 5. RESUMEN POR CATEGORÍA (selectores en sidebar)
# -----------------------------------------------------
st.sidebar.header("📈 Resumen por categoría")

COLUMNAS_AGRUPACION = ["BENEFICIARIO", "GRUPO_EMPRESA", "PROVINCIA",
                        "MUNICIPIO", "MEDIDA", "OBJETIVO_ESP", "year"]
COLUMNAS_ESTADISTICO = ["FEC_INI", "FEC_FIN", "FEAGA", "FEADER",
                         "IMPORTECOFIN", "FEADER_COFIN", "IMPORTE_EUROS"]

ESTADISTICOS = {
    "Suma": "sum",
    "Promedio": "mean",
    "Mediana": "median",
    "Máximo": "max",
    "Mínimo": "min",
}

opciones_agrupacion = ["(Ninguno)"] + [c for c in COLUMNAS_AGRUPACION if c in df_filtrado.columns]
col_agrupacion = st.sidebar.selectbox("Agrupar por columna", options=opciones_agrupacion)

if col_agrupacion != "(Ninguno)":
    estadistico_label = st.sidebar.selectbox("Estadístico a aplicar", options=list(ESTADISTICOS.keys()))
    estadistico = ESTADISTICOS[estadistico_label]

# -----------------------------------------------------
# 6. VISUALIZACIÓN DE LA TABLA (filtrada o resumida)
# -----------------------------------------------------
if col_agrupacion != "(Ninguno)":

    cols_estad_presentes = [c for c in COLUMNAS_ESTADISTICO if c in df_filtrado.columns]
    columnas_resto = [
        c for c in df_filtrado.columns
        if c not in cols_estad_presentes and c != col_agrupacion
    ]

    def aplicar_estadistico(serie, stat):
        if pd.api.types.is_datetime64_any_dtype(serie):
            if stat == "sum":
                return pd.NaT
            return getattr(serie, stat)()
        return getattr(serie, stat)()

    def valor_unico_o_vacio(serie):
        valores = serie.dropna().unique()
        return valores[0] if len(valores) == 1 else None

    if estadistico == "sum" and any(
        pd.api.types.is_datetime64_any_dtype(df_filtrado[c]) for c in cols_estad_presentes
    ):
        st.info("La 'Suma' no aplica a columnas de fecha (FEC_INI, FEC_FIN); esas celdas quedarán en blanco.")

    agg_dict = {}
    for col in cols_estad_presentes:
        agg_dict[col] = lambda s, stat=estadistico: aplicar_estadistico(s, stat)
    for col in columnas_resto:
        agg_dict[col] = valor_unico_o_vacio

    grupos = df_filtrado.groupby(col_agrupacion, dropna=False)
    df_mostrar = grupos.agg(agg_dict)
    df_mostrar["Nº registros"] = grupos.size()
    df_mostrar = df_mostrar.reset_index()

    orden_columnas = [col_agrupacion, "Nº registros"] + [c for c in df_filtrado.columns if c != col_agrupacion]
    df_mostrar = df_mostrar[orden_columnas]

    # Respetar la selección de columnas del usuario; el grupo y el conteo siempre se muestran
    columnas_a_mostrar = [
        c for c in orden_columnas
        if c in columnas_seleccionadas or c in [col_agrupacion, "Nº registros"]
    ]

    st.subheader("📈 Resumen por categoría")
    st.caption(
        f"Agrupado por **{col_agrupacion}** · Estadístico: **{estadistico_label}** · "
        f"{len(df_mostrar)} grupos ({len(df_filtrado)} filas de origen)"
    )

else:
    df_mostrar = df_filtrado
    columnas_a_mostrar = columnas_seleccionadas

    st.subheader("Datos tras aplicar opciones de visualización, filtros y resúmenes")
    st.caption(f"{len(df_filtrado)} filas de {len(datos_df)} totales")

if columnas_a_mostrar:
    column_config = {}
    for col in columnas_a_mostrar:
        if (col == "Nº registros") | (col == "CONVOCATORIA"):
            column_config[col] = st.column_config.NumberColumn(format="%d")
        elif col in ["FEC_INI", "FEC_FIN"]:
            column_config[col] = st.column_config.DateColumn(format="DD/MM/YYYY")
        elif col != "CONVOCATORIA" and pd.api.types.is_numeric_dtype(df_mostrar[col]):
            column_config[col] = st.column_config.NumberColumn(format="euro")

    st.dataframe(df_mostrar[columnas_a_mostrar], use_container_width=True, column_config=column_config)
else:
    st.warning("Selecciona al menos una columna para mostrar la tabla.")

# -----------------------------------------------------
# 7. DESCARGA DEL RESULTADO MOSTRADO
# -----------------------------------------------------
if columnas_a_mostrar:
    csv_export = df_mostrar[columnas_a_mostrar].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Descargar CSV de la tabla mostrada",
        data=csv_export,
        file_name="datos_FEDA_PAC_filtrados.csv",
        mime="text/csv",
    )
    st.caption("\n\n")

# -----------------------------------------------------
# 8. FUNCIONALIDADES EXTRA
# -----------------------------------------------------
tab_datos, tab_resumen, tab_graficos = st.tabs(["📋 Datos", "📈 Resumen", "📊 Gráficos"])
with tab_datos:
    st.caption("Data")
with tab_resumen:
    st.caption("Summary")
with tab_graficos:
    st.caption("Graphs")
