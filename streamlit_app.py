# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import unicodedata
import base64
import os
from datetime import datetime
import numpy as np

# ==================== CONFIGURACIÓN DE LA PÁGINA ====================

st.set_page_config(
    page_title="Sistema de Recomendación de Productos",
    page_icon="🏥",
    layout="wide"
)

# ==================== INICIALIZACIÓN DE SESSION STATE ====================

# Inicializar variables de sesión para mantener datos entre páginas
if 'recomendacion_generada' not in st.session_state:
    st.session_state.recomendacion_generada = False

if 'plan_recomendado' not in st.session_state:
    st.session_state.plan_recomendado = None

if 'edad_titular' not in st.session_state:
    st.session_state.edad_titular = 30

if 'numero_afiliados' not in st.session_state:
    st.session_state.numero_afiliados = 1

if 'tiene_continuidad' not in st.session_state:
    st.session_state.tiene_continuidad = "No"

if 'distrito_cliente' not in st.session_state:
    st.session_state.distrito_cliente = "Santiago de Surco"

if 'sexo_cliente' not in st.session_state:
    st.session_state.sexo_cliente = "Masculino"

# ==================== FUNCIONES AUXILIARES ====================

def normalizar_texto(texto):
    """Normaliza texto eliminando tildes y convirtiendo a mayúsculas"""
    texto_sin_tildes = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto_sin_tildes.upper()

def cargar_tarifas():
    """Carga las tarifas base desde el archivo Excel"""
    try:
        df_tarifas = pd.read_excel('tarifario_base.xlsx')
        # Validar columnas requeridas
        columnas_requeridas = ['RangoEtario']
        for col in columnas_requeridas:
            if col not in df_tarifas.columns:
                st.error(f"⚠️ Falta la columna '{col}' en el tarifario")
                return None
        return df_tarifas
    except FileNotFoundError:
        st.error("⚠️ No se encontró el archivo 'tarifario_base.xlsx'")
        return None
    except Exception as e:
        st.error(f"⚠️ Error al cargar tarifas: {str(e)}")
        return None

def cargar_campanas():
    """Carga las campañas activas desde archivo Excel o retorna campañas por defecto"""
    try:
        df_campanas = pd.read_excel('campanas.xlsx')
        return df_campanas
    except:
        # Campañas por defecto si no existe el archivo
        return pd.DataFrame({
            'Nombre': ['Campaña ESENCIAL', 'Campaña CONTINUIDAD'],
            'Fecha_Inicio': [datetime(2024, 10, 20), datetime(2024, 10, 20)],
            'Fecha_Fin': [datetime(2024, 11, 30), datetime(2024, 11, 30)],
            'Tipo_Campana': ['General', 'Continuidad'],
            'MSLD': [33, 15], 'AM18': [33, 15],
            'MINT': [25, 15], 'MNAC': [25, 15], 'AM05': [25, 15],
            'AM15': [25, 15], 'AM17': [25, 15]
        })

def validar_edad_sin_continuidad(plan, edad):
    """
    Valida si la edad es aceptable para el plan cuando NO hay continuidad
    
    Restricciones sin continuidad:
    - MSLD, MINT, MNAC, AM05: máximo 65 años
    - AM18, AM17, AM15: máximo 60 años
    
    Retorna: (es_valido, mensaje)
    """
    planes_65 = ['MSLD', 'MINT', 'MNAC', 'AM05']
    planes_60 = ['AM18', 'AM17', 'AM15']
    
    if plan in planes_65:
        if edad > 65:
            return False, f"⚠️ Sin continuidad, la edad máxima para {plan} es 65 años"
        return True, ""
    
    elif plan in planes_60:
        if edad > 60:
            return False, f"⚠️ Sin continuidad, la edad máxima para {plan} es 60 años"
        return True, ""
    
    # Para otros planes o con continuidad, no hay restricción
    return True, ""

def obtener_planes_alternativos(plan_principal, edad, tiene_continuidad):
    """
    Obtiene planes alternativos válidos según la edad y continuidad
    
    Retorna: (segunda_opcion, tercera_opcion)
    """
    # Definir todas las opciones posibles
    if plan_principal == "MNAC":
        opciones = ["MSLD", "AM15", "MINT"]
    elif plan_principal == "MSLD":
        opciones = ["AM15", "AM05", "MNAC"]
    elif plan_principal == "AM15":
        opciones = ["AM17", "AM05", "MSLD"]
    elif plan_principal == "MINT":
        opciones = ["MNAC", "MSLD", "AM05"]
    else:
        opciones = ["MSLD", "AM15", "AM05"]
    
    # Filtrar opciones válidas según continuidad y edad
    opciones_validas = []
    for plan in opciones:
        es_valido, _ = validar_edad_sin_continuidad(plan, edad)
        if tiene_continuidad == "Sí" or es_valido:
            opciones_validas.append(plan)
    
    # Retornar las dos primeras opciones válidas (o None si no hay)
    segunda = opciones_validas[0] if len(opciones_validas) > 0 else None
    tercera = opciones_validas[1] if len(opciones_validas) > 1 else None
    
    return segunda, tercera

def calcular_pago_financiado(valor_presente, tasa_anual, num_cuotas):
    """
    Calcula el pago periódico usando la fórmula de Excel PAGO()
    
    Parámetros:
    - valor_presente: Monto total de la prima anual
    - tasa_anual: Tasa de interés anual (ej: 0.04 para 4%)
    - num_cuotas: Número de cuotas (12, 10, 6, 4)
    
    Retorna: Monto de cuota mensual
    """
    if num_cuotas == 1:
        return valor_presente
    
    tasa_mensual = tasa_anual / 12
    
    # Fórmula PAGO: pago = VP * (tasa * (1 + tasa)^n) / ((1 + tasa)^n - 1)
    if tasa_mensual == 0:
        return valor_presente / num_cuotas
    
    factor = (1 + tasa_mensual) ** num_cuotas
    pago_mensual = valor_presente * (tasa_mensual * factor) / (factor - 1)
    
    return pago_mensual

def obtener_tarifa_base(df_tarifas, plan, edad, es_hijo=False):
    """
    Obtiene la tarifa base según plan, edad y si es hijo
    
    Parámetros:
    - df_tarifas: DataFrame con las tarifas
    - plan: Código del plan (MINT, MNAC, etc.)
    - edad: Edad del asegurado
    - es_hijo: Boolean indicando si es hijo o titular
    
    Retorna: Tarifa base anual
    """
    if df_tarifas is None:
        return None
    
    # Validar que el plan existe en el tarifario
    if plan not in df_tarifas.columns:
        st.warning(f"⚠️ El plan {plan} no existe en el tarifario")
        return None
    
    # Determinar el rango etario
    if es_hijo:
        if edad <= 17:
            rango = 'Hijos 0 - 17 años'
        elif edad <= 25:
            rango = 'Hijos 18 - 25 años'
        elif edad == 26:
            rango = 'Hijos 26 años'
        else:
            # CORRECCIÓN: Para hijos mayores de 26 años, usar la edad específica
            # Ejemplo: hijo de 27 años -> buscar "27 años" en el tarifario
            rango = f'{edad} años'
    else:
        if edad <= 17:
            rango = '0 - 17 años'
        elif edad <= 25:
            rango = '18 - 25 años'
        else:
            rango = f'{edad} años'
    
    # Buscar la tarifa en el DataFrame
    try:
        fila = df_tarifas[df_tarifas['RangoEtario'] == rango]
        if not fila.empty and plan in fila.columns:
            tarifa = fila[plan].values[0]
            return float(tarifa) if pd.notna(tarifa) else None
        return None
    except Exception as e:
        st.error(f"Error al obtener tarifa: {str(e)}")
        return None

def aplicar_descuento_campana(df_campanas, plan, tarifa_base, tiene_continuidad):
    """
    Aplica descuento de campaña vigente según si tiene continuidad o no
    
    Retorna: (tarifa_con_descuento, porcentaje_descuento, nombre_campana)
    """
    if df_campanas is None or df_campanas.empty:
        return tarifa_base, 0, None
    
    fecha_actual = datetime.now()
    
    # Determinar el tipo de campaña a buscar
    tipo_campana = 'Continuidad' if tiene_continuidad == "Sí" else 'General'
    
    # Buscar campañas vigentes del tipo correspondiente
    campanas_vigentes = df_campanas[
        (df_campanas['Fecha_Inicio'] <= fecha_actual) & 
        (df_campanas['Fecha_Fin'] >= fecha_actual) &
        (df_campanas['Tipo_Campana'] == tipo_campana)
    ]
    
    # Si no hay campaña específica de continuidad, buscar campaña general
    if campanas_vigentes.empty and tipo_campana == 'Continuidad':
        campanas_vigentes = df_campanas[
            (df_campanas['Fecha_Inicio'] <= fecha_actual) & 
            (df_campanas['Fecha_Fin'] >= fecha_actual) &
            (df_campanas['Tipo_Campana'] == 'General')
        ]
    
    if campanas_vigentes.empty:
        return tarifa_base, 0, None
    
    # Tomar la primera campaña vigente
    campana = campanas_vigentes.iloc[0]
    
    if plan in campana and pd.notna(campana[plan]):
        descuento_pct = float(campana[plan])
        tarifa_con_descuento = tarifa_base * (1 - descuento_pct / 100)
        return tarifa_con_descuento, descuento_pct, campana['Nombre']
    
    return tarifa_base, 0, campana['Nombre']

def mostrar_pdf(archivo_pdf):
    """Muestra un PDF en Streamlit"""
    if not os.path.exists(archivo_pdf):
        st.warning(f"El archivo {archivo_pdf} no está disponible.")
        return False
        
    try:
        with open(archivo_pdf, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        pdf_display = f"""
        <embed src="data:application/pdf;base64,{base64_pdf}" 
               width="100%" 
               height="600" 
               type="application/pdf">
        """
        st.markdown(pdf_display, unsafe_allow_html=True)
        return True
    except Exception as e:
        st.error(f"Error al cargar el PDF: {str(e)}")
        return False

def crear_boton_descarga_pdf(archivo_pdf):
    """Crea un botón para descargar el PDF"""
    if not os.path.exists(archivo_pdf):
        return False
        
    try:
        with open(archivo_pdf, "rb") as pdf_file:
            PDFbyte = pdf_file.read()

        st.download_button(
            label="📄 Descargar Cartilla Comparativa",
            data=PDFbyte,
            file_name="Cartilla_Comparativa_Seguros_Integrales_2024.pdf",
            mime='application/octet-stream',
            help="Haz clic para descargar la cartilla comparativa completa"
        )
        return True
    except:
        return False

# ==================== HEADER ====================

try:
    if os.path.exists("pacifico.png"):
        st.image("pacifico.png", width=200)
    else:
        st.markdown(
            """
            <div style="text-align:center; background-color:#00BFFF; color:white; padding:20px; border-radius:10px; margin-bottom:20px;">
                <h2>🏥 PACÍFICO SEGUROS</h2>
            </div>
            """,
            unsafe_allow_html=True
        )
except:
    st.markdown(
        """
        <div style="text-align:center; background-color:#00BFFF; color:white; padding:20px; border-radius:10px; margin-bottom:20px;">
            <h2>🏥 PACÍFICO SEGUROS</h2>
        </div>
        """,
        unsafe_allow_html=True
    )

st.title("Sistema de recomendación productos integrales")

# Cargar datos
df_tarifas = cargar_tarifas()
df_campanas = cargar_campanas()

# ==================== MENÚ DE NAVEGACIÓN ====================

menu = st.sidebar.radio(
    "📋 Menú Principal",
    ["🎯 Recomendador de Plan", "💰 Calculadora de Tarifas", "📊 Campañas Vigentes", "📚 Recursos"]
)

# ==================== MÓDULO 1: RECOMENDADOR DE PLAN ====================

if menu == "🎯 Recomendador de Plan":
    st.sidebar.header("Información del Cliente")
    
    # NUEVO: Campo de Continuidad
    tiene_continuidad = st.sidebar.selectbox(
        "¿Cuenta con continuidad?",
        ["No", "Sí"],
        help="La continuidad indica si el cliente viene de otro seguro de salud"
    )
    
    # Guardar en session_state
    st.session_state.tiene_continuidad = tiene_continuidad
    
    # Mostrar información sobre continuidad
    if tiene_continuidad == "Sí":
        st.sidebar.success("✅ Con continuidad: Sin restricción de edad")
    else:
        st.sidebar.warning("⚠️ Sin continuidad: Aplican restricciones de edad")
    
    Edad = st.sidebar.slider("Edad del Titular", min_value=18, max_value=90, step=1, value=st.session_state.edad_titular)
    st.session_state.edad_titular = Edad
    
    Numero_dependientes = st.sidebar.slider("Número de afiliados", min_value=1, max_value=10, step=1, value=st.session_state.numero_afiliados)
    st.session_state.numero_afiliados = Numero_dependientes

    opciones_distrito_display = [
        "Santiago de Surco", "Miraflores", "San Isidro", "San Juan de Lurigancho", 
        "La Molina", "Cercado de Lima", "Jesús María", "San Juan de Miraflores",
        "San Borja", "Magdalena del Mar", "Pueblo Libre", "Otro"
    ]
    distrito_mapping_especial = {"Cercado de Lima": "LIMA"}

    Distrito_display = st.sidebar.selectbox("Selecciona el distrito", opciones_distrito_display, 
                                            index=opciones_distrito_display.index(st.session_state.distrito_cliente) 
                                            if st.session_state.distrito_cliente in opciones_distrito_display else 0)
    st.session_state.distrito_cliente = Distrito_display
    
    if Distrito_display in distrito_mapping_especial:
        Distrito = distrito_mapping_especial[Distrito_display]
    else:
        Distrito = normalizar_texto(Distrito_display)

    Sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Femenino"], 
                                index=0 if st.session_state.sexo_cliente == "Masculino" else 1)
    st.session_state.sexo_cliente = Sexo
    
    Tiene_Hijo_Menor = st.sidebar.selectbox("¿Incluye hijo menor de edad?", ["No", "Si"])

    if st.sidebar.button("Generar Recomendación", type="primary"):
        with st.spinner('🔍 Analizando perfil del cliente...'):
            # Lógica de recomendación
            plan = "MSLD"

            if Distrito in ["MIRAFLORES", "SAN ISIDRO", "LA MOLINA", "SANTIAGO DE SURCO"]:
                if Sexo == "Masculino":
                    plan = "MNAC" if Edad >= 30 else "MSLD"
                else:
                    plan = "MNAC" if Edad > 30 else "MSLD"  # Corregido: era MLSD

            elif Distrito in ["LOS OLIVOS", "SAN JUAN DE LURIGANCHO", "SAN JUAN DE MIRAFLORES"]:
                if Sexo == "Femenino":
                    plan = "MSLD" if Numero_dependientes >= 2 else "AM15"
                else:
                    plan = "MSLD" if Edad > 35 else "AM15"
            else:
                if Sexo == "Femenino":
                    plan = "MSLD" if Edad > 30 and Numero_dependientes >= 2 else "AM15"
                else:
                    plan = "AM15" if Edad < 30 else "MSLD"

            # NUEVO: Validar edad según continuidad
            es_valido, mensaje_error = validar_edad_sin_continuidad(plan, Edad)
            
            if not es_valido:
                st.error(mensaje_error)
                st.warning("💡 **Sugerencia:** El cliente necesita continuidad para acceder a este plan, o considera planes alternativos.")
                # Intentar encontrar un plan alternativo válido
                planes_alternativos = ['AM15', 'AM17', 'AM18', 'AM05', 'MSLD', 'MNAC', 'MINT']
                for plan_alt in planes_alternativos:
                    es_valido_alt, _ = validar_edad_sin_continuidad(plan_alt, Edad)
                    if es_valido_alt:
                        plan = plan_alt
                        st.info(f"✅ Plan ajustado a: {plan}")
                        break
            
            # Guardar en session_state
            st.session_state.plan_recomendado = plan
            st.session_state.recomendacion_generada = True
            
            # Obtener planes alternativos válidos
            segunda_opcion, tercera_opcion = obtener_planes_alternativos(plan, Edad, tiene_continuidad)
            
            # Nombres de los planes (solo siglas)
            nombres_planes = {
                'MNAC': 'MNAC',
                'MSLD': 'MSLD',
                'MLSD': 'MLSD',
                'AM15': 'AM15',
                'AM17': 'AM17',
                'AM05': 'AM05',
                'AM18': 'AM18',
                'MINT': 'MINT'
            }
            
            # Mostrar resultado - Plan Recomendado (Grande)
            st.success("✅ Recomendación generada exitosamente")
            
            st.markdown(
                f"""
                <div style="background-color:#e6f7ff; padding:30px; border-radius:15px; margin-bottom:20px; border:3px solid #00BFFF;">
                    <h1 style='text-align:center; color:#00BFFF; font-weight:bold; text-shadow: 2px 2px 4px #aaa; margin-bottom:10px;'>
                        🎯 PLAN RECOMENDADO: {nombres_planes.get(plan, plan)}
                    </h1>
                    <p style='text-align:center; color:#0080ff; font-size:16px; margin-top:15px;'>
                        Este es el plan más adecuado según el perfil del cliente
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Mostrar información de continuidad aplicada
            if tiene_continuidad == "Sí":
                st.info("ℹ️ **Campaña de Continuidad:** Este cliente califica para descuentos especiales por continuidad")
            
            # Opciones alternativas
            st.markdown("### 🔄 Opciones Alternativas")
            
            col1, col2 = st.columns(2)
            
            # Segunda opción (mediano)
            if segunda_opcion:
                with col1:
                    st.markdown(
                        f"""
                        <div style="background-color:#f0f8ff; padding:20px; border-radius:12px; border:2px solid #87CEEB; height:160px; display:flex; flex-direction:column; justify-content:center;">
                            <h3 style='text-align:center; color:#4682B4; margin-bottom:10px; font-size:18px;'>
                                Segunda Opción
                            </h3>
                            <h2 style='text-align:center; color:#00BFFF; font-weight:bold; font-size:24px; line-height:1.2; word-wrap:break-word; padding:0 10px;'>
                                {nombres_planes.get(segunda_opcion, segunda_opcion)}
                            </h2>
                            <p style='text-align:center; color:#666; font-size:14px; margin-top:10px;'>
                                Alternativa recomendada
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            
            # Tercera opción (pequeño)
            if tercera_opcion:
                with col2:
                    st.markdown(
                        f"""
                        <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border:1px solid #B0C4DE; height:160px; display:flex; flex-direction:column; justify-content:center;">
                            <h4 style='text-align:center; color:#708090; margin-bottom:8px; font-size:16px;'>
                                Tercera Opción
                            </h4>
                            <h3 style='text-align:center; color:#4682B4; font-weight:bold; font-size:20px; line-height:1.2; word-wrap:break-word; padding:0 10px;'>
                                {nombres_planes.get(tercera_opcion, tercera_opcion)}
                            </h3>
                            <p style='text-align:center; color:#888; font-size:13px; margin-top:8px;'>
                                Opción adicional
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
            
            st.markdown("---")
            
            # Información adicional del cliente
            st.markdown("### 📋 Detalles de la Recomendación")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.info(f"**Cliente:** {Sexo}, {Edad} años")
            with col2:
                st.info(f"**Afiliados:** {Numero_dependientes} persona(s)")
            with col3:
                st.info(f"**Distrito:** {Distrito_display}")
            with col4:
                continuidad_icon = "✅" if tiene_continuidad == "Sí" else "❌"
                st.info(f"**Continuidad:** {continuidad_icon} {tiene_continuidad}")
            
            # Llamado a acción para cotización
            st.markdown(
                """
                <div style="background-color:#d1ecf1; padding:20px; border-radius:10px; border-left:5px solid #0c5460; margin:20px 0;">
                    <h4 style='color:#0c5460; margin-bottom:10px;'>💰 ¿Listo para cotizar?</h4>
                    <p style='color:#0c5460; margin:0;'>
                        Los datos del cliente ya están cargados. 
                        Ve a la <strong>Calculadora de Tarifas</strong> para generar la cotización con un solo clic.
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

            # Registro de gestión
            st.markdown("### 🎯 Siguiente Paso")
            st.markdown(
                """
                <div style="text-align:center; margin:30px 0; padding:20px; background-color:#f0f8ff; border-radius:10px;">
                    <p style="font-size:18px; margin-bottom:20px; color:#333;">No olvides registrar esta gestión</p>
                    <a href="https://pacificocia-my.sharepoint.com/:f:/g/personal/mcamino_pacifico_com_pe/EoKRHieZhB9LkpJa6tCqClYBrvHnM6LK_nUkumbFrnALug?e=utUJBJ" target="_blank">
                        <button style="background-color:#28a745; color:white; padding:15px 30px; font-size:18px; border:none; border-radius:10px; cursor:pointer; box-shadow:0 4px 8px rgba(40,167,69,0.3);">
                            📝 Registrar Gestión
                        </button>
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

    else:
        st.markdown("### 👋 Bienvenido al Sistema de Recomendación")
        st.write("Este sistema te ayudará a encontrar el plan de seguro integral más adecuado para cada cliente.")
        
        st.markdown("#### 📋 Instrucciones:")
        st.write("""
        1. **Completa la información** del cliente en el panel lateral
        2. **Indica si tiene continuidad** (viene de otro seguro)
        3. **Haz clic en 'Generar Recomendación'** para obtener el plan sugerido
        4. **Revisa los detalles** del plan recomendado
        5. **Ve a la Calculadora de Tarifas** para cotizar (datos ya cargados)
        6. **Registra la gestión** según el resultado de la propuesta
        """)
        
        # Mostrar información sobre continuidad
        st.markdown("#### ℹ️ Sobre la Continuidad:")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **Con Continuidad (Sí):**
            - ✅ Sin restricción de edad
            - ✅ Descuentos especiales (15%)
            - ✅ Más opciones de planes
            """)
        with col2:
            st.markdown("""
            **Sin Continuidad (No):**
            - ⚠️ Edad máxima 65 años (MSLD, MINT, MNAC, AM05)
            - ⚠️ Edad máxima 60 años (AM18, AM17, AM15)
            - 📊 Descuentos estándar
            """)

# ==================== MÓDULO 2: CALCULADORA DE TARIFAS ====================

elif menu == "💰 Calculadora de Tarifas":
    st.header("💰 Calculadora de Tarifas")
    
    if df_tarifas is None:
        st.error("⚠️ No se pudo cargar el archivo de tarifas. Verifica que 'tarifario_base.xlsx' esté en la carpeta correcta.")
    else:
        # NUEVO: Mostrar si hay datos pre-cargados de la recomendación
        if st.session_state.recomendacion_generada:
            st.success("✅ Datos cargados desde la recomendación anterior")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**Plan:** {st.session_state.plan_recomendado}")
            with col2:
                st.info(f"**Edad Titular:** {st.session_state.edad_titular} años")
            with col3:
                st.info(f"**Afiliados:** {st.session_state.numero_afiliados}")
            
            # Opción para resetear
            if st.button("🔄 Empezar cotización nueva", help="Limpia los datos pre-cargados"):
                st.session_state.recomendacion_generada = False
                st.session_state.plan_recomendado = None
                st.rerun()
        
        st.markdown("### 📝 Datos de la Cotización")
        
        # Selección de plan (usar el recomendado si existe)
        planes_disponibles = [col for col in df_tarifas.columns if col != 'RangoEtario']
        
        # Determinar índice por defecto
        if st.session_state.recomendacion_generada and st.session_state.plan_recomendado:
            try:
                index_default = planes_disponibles.index(st.session_state.plan_recomendado)
            except:
                index_default = 0
        else:
            index_default = 0
        
        plan_seleccionado = st.selectbox("Plan de Seguro", planes_disponibles, index=index_default)
        
        # Configuración de cuotas
        col1, col2 = st.columns(2)
        with col1:
            num_cuotas = st.selectbox("Número de Cuotas", [1, 4, 6, 10, 12], index=4)
        with col2:
            tipo_financiamiento = st.selectbox("Tipo de Financiamiento", ["Sin Interés (0%)", "Con Interés (4%)"])
            tasa_interes = 0.0 if tipo_financiamiento == "Sin Interés (0%)" else 0.04
        
        st.markdown("---")
        st.markdown("### 👥 Asegurados")
        
        # Número de asegurados (usar el de la recomendación si existe)
        num_asegurados_default = st.session_state.numero_afiliados if st.session_state.recomendacion_generada else 1
        num_asegurados = st.number_input("Número de asegurados", min_value=1, max_value=10, value=num_asegurados_default)
        
        # Recopilar datos de cada asegurado
        asegurados = []
        total_prima = 0
        
        for i in range(num_asegurados):
            st.markdown(f"#### Asegurado {i+1}")
            col1, col2 = st.columns(2)
            
            with col1:
                if i == 0:
                    # El primer asegurado siempre es Titular (no editable)
                    st.text_input(
                        f"Relación de parentesco",
                        value="Titular",
                        disabled=True,
                        key=f"rel_{i}"
                    )
                    relacion = "Titular"
                else:
                    # Los demás pueden elegir
                    relacion = st.selectbox(
                        f"Relación de parentesco",
                        ["Hijo", "Cónyuge", "Otro"],
                        key=f"rel_{i}"
                    )
            
            with col2:
                # NUEVO: Usar edad del titular si es el primero y hay recomendación
                if i == 0 and st.session_state.recomendacion_generada:
                    edad_default = st.session_state.edad_titular
                else:
                    edad_default = 30 if i == 0 else 5
                
                edad = st.number_input(
                    f"Edad",
                    min_value=0,
                    max_value=100,
                    value=edad_default,
                    key=f"edad_{i}"
                )
            
            # NUEVO: Validar edad según continuidad para el titular
            if i == 0 and st.session_state.tiene_continuidad == "No":
                es_valido, mensaje_error = validar_edad_sin_continuidad(plan_seleccionado, edad)
                if not es_valido:
                    st.error(mensaje_error)
                    st.warning("⚠️ Considera cambiar el plan o verificar si el cliente tiene continuidad")
            
            # Obtener tarifa
            es_hijo = (relacion == "Hijo")
            tarifa_base = obtener_tarifa_base(df_tarifas, plan_seleccionado, edad, es_hijo)
            
            if tarifa_base:
                # Aplicar descuento de campaña (usando la continuidad guardada)
                tarifa_desc, desc_pct, campana = aplicar_descuento_campana(
                    df_campanas, 
                    plan_seleccionado, 
                    tarifa_base, 
                    st.session_state.tiene_continuidad
                )
                
                asegurados.append({
                    'relacion': relacion,
                    'edad': edad,
                    'tarifa_base': tarifa_base,
                    'descuento_pct': desc_pct,
                    'tarifa_final': tarifa_desc,
                    'campana': campana
                })
                
                total_prima += tarifa_desc
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Prima Base", f"S/ {tarifa_base:,.2f}")
                with col2:
                    if desc_pct > 0:
                        st.metric("Descuento", f"{desc_pct}%", help=f"Campaña: {campana}")
                    else:
                        st.metric("Descuento", "0%")
                with col3:
                    st.metric("Prima Final", f"S/ {tarifa_desc:,.2f}")
            else:
                st.warning(f"⚠️ No se encontró tarifa para la edad {edad} en el plan {plan_seleccionado}")
            
            st.markdown("---")
        
        # Resumen total
        if total_prima > 0:
            st.markdown("### 💳 Resumen de Cotización")
            
            # Calcular cuota mensual
            cuota_mensual = calcular_pago_financiado(total_prima, tasa_interes, num_cuotas)
            total_financiado = cuota_mensual * num_cuotas
            costo_financiamiento = total_financiado - total_prima
            
            # Mostrar métricas
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Prima Total Anual", f"S/ {total_prima:,.2f}")
            with col2:
                st.metric("Número de Cuotas", num_cuotas)
            with col3:
                st.metric("Cuota Mensual", f"S/ {cuota_mensual:,.2f}")
            with col4:
                st.metric("Costo Financiamiento", f"S/ {costo_financiamiento:,.2f}")
            
            # Mostrar información de campaña aplicada
            if asegurados[0]['descuento_pct'] > 0:
                campana_aplicada = asegurados[0]['campana']
                tipo_campana = "Continuidad" if st.session_state.tiene_continuidad == "Sí" else "General"
                st.info(f"🎉 **Campaña aplicada:** {campana_aplicada} ({tipo_campana}) - Ahorro: S/ {(sum([a['tarifa_base'] for a in asegurados]) - total_prima):,.2f}")
            
            # Tabla detallada
            st.markdown("#### 📊 Detalle por Asegurado")
            df_resumen = pd.DataFrame(asegurados)
            df_resumen['tarifa_base'] = df_resumen['tarifa_base'].apply(lambda x: f"S/ {x:,.2f}")
            df_resumen['descuento_pct'] = df_resumen['descuento_pct'].apply(lambda x: f"{x}%")
            df_resumen['tarifa_final'] = df_resumen['tarifa_final'].apply(lambda x: f"S/ {x:,.2f}")
            df_resumen = df_resumen[['relacion', 'edad', 'tarifa_base', 'descuento_pct', 'tarifa_final']]
            df_resumen.columns = ['Relación', 'Edad', 'Prima Base', 'Descuento', 'Prima Final']
            
            st.dataframe(df_resumen, use_container_width=True)
            
            # Tabla de amortización resumida
            if num_cuotas > 1:
                st.markdown("#### 📅 Plan de Pagos")
                
                with st.expander("Ver detalle de cuotas"):
                    pagos_data = []
                    saldo = total_prima
                    
                    for i in range(num_cuotas):
                        interes = saldo * (tasa_interes / 12) if tasa_interes > 0 else 0
                        capital = cuota_mensual - interes
                        saldo -= capital
                        
                        pagos_data.append({
                            'Cuota': i + 1,
                            'Pago': f"S/ {cuota_mensual:,.2f}",
                            'Capital': f"S/ {capital:,.2f}",
                            'Interés': f"S/ {interes:,.2f}",
                            'Saldo': f"S/ {max(0, saldo):,.2f}"
                        })
                    
                    df_pagos = pd.DataFrame(pagos_data)
                    st.dataframe(df_pagos, use_container_width=True)
            
            # Botón para generar propuesta
            st.markdown("### 📄 Generar Propuesta")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📥 Descargar Propuesta en PDF", type="primary"):
                    st.info("🚧 Funcionalidad en desarrollo. Próximamente podrás descargar la propuesta en formato PDF.")
            
            with col2:
                if st.button("📧 Enviar por Email"):
                    st.info("🚧 Funcionalidad en desarrollo. Próximamente podrás enviar la propuesta por correo.")

# ==================== MÓDULO 3: CAMPAÑAS VIGENTES ====================

elif menu == "📊 Campañas Vigentes":
    st.header("📊 Campañas y Descuentos Vigentes")
    
    if df_campanas is not None and not df_campanas.empty:
        fecha_actual = datetime.now()
        
        # Filtrar campañas vigentes
        campanas_vigentes = df_campanas[
            (df_campanas['Fecha_Inicio'] <= fecha_actual) & 
            (df_campanas['Fecha_Fin'] >= fecha_actual)
        ]
        
        if not campanas_vigentes.empty:
            # Separar por tipo de campaña
            campanas_generales = campanas_vigentes[campanas_vigentes['Tipo_Campana'] == 'General']
            campanas_continuidad = campanas_vigentes[campanas_vigentes['Tipo_Campana'] == 'Continuidad']
            
            # Mostrar campañas generales
            if not campanas_generales.empty:
                st.markdown("### 🎯 Campañas Generales")
                for idx, campana in campanas_generales.iterrows():
                    st.markdown(f"#### 🎉 {campana['Nombre']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Inicio:** {campana['Fecha_Inicio'].strftime('%d/%m/%Y')}")
                    with col2:
                        st.info(f"**Fin:** {campana['Fecha_Fin'].strftime('%d/%m/%Y')}")
                    
                    st.markdown("##### 💎 Descuentos por Plan")
                    
                    # Crear columnas para mostrar descuentos
                    planes = ['MINT', 'MNAC', 'MSLD', 'AM05', 'AM18', 'AM17', 'AM15']
                    cols = st.columns(len(planes))
                    
                    for i, plan in enumerate(planes):
                        if plan in campana and pd.notna(campana[plan]) and campana[plan] > 0:
                            with cols[i]:
                                st.metric(plan, f"{campana[plan]}%")
                    
                    st.markdown("---")
            
            # Mostrar campañas de continuidad
            if not campanas_continuidad.empty:
                st.markdown("### 🔄 Campañas de Continuidad")
                st.info("✨ Estas campañas aplican solo para clientes que vienen de otro seguro de salud")
                
                for idx, campana in campanas_continuidad.iterrows():
                    st.markdown(f"#### 🎉 {campana['Nombre']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**Inicio:** {campana['Fecha_Inicio'].strftime('%d/%m/%Y')}")
                    with col2:
                        st.info(f"**Fin:** {campana['Fecha_Fin'].strftime('%d/%m/%Y')}")
                    
                    st.markdown("##### 💎 Descuentos por Plan")
                    
                    # Crear columnas para mostrar descuentos
                    planes = ['MINT', 'MNAC', 'MSLD', 'AM05', 'AM18', 'AM17', 'AM15']
                    cols = st.columns(len(planes))
                    
                    for i, plan in enumerate(planes):
                        if plan in campana and pd.notna(campana[plan]) and campana[plan] > 0:
                            with cols[i]:
                                st.metric(plan, f"{campana[plan]}%")
                    
                    st.markdown("---")
        else:
            st.warning("⚠️ No hay campañas vigentes en este momento")
            
        # Mostrar próximas campañas
        campanas_futuras = df_campanas[df_campanas['Fecha_Inicio'] > fecha_actual]
        if not campanas_futuras.empty:
            st.markdown("### 📅 Próximas Campañas")
            for idx, campana in campanas_futuras.iterrows():
                tipo_icon = "🔄" if campana['Tipo_Campana'] == 'Continuidad' else "🎯"
                st.info(f"{tipo_icon} **{campana['Nombre']}** ({campana['Tipo_Campana']}) - Inicia: {campana['Fecha_Inicio'].strftime('%d/%m/%Y')}")
    else:
        st.warning("⚠️ No se encontraron campañas configuradas")
        st.info("Para configurar campañas, crea un archivo 'campanas.xlsx' con las columnas: Nombre, Fecha_Inicio, Fecha_Fin, Tipo_Campana (General/Continuidad), y los planes con sus respectivos descuentos.")

# ==================== MÓDULO 4: RECURSOS ====================

elif menu == "📚 Recursos":
    st.header("📚 Recursos para Asesores")
    
    tab1, tab2, tab3 = st.tabs(["📄 Cartilla Comparativa", "💡 Guía de Venta", "📊 Validaciones"])
    
    with tab1:
        st.subheader("Cartilla Comparativa de Seguros Integrales 2024")
        
        if not crear_boton_descarga_pdf("Cartilla Comparativa Seguros Integrales_2024.pdf"):
            st.info("📋 La cartilla comparativa estará disponible próximamente.")
        
        st.markdown("---")
        
        if os.path.exists("Cartilla Comparativa Seguros Integrales_2024.pdf"):
            st.write("**Vista previa del documento:**")
            mostrar_pdf("Cartilla Comparativa Seguros Integrales_2024.pdf")
        else:
            st.markdown("""
            ### 📋 Información de Planes Disponibles
            
            **Planes Principales:**
            - **MNAC**: Medicvida Nacional - Plan premium con cobertura nacional amplia
            - **MINT**: Medicvida Internacional - Plan con cobertura internacional
            - **MSLD**: Multisalud - Plan estándar versátil para diferentes perfiles
            - **AM18**: Multisalud Base - Plan base con red preferente
            - **AM17**: Salud Esencial Plus - Versión mejorada del plan esencial
            - **AM15**: Salud Esencial - Plan económico con coberturas esenciales
            - **AM05**: Multisalud Base - Plan base con red preferente
            
            *La cartilla completa con coberturas detalladas estará disponible próximamente.*
            """)
    
    with tab2:
        st.subheader("🎯 Guía Rápida para Asesores")
        
        with st.expander("📞 Consejos para la Venta", expanded=True):
            st.markdown("""
            **✅ Mejores Prácticas:**
            - Enfatiza los **beneficios específicos** del plan recomendado
            - Explica las **diferencias entre planes** usando la cartilla
            - Menciona la **cobertura por dependientes**
            - Resalta las **redes de prestadores** disponibles
            - Ofrece **formas de pago flexibles**
            - Personaliza la propuesta según el **perfil del cliente**
            - **Pregunta siempre por continuidad** para maximizar descuentos
            """)
        
        with st.expander("❓ Preguntas Frecuentes"):
            st.markdown("""
            **P: ¿Qué pasa si el cliente no vive en los distritos listados?**  
            R: Se aplican las reglas de "Otros distritos" del sistema
            
            **P: ¿Qué significa continuidad?**  
            R: El cliente viene de otro seguro de salud. Con continuidad obtiene descuentos especiales (15%) y no tiene restricción de edad.
            
            **P: ¿Cuáles son las restricciones de edad sin continuidad?**  
            R: MSLD, MINT, MNAC, AM05: máximo 65 años. AM18, AM17, AM15: máximo 60 años.
            
            **P: ¿Los precios incluyen IGV?**  
            R: Verificar en la cartilla comparativa las condiciones específicas
            
            **P: ¿Se puede cambiar de plan después?**  
            R: Consultar las condiciones de modificación en la cartilla
            
            **P: ¿Cómo funciona la cobertura para dependientes?**  
            R: Cada dependiente tiene cobertura según el plan seleccionado
            """)
        
        with st.expander("🔄 Sobre la Continuidad"):
            st.markdown("""
            **¿Qué es la continuidad?**
            
            La continuidad se refiere a que el cliente viene de otro seguro de salud sin interrupciones.
            
            **Ventajas de tener continuidad:**
            - ✅ Sin restricción de edad de ingreso
            - ✅ Descuentos especiales hasta 15%
            - ✅ Más flexibilidad en la selección de planes
            - ✅ Proceso de afiliación más ágil
            
            **Documentos requeridos para continuidad:**
            - Certificado de cobertura del seguro anterior
            - Carta de no adeudo (si aplica)
            - Constancia de cese del seguro anterior
            
            **Importante:** La continuidad debe ser sin interrupciones mayores a 30 días.
            """)
    
    with tab3:
        st.subheader("📊 Tabla de Validaciones")
        
        st.markdown("""
        ### Restricciones de Edad sin Continuidad
        
        Esta tabla muestra las edades máximas permitidas para cada plan cuando el cliente NO tiene continuidad:
        """)
        
        # Crear tabla de validaciones
        validaciones_data = {
            'Plan': ['MSLD', 'MINT', 'MNAC', 'AM05', 'AM18', 'AM17', 'AM15'],
            'Nombre Comercial': [
                'Multisalud',
                'Medicvida Internacional',
                'Medicvida Nacional',
                'Multisalud Base',
                'Multisalud Base',
                'Salud Esencial Plus',
                'Salud Esencial'
            ],
            'Edad Máxima (Sin Continuidad)': [65, 65, 65, 65, 60, 60, 60],
            'Edad Máxima (Con Continuidad)': ['Sin límite'] * 7
        }
        
        df_validaciones = pd.DataFrame(validaciones_data)
        st.dataframe(df_validaciones, use_container_width=True)
        
        st.markdown("---")
        
        st.markdown("""
        ### 💡 Recomendaciones según validaciones
        
        **Si el cliente tiene más de 65 años sin continuidad:**
        - Ofrecer planes AM18, AM17 o AM15 solo si tiene 60 años o menos
        - Sugerir obtener continuidad de su seguro anterior
        - Considerar otras alternativas de seguro
        
        **Si el cliente tiene entre 60-65 años sin continuidad:**
        - Recomendar MSLD, MINT, MNAC o AM05
        - Evitar AM18, AM17 y AM15
        
        **Si el cliente tiene continuidad:**
        - ✅ Todas las edades son válidas
        - ✅ Aplicar descuento del 15%
        - ✅ Mayor flexibilidad en la selección
        """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; color:#666; font-size:12px; padding:20px;">
        🏥 Sistema de Recomendación de Productos Integrales | Pacífico Salud 2025<br>
        <em>Versión 2.0 - Con soporte de continuidad y datos persistentes entre módulos</em>
    </div>
    """,
    unsafe_allow_html=True
)
# rebuild trigger


