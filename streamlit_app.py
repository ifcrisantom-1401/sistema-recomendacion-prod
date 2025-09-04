# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st
import unicodedata
import base64
import os

# Función para normalizar texto
def normalizar_texto(texto):
    texto_sin_tildes = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return texto_sin_tildes.upper()

# Función para mostrar PDF (método alternativo para evitar bloqueo de Chrome)
def mostrar_pdf(archivo_pdf):
    """Muestra un PDF en Streamlit usando un método alternativo"""
    if not os.path.exists(archivo_pdf):
        st.warning(f"El archivo {archivo_pdf} no está disponible en esta versión en la nube.")
        return False
        
    try:
        with open(archivo_pdf, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # Usar método alternativo que es más compatible con Chrome
        pdf_display = f"""
        <embed src="data:application/pdf;base64,{base64_pdf}" 
               width="100%" 
               height="600" 
               type="application/pdf">
        """
        
        st.markdown(pdf_display, unsafe_allow_html=True)
        
        # Alternativa adicional: mostrar enlace directo
        st.markdown(
            f"""
            <div style="text-align:center; margin:10px 0;">
                <p>Si no puedes ver el PDF arriba, 
                <a href="data:application/pdf;base64,{base64_pdf}" target="_blank">
                <strong>haz clic aquí para abrirlo en una nueva pestaña</strong>
                </a></p>
            </div>
            """,
            unsafe_allow_html=True
        )
        return True
    except FileNotFoundError:
        st.warning(f"No se encontró el archivo: {archivo_pdf}")
        return False
    except Exception as e:
        st.error(f"Error al cargar el PDF: {str(e)}")
        return False

# Función para crear botón de descarga del PDF
def crear_boton_descarga_pdf(archivo_pdf):
    """Crea un botón para descargar el PDF"""
    if not os.path.exists(archivo_pdf):
        st.info("La cartilla comparativa estará disponible próximamente.")
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
    except FileNotFoundError:
        st.info("La cartilla comparativa estará disponible próximamente.")
        return False

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Recomendación de Productos",
    page_icon="🏥",
    layout="wide"
)

# Imagen superior - usar una URL o imagen por defecto
try:
    if os.path.exists("pacifico.png"):
        st.image("pacifico.png", width=200)
    else:
        # Usar una imagen de placeholder o logo alternativo
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

# Sidebar para entradas
st.sidebar.header("Información del Cliente")
Edad = st.sidebar.slider("Edad", min_value=18, max_value=90, step=1)
Numero_dependientes = st.sidebar.slider("Número de afiliados", min_value=1, max_value=10, step=1)

opciones_distrito_display = [
    "Santiago de Surco", 
    "Miraflores", 
    "San Isidro", 
    "San Juan de Lurigancho", 
    "La Molina",
    "Cercado de Lima",  
    "Jesús María", 
    "San Juan de Miraflores",
    "San Borja",
    "Magdalena del Mar",
    "Pueblo Libre",
    "Otro"
]
distrito_mapping_especial = {"Cercado de Lima": "LIMA"}

Distrito_display = st.sidebar.selectbox("Selecciona el distrito", opciones_distrito_display)
if Distrito_display in distrito_mapping_especial:
    Distrito = distrito_mapping_especial[Distrito_display]
else:
    Distrito = normalizar_texto(Distrito_display)

Sexo = st.sidebar.selectbox("Sexo", ["Masculino", "Femenino"])
Tiene_Hijo_Menor = st.sidebar.selectbox("¿Incluye hijo menor de edad?", ["No", "Si"])

# Botón para generar recomendación
if st.sidebar.button("Generar Recomendación", type="primary"):

    # -----------------------------
    # REGLAS DEL PLAN
    # -----------------------------
    plan = "MSLD"

    if Distrito in ["MIRAFLORES", "SAN ISIDRO", "LA MOLINA", "SANTIAGO DE SURCO"]:
        if Sexo == "Masculino":
            plan = "MNAC" if Edad >= 30 else "MSLD"
        else:  # Mujer
            plan = "MNAC" if Edad > 30 else "MLSD"

    elif Distrito in ["LOS OLIVOS", "SAN JUAN DE LURIGANCHO", "SAN JUAN DE MIRAFLORES"]:
        if Sexo == "Femenino":
            plan = "MSLD" if Numero_dependientes >= 2 else "AM15"
        else:  # Hombre
            plan = "MSLD" if Edad > 35 else "AM15"
    else:
        if Sexo == "Femenino":
            plan = "MSLD" if Edad > 30 and Numero_dependientes >= 2 else "AM15"
        else:  # Hombre
            plan = "AM15" if Edad < 30 else "MSLD"

    # -----------------------------
    # RESULTADO EN GRANDE CON FONDO SUAVE CELESTE (SIN PRIMA)
    # -----------------------------
    st.markdown(
        f"""
        <div style="background-color:#e6f7ff; padding:30px; border-radius:15px; margin-bottom:20px; border:2px solid #00BFFF;">
            <h1 style='text-align:center; color:#00BFFF; font-weight:bold; text-shadow: 2px 2px 4px #aaa; margin-bottom:10px;'>
                🎯 PLAN RECOMENDADO: {plan}
            </h1>
            <p style='text-align:center; color:#0080ff; font-size:18px; margin-top:20px;'>
                📋 Consulta los detalles de cobertura y precios en la cartilla comparativa
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Información adicional del plan
    st.markdown("### 📋 Detalles de la Recomendación")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info(f"**Cliente:** {Sexo}, {Edad} años")
    with col2:
        st.info(f"**Afiliados:** {Numero_dependientes} persona(s)")
    with col3:
        st.info(f"**Distrito:** {Distrito_display}")

    # -----------------------------
    # FORMULARIO PARA REGISTRO DE VENTA (ACTUALIZADO)
    # -----------------------------
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
    2. **Haz clic en 'Generar Recomendación'** para obtener el plan sugerido
    3. **Revisa los detalles** del plan recomendado
    4. **Consulta la cartilla comparativa** para información de precios y coberturas
    5. **Registra la gestión** según el resultado de la propuesta
    """)
    
    # Imagen ilustrativa o placeholder
    st.markdown(
        """
        <div style="text-align:center; margin:40px 0; padding:40px; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius:15px;">
            <h3 style="color:#1565c0;">🔍 Sistema Inteligente de Recomendación</h3>
            <p style="color:#666; font-size:16px;">Utiliza algoritmos avanzados para sugerir el mejor plan según el perfil del cliente</p>
        </div>
        """,
        unsafe_allow_html=True
    )

# -----------------------------
# SECCIÓN DE DOCUMENTACIÓN ADICIONAL (SIN ESTADÍSTICAS)
# -----------------------------
st.markdown("---")
st.header("📚 Recursos para Asesores")

# Crear pestañas para organizar la información (sin la pestaña de estadísticas)
tab1, tab2 = st.tabs(["📄 Cartilla Comparativa", "💡 Guía de Venta"])

with tab1:
    st.subheader("Cartilla Comparativa de Seguros Integrales 2024")
    
    # Botón de descarga
    if not crear_boton_descarga_pdf("Cartilla Comparativa Seguros Integrales_2024.pdf"):
        st.info("📋 La cartilla comparativa se encuentra en proceso de actualización y estará disponible próximamente.")
    
    st.markdown("---")
    
    # Mostrar el PDF directamente en la aplicación si existe
    if os.path.exists("Cartilla Comparativa Seguros Integrales_2024.pdf"):
        st.write("**Vista previa del documento:**")
        mostrar_pdf("Cartilla Comparativa Seguros Integrales_2024.pdf")
    else:
        st.markdown(
            """
            ### 📋 Información de Planes Disponibles
            
            **Planes Principales:**
            - **MNAC**: Plan premium para clientes de 30+ años en distritos A
            - **MSLD**: Plan estándar versátil para diferentes perfiles
            - **MLSD**: Plan específico para mujeres jóvenes
            - **AM15**: Plan económico para perfiles específicos
            
            *La cartilla completa con coberturas detalladas estará disponible próximamente.*
            """
        )

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
        """)
    
    with st.expander("❓ Preguntas Frecuentes"):
        st.markdown("""
        **P: ¿Qué pasa si el cliente no vive en los distritos listados?**  
        R: Se aplican las reglas de "Otros distritos" del sistema
        
        **P: ¿Los precios incluyen IGV?**  
        R: Verificar en la cartilla comparativa las condiciones específicas
        
        **P: ¿Se puede cambiar de plan después?**  
        R: Consultar las condiciones de modificación en la cartilla
        
        **P: ¿Cómo funciona la cobertura para dependientes?**  
        R: Cada dependiente tiene cobertura según el plan seleccionado
        """)
    
    with st.expander("🎯 Manejo de Objeciones"):
        st.markdown("""
        **"Es muy caro"**  
        → Enfoca en el valor: cobertura vs costo, compara con gastos médicos sin seguro
        
        **"Ya tengo seguro"**  
        → Compara coberturas, beneficios adicionales, red de prestadores
        
        **"Lo voy a pensar"**  
        → Ofrece información adicional, agenda seguimiento, menciona ofertas limitadas
        """)

# Footer
st.markdown("---")
st.markdown(
    """
    <div style="text-align:center; color:#666; font-size:12px; padding:20px;">
        🏥 Sistema de Recomendación de Productos Integrales | Pacífico Seguros 2024<br>
        <em>Desarrollado para optimizar el proceso de venta y mejorar la experiencia del cliente</em>
    </div>
    """,
    unsafe_allow_html=True
)

