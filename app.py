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
                       #encoding='latin-1',
                       encoding_errors='backslashreplace',
                       dtype={'GRUPO_EMPRESA': str})       # Esta opción elimina "DtypeWarning: Columns (1) have mixed types"


# -----------------------------------------------------
# 2. PREPARACIÓN DE DATOS
# -----------------------------------------------------
st.title("Inicialización")

@st.cache_data
def cargar_datos(archivos: list[str]) -> pd.DataFrame:
    lista_dfs = []
    for fichero in archivos:
        st.caption(f"Leyendo {fichero} ...")
        df_aux = cargar_csv(fichero)
        #df_aux['CONVOCATORIA'] = int(fichero[-8:-4])
        df_aux['CONVOCATORIA'] = fichero[-8:-4]    # Comento lo anterior porque no trataremos esta columna como entero
        lista_dfs.append(df_aux)

    datos_df = pd.concat(lista_dfs, ignore_index=True)
    
    # Elimino espacios innecesarios
    col_espacios = ['BENEFICIARIO', 'GRUPO_EMPRESA']
    for col in col_espacios:
        datos_df[col] = (
            datos_df[col]
            .str.strip()                          # elimina espacios al inicio/final
            .str.replace(r'\s+', ' ', regex=True) # colapsa espacios múltiples internos en uno solo
        )
    
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
archivos_trabajo = ["TOP1000-Beneficiarios_municipio_ejercicio_financiero_2023.csv",
                    "TOP1000-Beneficiarios_municipio_ejercicio_financiero_2024.csv",
                    "TOP1000-Beneficiarios_municipio_ejercicio_financiero_2025.csv"]
#archivos_trabajo = ["Beneficiarios_municipio_ejercicio_financiero_2023.csv",
#                   "Beneficiarios_municipio_ejercicio_financiero_2024.csv",
#                   "Beneficiarios_municipio_ejercicio_financiero_2025.csv"]

datos_df = cargar_datos(archivos_trabajo)


# -----------------------------------------------------
# 3. FUNCIONES DE RESETEO EN CASCADA
# -----------------------------------------------------
def reset_filtros_y_resumen():
    st.session_state["columnas_a_filtrar"] = []
    st.session_state["col_agrupacion"] = "(Ninguno)"

def reset_resumen():
    st.session_state["col_agrupacion"] = "(Ninguno)"

def reset_todo():
    st.session_state["columnas_seleccionadas"] = columnas_disponibles
    st.session_state["columnas_a_filtrar"] = []
    st.session_state["texto_busqueda"] = ""
    st.session_state["col_agrupacion"] = "(Ninguno)"
    # Los selectbox de la pestaña Cruce solo existen en session_state
    # si esa pestaña ya se ha renderizado al menos una vez
    for key_cruce in ["conv_a", "conv_b", "medida_a", "medida_b"]:
        if key_cruce in st.session_state:
            del st.session_state[key_cruce]

st.sidebar.button("🔄 Restablecer todo", on_click=reset_todo)
st.sidebar.divider()


# -----------------------------------------------------
# 3. SIDEBAR
# -----------------------------------------------------

# 3.1. SELECCIÓN DE COLUMNAS A MOSTRAR
st.sidebar.header("⚙️ Opciones de visualización")

columnas_disponibles = list(datos_df.columns)
# Inicialización explícita del valor por defecto (solo si aún no existe)
if "columnas_seleccionadas" not in st.session_state:
    st.session_state["columnas_seleccionadas"] = columnas_disponibles
columnas_seleccionadas = st.sidebar.multiselect(
    "Columnas a mostrar",
    options=columnas_disponibles,
    key="columnas_seleccionadas",
    on_change=reset_filtros_y_resumen,
)

# 3.2. FILTROS DINÁMICOS POR COLUMNA
st.sidebar.header("🔍 Filtros")

df_filtrado = datos_df.copy()

columnas_a_filtrar = st.sidebar.multiselect(
    "Elige columnas para filtrar",
    options=columnas_disponibles,
    key="columnas_a_filtrar",
    on_change=reset_resumen,
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
            format_func=lambda s: s.split(" - ", 1)[-1] if col == "MUNICIPIO" and " - " in str(s) else s,
        )
        df_filtrado = df_filtrado[df_filtrado[col].isin(seleccionados)]

texto_busqueda = st.sidebar.text_input(
    "Búsqueda libre (en todas las columnas)",
    key="texto_busqueda"
)
if texto_busqueda:
    mask = df_filtrado.apply(
        lambda row: row.astype(str).str.contains(texto_busqueda, case=False).any(),
        axis=1,
    )
    df_filtrado = df_filtrado[mask]

# 3.3. RESUMEN POR CATEGORÍA (selectores en sidebar)
st.sidebar.header("📈 Resumen por categoría")

COLUMNAS_AGRUPACION = ["CONVOCATORIA", "BENEFICIARIO", "GRUPO_EMPRESA", "PROVINCIA",
                        "MUNICIPIO", "MEDIDA", "OBJETIVO_ESP"]
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
col_agrupacion = st.sidebar.selectbox(
    "Agrupar por columna", 
    options=opciones_agrupacion,
    key="col_agrupacion",
)

if col_agrupacion != "(Ninguno)":
    estadistico_label = st.sidebar.selectbox(
        "Estadístico a aplicar",
        options=list(ESTADISTICOS.keys()),
        key="estadistico_label"
    )
    estadistico = ESTADISTICOS[estadistico_label]


# -----------------------------------------------------
# 4. FUNCIONALIDADES
# -----------------------------------------------------
def preparar_para_mostrar(df):
    """Copia del DataFrame con MUNICIPIO simplificado, solo para visualización."""
    df_vista = df.copy()
    if "MUNICIPIO" in df_vista.columns:
        df_vista["MUNICIPIO"] = df_vista["MUNICIPIO"].apply(
            lambda s: s.split(" - ", 1)[-1] if isinstance(s, str) and " - " in s else s
        )
    return df_vista

import requests
from urllib.parse import quote

API_BASE_URL = "https://analisis.datosabiertos.jcyl.es/api/explore/v2.1/catalog/datasets/superficies-de-cultivos-lenosos/records"

@st.cache_data
def obtener_cultivos_municipio(nombre_municipio: str) -> pd.DataFrame:
    """Consulta la API de la JCyL y devuelve un DataFrame con los cultivos del municipio."""
    where_clause = f'municipio LIKE "{nombre_municipio}"'
    params = {
        "where": where_clause,
        "limit": 100,  # margen amplio; ajustar si un municipio tiene más de 100 registros
    }

    try:
        resp = requests.get(API_BASE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error al consultar la API de cultivos: {e}")
        return pd.DataFrame()

    registros = data.get("results", [])
    if not registros:
        return pd.DataFrame()

    df_cultivos = pd.DataFrame(registros)

    columnas_interes = ["ano", "grupo_de_cultivo", "cultivo",
                        "superficie_secano_ha", "superficie_regadio_ha", "superficie_total_ha"]
    columnas_presentes = [c for c in columnas_interes if c in df_cultivos.columns]

    return df_cultivos[columnas_presentes].sort_values("ano", ascending=False)


tab_visualizacion, tab_cruce, tab_prov_muni, tab_jovenesAg = st.tabs(["📋 Visualización", "🔗 Cruce", "📍 Provincia/municipio", "👶 Jóvenes agricultores"])
with tab_visualizacion:
    st.subheader("📋 Visualización de datos de trabajo")

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
    
    columnas_a_mostrar = [c for c in columnas_a_mostrar if c in df_mostrar.columns]
    
    if columnas_a_mostrar:
        column_config = {}
        for col in columnas_a_mostrar:
            if (col == "Nº registros") | (col == "CONVOCATORIA"):
                column_config[col] = st.column_config.NumberColumn(format="%d")
            elif col in ["FEC_INI", "FEC_FIN"]:
                column_config[col] = st.column_config.DateColumn(format="DD/MM/YYYY")
            elif col != "CONVOCATORIA" and pd.api.types.is_numeric_dtype(df_mostrar[col]):
                column_config[col] = st.column_config.NumberColumn(format="euro")
    
        st.dataframe(
            preparar_para_mostrar(df_mostrar[columnas_a_mostrar]),
            width='stretch',
            column_config=column_config
        )
        
        # Botón de descarga
        csv_export = df_mostrar[columnas_a_mostrar].to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV de la tabla mostrada",
            data=csv_export,
            file_name="datos_FEDA_PAC_filtrados.csv",
            mime="text/csv",
            key="descarga_visualizacion",
        )
    else:
        st.warning("Selecciona al menos una columna para mostrar la tabla.")



with tab_cruce:
    st.subheader("🔗 Beneficiarios que cumplen condiciones en dos convocatorias")

    convocatorias_disp = sorted(df_filtrado["CONVOCATORIA"].dropna().unique())
    medidas_disp = sorted(df_filtrado["MEDIDA"].dropna().unique())

    col1, col2 = st.columns(2)
    with col1:
        conv_a = st.selectbox("Convocatoria A", convocatorias_disp, index=0, key="conv_a")
        medida_a = st.selectbox("Medida en A", medidas_disp, key="medida_a")
    with col2:
        conv_b = st.selectbox("Convocatoria B", convocatorias_disp, index=0, key="conv_b")
        medida_b = st.selectbox("Medida en B", medidas_disp, key="medida_b")

    ben_a = set(df_filtrado.loc[
        (df_filtrado["CONVOCATORIA"] == conv_a) & (df_filtrado["MEDIDA"] == medida_a), "BENEFICIARIO"
    ])
    ben_b = set(df_filtrado.loc[
        (df_filtrado["CONVOCATORIA"] == conv_b) & (df_filtrado["MEDIDA"] == medida_b), "BENEFICIARIO"
    ])
    resultado = ben_a & ben_b

    st.caption(f"{len(resultado)} beneficiarios cumplen ambas condiciones")
    if resultado:
        df_cruce = df_filtrado[df_filtrado["BENEFICIARIO"].isin(resultado)]
        st.dataframe(
            preparar_para_mostrar(df_cruce),
            width='stretch'
        )
        # Botón de descarga
        csv_export_cruce = df_cruce.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV del cruce",
            data=csv_export_cruce,
            file_name="datos_FEDA_PAC_cruce.csv",
            mime="text/csv",
            key="descarga_cruce",
        )
with tab_prov_muni:
    st.subheader("📍 Consulta por provincia y municipio")

    PROVINCIAS_PERMITIDAS = ["León", "Zamora", "Salamanca", "Valladolid",
                              "Palencia", "Burgos", "Soria", "Segovia", "Ávila"]

    # Solo provincias de la lista que realmente existen en los datos
    provincias_existentes = datos_df["PROVINCIA"].dropna().unique()
    provincias_disp = [p for p in PROVINCIAS_PERMITIDAS if p in provincias_existentes]

    if not provincias_disp:
        st.warning("Ninguna de las provincias esperadas está presente en los datos.")
    else:
        provincia_sel = st.selectbox(
            "Provincia",
            options=provincias_disp,
            key="provincia_sel",
        )

        # Municipios disponibles para la provincia seleccionada
        municipios_disp = sorted(
            datos_df.loc[datos_df["PROVINCIA"] == provincia_sel, "MUNICIPIO"].dropna().unique()
        )

        # La key incluye la provincia: al cambiar de provincia, el widget se
        # reinicia automáticamente al primer municipio, sin arrastrar un
        # valor que ya no pertenece a la nueva lista de opciones.
        municipio_sel = st.selectbox(
            "Municipio",
            options=municipios_disp,
            format_func=lambda s: s[8:],
            #format_func=lambda s: s.split(" - ", 1)[-1] if " - " in s else s
            key=f"municipio_sel__{provincia_sel}",
        )

        st.markdown(f"**Provincia:** {provincia_sel} &nbsp;&nbsp;|&nbsp;&nbsp; **Municipio:** {municipio_sel[8:]}")
        
        st.divider()
        st.subheader("💲 PAC")       

        df_municipio = datos_df[
            (datos_df["PROVINCIA"] == provincia_sel) & (datos_df["MUNICIPIO"] == municipio_sel)
        ]

        resumen_municipio = (
            df_municipio.groupby("CONVOCATORIA")
            .agg(
                num_filas=("BENEFICIARIO", "size"),
                num_beneficiarios=("BENEFICIARIO", "nunique"),
                total_importe_euros=("IMPORTE_EUROS", "sum"),
            )
            .reset_index()
            .rename(columns={
                "CONVOCATORIA": "Año",
                "num_filas": "Nº filas",
                "num_beneficiarios": "Nº beneficiarios",
                "total_importe_euros": "IMPORTE_EUROS",
            })
        )

        st.dataframe(
            preparar_para_mostrar(resumen_municipio),
            width='stretch',
            column_config={
                "Nº filas": st.column_config.NumberColumn(format="%d"),
                "Nº beneficiarios": st.column_config.NumberColumn(format="%d"),
                "IMPORTE_EUROS": st.column_config.NumberColumn(format="euro"),
            },
            hide_index=True,

            st.divider()
            st.subheader("🌾 Superficies de cultivos leñosos")
            
            nombre_municipio_limpio = municipio_sel.split(" - ", 1)[-1] if " - " in municipio_sel else municipio_sel
            
            df_cultivos = obtener_cultivos_municipio(nombre_municipio_limpio)
            
            if df_cultivos.empty:
                st.info(f"No se han encontrado datos de cultivos leñosos para '{nombre_municipio_limpio}' en la API.")
            else:
                st.dataframe(
                    df_cultivos,
                    width='stretch',
                    column_config={
                        "ano": st.column_config.NumberColumn("Año", format="%d"),
                        "grupo_de_cultivo": "Grupo de cultivo",
                        "cultivo": "Cultivo",
                        "superficie_secano_ha": st.column_config.NumberColumn("Secano (ha)", format="%.2f"),
                        "superficie_regadio_ha": st.column_config.NumberColumn("Regadío (ha)", format="%.2f"),
                        "superficie_total_ha": st.column_config.NumberColumn("Total (ha)", format="%.2f"),
                    },
                    hide_index=True,
                )
        )
with tab_jovenesAg:
    st.write("ToDo")
