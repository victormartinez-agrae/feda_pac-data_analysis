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
                       encoding_errors='backslashreplace',
                       dtype={'GRUPO_EMPRESA': str})


# -----------------------------------------------------
# 2. PREPARACIÓN DE DATOS
# -----------------------------------------------------
st.title("📋 Explorador de Datos FEDA PAC")

@st.cache_data
def cargar_datos(archivos: list[str]) -> pd.DataFrame:
    lista_dfs = []
    for fichero in archivos:
        st.caption(f"Leyendo {fichero} ...")
        df_aux = cargar_csv(fichero)
        df_aux['CONVOCATORIA'] = fichero[-8:-4]
        lista_dfs.append(df_aux)

    datos_df = pd.concat(lista_dfs, ignore_index=True)

    col_espacios = ['BENEFICIARIO', 'GRUPO_EMPRESA']
    for col in col_espacios:
        datos_df[col] = (
            datos_df[col]
            .str.strip()
            .str.replace(r'\s+', ' ', regex=True)
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


archivos_trabajo = ["TOP1000-Beneficiarios_municipio_ejercicio_financiero_2023.csv",
                    "TOP1000-Beneficiarios_municipio_ejercicio_financiero_2024.csv",
                    "TOP1000-Beneficiarios_municipio_ejercicio_financiero_2025.csv"]

datos_df = cargar_datos(archivos_trabajo)
columnas_disponibles = list(datos_df.columns)


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
    st.session_state["seccion_activa"] = "📋 Visualización"


# -----------------------------------------------------
# 4. UTILIDADES COMPARTIDAS
# -----------------------------------------------------
def preparar_para_mostrar(df):
    """Copia del DataFrame con MUNICIPIO simplificado, solo para visualización."""
    df_vista = df.copy()
    if "MUNICIPIO" in df_vista.columns:
        df_vista["MUNICIPIO"] = df_vista["MUNICIPIO"].apply(
            lambda s: s.split(" - ", 1)[-1] if isinstance(s, str) and " - " in s else s
        )
    return df_vista


# -----------------------------------------------------
# 5. CONFIGURACIÓN REPO
# -----------------------------------------------------
import json
from github import Github, GithubException

CONFIG_DIR = Path("config")
FILE_CLASIFICACION = CONFIG_DIR / "clasificacion_medidas.json"

GITHUB_REPO_NAME = "victormartinez-agrae/feda_pac-data_analysis"
RUTA_FICHERO_CONFIG_REPO = "config/clasificacion_medidas.json"


def cargar_clasificacion_guardada() -> dict:
    """Lee la clasificación guardada en el repo (copia local clonada)."""
    if FILE_CLASIFICACION.exists():
        try:
            with open(FILE_CLASIFICACION, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "recurrentes": data.get("recurrentes", []),
                "puntuales": data.get("puntuales", []),
            }
        except (json.JSONDecodeError, OSError):
            return {"recurrentes": [], "puntuales": []}
    return {"recurrentes": [], "puntuales": []}


def guardar_clasificacion_en_github(recurrentes: list, puntuales: list) -> bool:
    """Escribe la clasificación en GitHub vía API (persiste para futuras sesiones)."""
    contenido = json.dumps(
        {"recurrentes": recurrentes, "puntuales": puntuales},
        ensure_ascii=False, indent=2,
    )
    try:
        g = Github(st.secrets["github_token"])
        repo = g.get_repo(GITHUB_REPO_NAME)
        try:
            archivo_actual = repo.get_contents(RUTA_FICHERO_CONFIG_REPO)
            repo.update_file(
                path=RUTA_FICHERO_CONFIG_REPO,
                message="Actualiza clasificación de medidas desde la app",
                content=contenido,
                sha=archivo_actual.sha,
            )
        except GithubException as e:
            if e.status == 404:
                repo.create_file(
                    path=RUTA_FICHERO_CONFIG_REPO,
                    message="Crea fichero de clasificación de medidas",
                    content=contenido,
                )
            else:
                raise
        return True
    except Exception as e:
        st.error(f"Error al guardar en GitHub: {e}")
        return False


# --- Inicialización global (disponible para cualquier sección) ---
TODAS_MEDIDAS = sorted(datos_df["MEDIDA"].dropna().unique())

if "config_recurrentes" not in st.session_state:
    clasif_guardada = cargar_clasificacion_guardada()
    st.session_state["config_recurrentes"] = [m for m in clasif_guardada["recurrentes"] if m in TODAS_MEDIDAS]
    st.session_state["config_puntuales"] = [m for m in clasif_guardada["puntuales"] if m in TODAS_MEDIDAS]

med_recurrentes = st.session_state["config_recurrentes"]
med_puntuales = st.session_state["config_puntuales"]
med_sin_clasificar = sorted(set(TODAS_MEDIDAS) - set(med_recurrentes) - set(med_puntuales))


# -----------------------------------------------------
# 6. SELECTOR DE SECCIÓN (sustituye a st.tabs)
# -----------------------------------------------------
OPCIONES_SECCION = ["📋 Visualización", "⚙️ Configuración", 
                    "🔗 Cruce", "📍 Provincia/municipio", "👶 Jóvenes agricultores"]

if "seccion_activa" not in st.session_state:
    st.session_state["seccion_activa"] = OPCIONES_SECCION[0]

col_titulo, col_reset = st.columns([5, 1])
with col_titulo:
    seccion_activa = st.segmented_control(
        "Sección",
        options=OPCIONES_SECCION,
        key="seccion_activa",
        label_visibility="collapsed",
    )
with col_reset:
    st.button("🔄 Restablecer todo", on_click=reset_todo, width='stretch')

st.divider()


# =======================================================
# SECCIÓN: VISUALIZACIÓN
# =======================================================
if seccion_activa == "📋 Visualización":

    # --- 6.1. Opciones de visualización ---
    with st.expander("⚙️ Opciones de visualización", expanded=True):
        if "columnas_seleccionadas" not in st.session_state:
            st.session_state["columnas_seleccionadas"] = columnas_disponibles
        columnas_seleccionadas = st.multiselect(
            "Columnas a mostrar",
            options=columnas_disponibles,
            key="columnas_seleccionadas",
            on_change=reset_filtros_y_resumen,
        )

    # --- 6.2. Filtros ---
    df_filtrado = datos_df.copy()

    with st.expander("🔍 Filtros"):
        columnas_a_filtrar = st.multiselect(
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
                    st.write(f"**{col}**: valor único ({min_val})")
                    continue
                rango = st.slider(
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
                rango_fechas = st.date_input(
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
                seleccionados = st.multiselect(
                    f"Valores para '{col}'",
                    options=valores_unicos,
                    default=valores_unicos,
                    format_func=lambda s: s.split(" - ", 1)[-1] if col == "MUNICIPIO" and " - " in str(s) else s,
                )
                df_filtrado = df_filtrado[df_filtrado[col].isin(seleccionados)]

        texto_busqueda = st.text_input(
            "Búsqueda libre (en todas las columnas)",
            key="texto_busqueda",
        )
        if texto_busqueda:
            mask = df_filtrado.apply(
                lambda row: row.astype(str).str.contains(texto_busqueda, case=False).any(),
                axis=1,
            )
            df_filtrado = df_filtrado[mask]

    # --- 6.3. Resumen por categoría ---
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

    with st.expander("📈 Resumen por categoría"):
        opciones_agrupacion = ["(Ninguno)"] + [c for c in COLUMNAS_AGRUPACION if c in df_filtrado.columns]
        col_agrupacion = st.selectbox(
            "Agrupar por columna",
            options=opciones_agrupacion,
            key="col_agrupacion",
        )

        if col_agrupacion != "(Ninguno)":
            estadistico_label = st.selectbox(
                "Estadístico a aplicar",
                options=list(ESTADISTICOS.keys()),
                key="estadistico_label",
            )
            estadistico = ESTADISTICOS[estadistico_label]

    # --- 6.4. Tabla resultante (filtrada o resumida) ---
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
            column_config=column_config,
        )

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


# =======================================================
# SECCIÓN: CONFIGURACIÓN
# =======================================================
elif seccion_activa == "⚙️ Configuración":
    st.subheader("⚙️ Configuración: clasificación de medidas")
    st.caption("Clasifica cada MEDIDA como recurrente o puntual. Lo no clasificado aparece en 'Sin clasificar'.")

    # Opciones dinámicas: cada multiselect excluye lo ya elegido en el otro
    opciones_recurrentes = [m for m in TODAS_MEDIDAS if m not in st.session_state.get("config_puntuales", [])]
    opciones_puntuales = [m for m in TODAS_MEDIDAS if m not in st.session_state.get("config_recurrentes", [])]

    # Salvaguarda: si el valor guardado ya no está entre las opciones
    # disponibles, se descarta silenciosamente para evitar un error
    st.session_state["config_recurrentes"] = [
        m for m in st.session_state.get("config_recurrentes", []) if m in opciones_recurrentes
    ]
    st.session_state["config_puntuales"] = [
        m for m in st.session_state.get("config_puntuales", []) if m in opciones_puntuales
    ]

    col_rec, col_punt = st.columns(2)
    with col_rec:
        st.multiselect(
            "🔁 Medidas recurrentes",
            options=opciones_recurrentes,
            key="config_recurrentes",
        )
    with col_punt:
        st.multiselect(
            "📌 Medidas puntuales",
            options=opciones_puntuales,
            key="config_puntuales",
        )

    st.multiselect(
        "❔ Sin clasificar",
        options=med_sin_clasificar,
        default=med_sin_clasificar,
        disabled=True,
        help="Se calcula automáticamente: son las medidas que no están en ninguna de las dos listas anteriores.",
    )

    st.divider()
    if st.button("💾 Guardar clasificación"):
        ok = guardar_clasificacion_en_github(
            st.session_state["config_recurrentes"],
            st.session_state["config_puntuales"],
        )
        if ok:
            st.success("Clasificación guardada correctamente en GitHub.")


# =======================================================
# SECCIÓN: CRUCE
# =======================================================
elif seccion_activa == "🔗 Cruce":
    st.write("ToDo")


# =======================================================
# SECCIÓN: PROVINCIA/MUNICIPIO
# =======================================================
elif seccion_activa == "📍 Provincia/municipio":
    st.write("ToDo")


# =======================================================
# SECCIÓN: JÓVENES AGRICULTORES
# =======================================================
elif seccion_activa == "👶 Jóvenes agricultores":
    st.write("ToDo")
