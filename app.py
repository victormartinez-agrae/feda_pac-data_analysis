import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Explorador de Datos", layout="wide")

# -----------------------------------------------------
# 1. CONFIGURACIÓN: rutas a los CSV
# -----------------------------------------------------
DATA_DIR = Path("data")

@st.cache_data
def cargar_csv(nombre_archivo: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / nombre_archivo, sep=';',
                       index_col=False,
                       encoding='utf-8',
                       encoding_errors='backslashreplace')


# -----------------------------------------------------
# 2. EXTRACCIÓN DE DATOS
# -----------------------------------------------------
st.title("📊 Visualización inicial")

archivos_trabajo = ["Beneficiarios_municipio_ejercicio_financiero_2023.csv",
                    "Beneficiarios_municipio_ejercicio_financiero_2024.csv",
                    "Beneficiarios_municipio_ejercicio_financiero_2025.csv"]

lista_dfs = []
for fichero in archivos_trabajo:
    st.caption(f"Leyendo {fichero} ...")
    df_aux = cargar_csv(fichero)
    df_aux['year']=int(fichero[-8:-4])
    lista_dfs.append(df_aux)

datos_df = pd.concat(lista_dfs, ignore_index=True)

# Configuro columnas numéricas como float y columnas tipo fecha como datetime
# numéricas (€)
col_euros = ['FEAGA','FEADER','IMPORTECOFIN','FEADER_COFIN','IMPORTE_EUROS']
for col in col_euros:
  datos_df[col] = datos_df[col].str.replace(',','.').astype(float)
# fechas
col_fecha = ['FEC_INI','FEC_FIN']
for col in col_fecha:
  datos_df[col] = pd.to_datetime(datos_df[col], format='%d/%m/%Y')

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

# También un filtro de texto libre (búsqueda general)
texto_busqueda = st.sidebar.text_input("Búsqueda libre (en todas las columnas)")
if texto_busqueda:
    mask = df_filtrado.apply(
        lambda row: row.astype(str).str.contains(texto_busqueda, case=False).any(),
        axis=1,
    )
    df_filtrado = df_filtrado[mask]

# -----------------------------------------------------
# 5. VISUALIZACIÓN DE LA TABLA
# -----------------------------------------------------
st.subheader(f"Datos seleccionados")
st.caption(f"{len(df_filtrado)} filas de {len(datos_df)} totales")

if columnas_seleccionadas:
    # Construir configuración de columnas dinámicamente
    column_config = {}
    
    for col in columnas_seleccionadas:
        if col in ["FEC_INI", "FEC_FIN"]:
            column_config[col] = st.column_config.DateColumn(format="DD/MM/YYYY")
        elif col != "year" and pd.api.types.is_numeric_dtype(df_filtrado[col]):
            column_config[col] = st.column_config.NumberColumn(format="%,.2f €")
            #column_config[col] = st.column_config.NumberColumn(format="euro")            # columna equivalente a la anterior en Streamlite
    
    st.dataframe(
        df_filtrado[columnas_seleccionadas],
        use_container_width=True,
        column_config=column_config,
)
else:
    st.warning("Selecciona al menos una columna para mostrar la tabla.")

# -----------------------------------------------------
# 6. DESCARGA DEL RESULTADO FILTRADO
# -----------------------------------------------------
csv_export = df_filtrado[columnas_seleccionadas].to_csv(index=False).encode("utf-8")
st.download_button(
    "⬇️ Descargar CSV filtrado",
    data=csv_export,
    file_name=f"datos_FEDA_PAC_filtrados",
    mime="text/csv",
)

# -----------------------------------------------------
# 7. RESUMEN POR CATEGORÍA
# -----------------------------------------------------
st.subheader("📈 Resumen por categoría")

COLUMNAS_ESTADISTICO = ["FEC_INI", "FEC_FIN", "FEAGA", "FEADER",
                         "IMPORTECOFIN", "FEADER_COFIN", "IMPORTE_EUROS"]
COLUMNAS_AGRUPACION = ["BENEFICIARIO", "GRUPO_EMPRESA", "PROVINCIA",
                        "MUNICIPIO", "MEDIDA", "OBJETIVO_ESP", "year"]

ESTADISTICOS = {
    "Suma": "sum",
    "Promedio": "mean",
    "Mediana": "median",
    "Máximo": "max",
    "Mínimo": "min",
}

col_a, col_b = st.columns(2)
with col_a:
    col_agrupacion = st.selectbox(
        "Agrupar por columna",
        options=[c for c in COLUMNAS_AGRUPACION if c in df_filtrado.columns],
    )
with col_b:
    estadistico_label = st.selectbox("Estadístico a aplicar", options=list(ESTADISTICOS.keys()))

estadistico = ESTADISTICOS[estadistico_label]

# Columnas sobre las que se aplica el estadístico, presentes en el df filtrado
cols_estad_presentes = [c for c in COLUMNAS_ESTADISTICO if c in df_filtrado.columns]

# Columnas "informativas" (el resto): se muestra el valor si es único, si no, en blanco
columnas_resto = [
    c for c in df_filtrado.columns
    if c not in cols_estad_presentes and c != col_agrupacion
]


def aplicar_estadistico(serie, stat):
    """Aplica el estadístico, gestionando el caso de columnas de fecha con 'sum'."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        if stat == "sum":
            return pd.NaT
        return getattr(serie, stat)()
    return getattr(serie, stat)()


def valor_unico_o_vacio(serie):
    """Devuelve el valor si es único en el grupo; si no, None (celda en blanco)."""
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
df_resumen = grupos.agg(agg_dict)
df_resumen["Nº registros"] = grupos.size()
df_resumen = df_resumen.reset_index()

# Reordenar columnas: igual que la tabla original + Nº registros al final
orden_columnas = [col_agrupacion] + ["Nº registros"] + [c for c in df_filtrado.columns if c != col_agrupacion]
df_resumen = df_resumen[orden_columnas]

# Formato de columnas (igual criterio que la tabla principal)
column_config_resumen = {"Nº registros": st.column_config.NumberColumn(format="%d")}
for col in orden_columnas:
    if col in ["FEC_INI", "FEC_FIN"]:
        column_config_resumen[col] = st.column_config.DateColumn(format="DD/MM/YYYY")
    elif col != "year" and col in cols_estad_presentes:
        column_config_resumen[col] = st.column_config.NumberColumn(format="euro")

st.caption(f"Agrupado por **{col_agrupacion}** · Estadístico: **{estadistico_label}**")
st.dataframe(df_resumen, use_container_width=True, column_config=column_config_resumen)
