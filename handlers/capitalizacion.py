import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from utils.helpers import get_now_peru, format_date_for_sheets, safe_float
from utils.sheets import append_data as append_sheets, generate_unique_id

# Configurar logging
logger = logging.getLogger(__name__)

# Estados para la conversación
MONTO, ORIGEN, DESTINO, CONCEPTO, NOTAS, CONFIRMAR = range(6)

# Datos temporales
datos_capitalizacion = {}

# Opciones predefinidas
ORIGENES = ["Fondos personales", "Préstamo bancario", "Inversionista", "Ganancias reinvertidas", "Otro"]
DESTINOS = ["Compra de café", "Gastos operativos", "Equipo", "Expansión", "Otro"]

async def capitalizacion_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de registro de capitalización"""
    user_id = update.effective_user.id
    logger.info(f"Usuario {user_id} inició comando /capitalizacion")
    
    # Inicializar datos para este usuario
    datos_capitalizacion[user_id] = {
        "registrado_por": update.effective_user.username or update.effective_user.first_name
    }
    
    await update.message.reply_text(
        "💰 *REGISTRO DE CAPITALIZACIÓN*\n\n"
        "Vamos a registrar un nuevo ingreso de capital.\n\n"
        "Por favor, ingresa el monto a capitalizar (solo el número):",
        parse_mode="Markdown"
    )
    
    return MONTO

async def monto_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el monto y solicita el origen de los fondos"""
    user_id = update.effective_user.id
    
    try:
        monto = safe_float(update.message.text)
        logger.info(f"Usuario {user_id} ingresó monto: {monto}")
        
        if monto <= 0:
            await update.message.reply_text("El monto debe ser mayor que cero. Intenta nuevamente:")
            return MONTO
        
        # Guardar el monto
        datos_capitalizacion[user_id]["monto"] = monto
        
        # Crear teclado con opciones predefinidas para origen
        keyboard = [[origen] for origen in ORIGENES]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Monto: {monto}\n\n"
            "Selecciona el origen de los fondos:",
            reply_markup=reply_markup
        )
        return ORIGEN
    except ValueError:
        logger.warning(f"Usuario {user_id} ingresó un valor inválido para monto: {update.message.text}")
        await update.message.reply_text(
            "Por favor, ingresa un número válido para el monto."
        )
        return MONTO

async def origen_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el origen y solicita el destino de los fondos"""
    user_id = update.effective_user.id
    origen = update.message.text.strip()
    logger.info(f"Usuario {user_id} seleccionó origen: {origen}")
    
    # Guardar el origen
    datos_capitalizacion[user_id]["origen"] = origen
    
    # Crear teclado con opciones predefinidas para destino
    keyboard = [[destino] for destino in DESTINOS]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Origen de fondos: {origen}\n\n"
        "Selecciona el destino/propósito de los fondos:",
        reply_markup=reply_markup
    )
    return DESTINO

async def destino_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el destino y solicita el concepto"""
    user_id = update.effective_user.id
    destino = update.message.text.strip()
    logger.info(f"Usuario {user_id} seleccionó destino: {destino}")
    
    # Guardar el destino
    datos_capitalizacion[user_id]["destino"] = destino
    
    await update.message.reply_text(
        f"Destino de fondos: {destino}\n\n"
        "Ingresa una descripción breve del motivo de la capitalización:",
        reply_markup=ReplyKeyboardRemove()
    )
    return CONCEPTO

async def concepto_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el concepto y solicita notas adicionales"""
    user_id = update.effective_user.id
    concepto = update.message.text.strip()
    logger.info(f"Usuario {user_id} ingresó concepto: {concepto}")
    
    # Verificar que no esté vacío
    if not concepto:
        await update.message.reply_text(
            "Por favor, ingresa una descripción breve para la capitalización."
        )
        return CONCEPTO
    
    # Guardar el concepto
    datos_capitalizacion[user_id]["concepto"] = concepto
    
    await update.message.reply_text(
        f"Concepto: {concepto}\n\n"
        "Si deseas, puedes añadir notas adicionales (opcional).\n"
        "Si no deseas añadir notas, escribe 'ninguna':"
    )
    return NOTAS

async def notas_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda las notas y muestra resumen para confirmación"""
    user_id = update.effective_user.id
    notas = update.message.text.strip()
    logger.info(f"Usuario {user_id} ingresó notas: {notas}")
    
    # Si el usuario escribe "ninguna", guardamos una cadena vacía
    if notas.lower() == "ninguna":
        notas = ""
    
    # Guardar las notas
    datos_capitalizacion[user_id]["notas"] = notas
    
    # Crear teclado para confirmación
    keyboard = [["Sí", "No"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    # Mostrar resumen para confirmar
    capData = datos_capitalizacion[user_id]
    await update.message.reply_text(
        "📝 *RESUMEN DE LA CAPITALIZACIÓN*\n\n"
        f"Monto: {capData['monto']}\n"
        f"Origen: {capData['origen']}\n"
        f"Destino: {capData['destino']}\n"
        f"Concepto: {capData['concepto']}\n"
        f"Notas: {notas if notas else 'Ninguna'}\n\n"
        "¿Confirmar esta capitalización?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return CONFIRMAR

async def confirmar_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma y guarda la capitalización"""
    user_id = update.effective_user.id
    respuesta = update.message.text.lower()
    logger.info(f"Usuario {user_id} respondió a confirmación: {respuesta}")
    
    if respuesta in ["sí", "si", "s", "yes", "y"]:
        # Preparar datos para guardar
        capitalizacion = datos_capitalizacion[user_id].copy()
        
        # Generar un ID único para esta capitalización
        capitalizacion["id"] = generate_unique_id()
        logger.info(f"Generado ID único para capitalización: {capitalizacion['id']}")
        
        # Añadir fecha actualizada con formato protegido para Google Sheets
        now = get_now_peru()
        fecha_formateada = now.strftime("%Y-%m-%d %H:%M")
        capitalizacion["fecha"] = format_date_for_sheets(fecha_formateada)
        
        # Verificar que todos los datos requeridos estén presentes
        campos_requeridos = ["monto", "origen", "destino", "concepto"]
        datos_completos = all(campo in capitalizacion for campo in campos_requeridos)
        
        if not datos_completos:
            campos_faltantes = [campo for campo in campos_requeridos if campo not in capitalizacion]
            logger.error(f"Datos incompletos para usuario {user_id}. Campos faltantes: {campos_faltantes}. Datos: {capitalizacion}")
            await update.message.reply_text(
                "❌ Error: Datos incompletos. Por favor, inicia el proceso nuevamente con /capitalizacion.",
                reply_markup=ReplyKeyboardRemove()
            )
            if user_id in datos_capitalizacion:
                del datos_capitalizacion[user_id]
            return ConversationHandler.END
        
        logger.info(f"Guardando capitalización en Google Sheets: {capitalizacion}")
        
        # Guardar la capitalización en Google Sheets
        try:
            # Crear objeto de datos limpio con los campos correctos
            datos_limpios = {
                "id": capitalizacion.get("id", ""),
                "fecha": capitalizacion.get("fecha", ""),
                "monto": capitalizacion.get("monto", ""),
                "origen": capitalizacion.get("origen", ""),
                "destino": capitalizacion.get("destino", ""),
                "concepto": capitalizacion.get("concepto", ""),
                "registrado_por": capitalizacion.get("registrado_por", ""),
                "notas": capitalizacion.get("notas", "")
            }
            
            # Usar append_sheets para guardar en la hoja "capitalizacion"
            result = append_sheets("capitalizacion", datos_limpios)
            
            if result:
                logger.info(f"Capitalización guardada exitosamente para usuario {user_id}")
                
                await update.message.reply_text(
                    "✅ ¡Capitalización registrada exitosamente!\n\n"
                    f"ID: {capitalizacion['id']}\n"
                    f"Monto: {capitalizacion['monto']}\n\n"
                    "Usa /capitalizacion para registrar otra capitalización.",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                logger.error(f"Error al guardar capitalización: La función append_sheets devolvió False")
                await update.message.reply_text(
                    "❌ Error al guardar la capitalización. Por favor, intenta nuevamente.\n\n"
                    "Contacta al administrador si el problema persiste.",
                    reply_markup=ReplyKeyboardRemove()
                )
        except Exception as e:
            logger.error(f"Error al guardar capitalización: {e}")
            await update.message.reply_text(
                "❌ Error al guardar la capitalización. Por favor, intenta nuevamente.\n\n"
                f"Error: {str(e)}\n\n"
                "Contacta al administrador si el problema persiste.",
                reply_markup=ReplyKeyboardRemove()
            )
    else:
        logger.info(f"Usuario {user_id} canceló la capitalización")
        await update.message.reply_text(
            "❌ Capitalización cancelada.\n\n"
            "Usa /capitalizacion para iniciar de nuevo.",
            reply_markup=ReplyKeyboardRemove()
        )
    
    # Limpiar datos temporales
    if user_id in datos_capitalizacion:
        del datos_capitalizacion[user_id]
    
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación"""
    user_id = update.effective_user.id
    logger.info(f"Usuario {user_id} canceló el proceso de capitalización con /cancelar")
    
    # Limpiar datos temporales
    if user_id in datos_capitalizacion:
        del datos_capitalizacion[user_id]
    
    await update.message.reply_text(
        "❌ Operación cancelada.\n\n"
        "Usa /capitalizacion para iniciar de nuevo cuando quieras.",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END

def register_capitalizacion_handlers(application):
    """Registra los handlers para el módulo de capitalización"""
    # Crear manejador de conversación
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("capitalizacion", capitalizacion_command)],
        states={
            MONTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, monto_step)],
            ORIGEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, origen_step)],
            DESTINO: [MessageHandler(filters.TEXT & ~filters.COMMAND, destino_step)],
            CONCEPTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, concepto_step)],
            NOTAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, notas_step)],
            CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_step)],
        },
        fallbacks=[CommandHandler("cancelar", cancelar)],
    )
    
    # Agregar el manejador al dispatcher
    application.add_handler(conv_handler)
    logger.info("Handler de capitalización registrado")
