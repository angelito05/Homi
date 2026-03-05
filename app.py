from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from config import Config
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_limiter.util import get_remote_address
import consultas
from datetime import datetime 
from forms import PublicacionForm, PerfilForm, RegistroForm
import re
from flask_talisman import Talisman
from bson.objectid import ObjectId
from app_publicaciones import publicaciones_bp
import cloudinary
import cloudinary.uploader
import traceback
import os

app = Flask(__name__, template_folder="src/templates", static_folder="src/static")
app.config.from_object(Config)
app.register_blueprint(publicaciones_bp)

limiter = Limiter(
    get_remote_address, 
    app=app
)

csp = {
    'default-src': [
        '\'self\'',             # Solo permite recursos de tu propio dominio
        'https://res.cloudinary.com',  # Permite tus imágenes
        'https://cdn.jsdelivr.net',   # Si usas Bootstrap/JS desde CDN
    ],
    'script-src': [
        '\'self\'',
        '\'unsafe-inline\'', # Intenta evitar esto, usa archivos JS externos
        'https://cdn.jsdelivr.net'
    ],
    'style-src': [
        '\'self\'',
        '\'unsafe-inline\'', # Necesario para muchos CSS framework inline styles
        'https://cdn.jsdelivr.net'
    ]
}

entorno_produccion = os.environ.get('FLASK_ENV') == 'production'

# 3. Inicializamos Talisman con la variable dinámica
Talisman(app, content_security_policy=csp, force_https=entorno_produccion)

bcrypt = Bcrypt(app)

csrf = CSRFProtect(app)

# Conexión a MongoDB
client = MongoClient(app.config["MONGODB_URI"])
db = client["HomiDB"]
usuarios = db["usuarios"]
propiedades = db["propiedades"]
logs_col = db["log_audotoria"]
resenas = db["resenas"]
mongo = db

# --- CONFIGURACIÓN CLOUDINARY ---
cloudinary.config(
    cloud_name = app.config["CLOUDINARY_CLOUD_NAME"],
    api_key = app.config["CLOUDINARY_API_KEY"],
    api_secret = app.config["CLOUDINARY_API_SECRET"],
    secure = True
)

# --- FUNCIÓN DE AYUDA PARA VALIDAR CONTRASEÑA ---
def validar_contrasena_segura(password):
    """
    Debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial.
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[@$!%*?&#]", password):
        return False
    return True

@app.route("/")
def home():
    # Obtener hasta 9 propiedades para llenar el grid y el carrusel
    propiedades_destacadas = consultas.obtener_propiedades_destacadas(mongo, limite=9)

    # Colonias dinámicas desde MongoDB (solo Acapulco)
    colonias = propiedades.distinct("colonia", {"ciudad": "Acapulco"})
    colonias = sorted([c for c in colonias if c])

    return render_template(
        "Inicio.html",
        session=session,
        propiedades=propiedades_destacadas,
        colonias=colonias
    )


@app.route("/buscar")
def buscar():

    categoria = request.args.get("categoria", "").lower()
    localizacion = request.args.get("localizacion", "")
    keyword = request.args.get("keyword", "")
    operacion = request.args.get("operacion", "").lower()
    extra = request.args.get("extra", "")

    # Filtro base: solo Acapulco
    filtro = {
        "ciudad": "Acapulco"
    }

    # Venta / Renta
    if operacion:
        filtro["tipo_operacion"] = operacion

    # Categoría
    if categoria:
        filtro["tipo_propiedad"] = categoria

    # Más propiedades (solo si NO hay categoría)
    if extra == "mas" and not categoria:
        filtro["tipo_propiedad"] = {
            "$in": ["condominio", "local", "terreno"]
        }

    # Colonia
    if localizacion:
        filtro["colonia"] = {"$regex": f"^{localizacion}$", "$options": "i"}

    # Keyword (titulo o descripcion)
    if keyword:
        filtro["$or"] = [
            {"titulo": {"$regex": keyword, "$options": "i"}},
            {"descripcion": {"$regex": keyword, "$options": "i"}}
        ]

    resultados = list(propiedades.find(filtro))

    # --- AGREGA ESTE BLOQUE PARA LAS IMÁGENES ---
    for p in resultados:
        imagen_principal = ""
        if "imagenes" in p and len(p["imagenes"]) > 0:
            primera_img = p["imagenes"][0]
            # Verificamos si la imagen se guardó como diccionario o como texto (URL directa)
            if isinstance(primera_img, dict):
                imagen_principal = primera_img.get("url_imagen", "")
            else:
                imagen_principal = primera_img
        
        # Si no hay imagen, le ponemos una por defecto
        p["imagen_principal_url"] = imagen_principal if imagen_principal else url_for('static', filename='images/product/l-product-1.jpg')
    # ---------------------------------------------

    # Colonias dinámicas
    colonias = propiedades.distinct(
        "colonia",
        {"ciudad": "Acapulco"}
    )

    return render_template(
        "resultados.html",
        resultados=resultados,
        colonias=sorted(colonias),
        categoria=categoria,
        localizacion=localizacion,
        keyword=keyword,
        operacion=operacion,
        extra=extra
    )


# Registro de usuarios
@app.route("/registro", methods=["GET", "POST"])
def registro():
    form = RegistroForm()
    if request.method == "POST":
        data = request.form.to_dict()
        rol = "cliente"
        
        # Validar que las contraseñas coincidan
        if data["contrasena"] != data["confirmar_contrasena"]:
            flash("Las contraseñas no coinciden.", "error")
            return render_template("registro.html", data=data) 
        
        # Validar contraseña segura
        if not validar_contrasena_segura(data["contrasena"]):
            flash("La contraseña debe tener al menos 8 caracteres, una mayúscula, un número y un carácter especial (@$!%*?&#).", "error")
            return render_template("registro.html")

        # Campos obligatorios para clientes 
        campos_clientes = ["nombre", "primer_apellido", "segundo_apellido", "correo_electronico", "telefono", "contrasena"]

        # Validación de campos
        for c in campos_clientes:
            if not data.get(c):
                flash(f"El campo '{c}' es obligatorio.", "error")
                return redirect(url_for("registro"))

        # Evitar correos duplicados
        if usuarios.find_one({"correo_electronico": data["correo_electronico"]}):
            flash("El correo electrónico ya está registrado.", "error")
            return redirect(url_for("registro"))
        
        
        if form.validate_on_submit():
            email = form.email.data
            if db.usuarios.find_one({"email": email}):
                flash("El correo ya está registrado.", "danger")
                return render_template("registro.html", form=form)

        # Hash de contraseña
        hashed_password = bcrypt.generate_password_hash(data["contrasena"]).decode("utf-8")

        nuevo_usuario = {
            "nombre": form.nombre.data,
            "primer_apellido": form.primer_apellido.data,
            "correo_electronico": form.correo_electronico.data,
            "contrasena": hashed_password,
            "segundo_apellido": form.segundo_apellido.data,
            "telefono": form.telefono.data,
            "rol": "cliente",
            "estado": "activo"
        }

        result = db.usuarios.insert_one(nuevo_usuario)
        flash("Registro exitoso. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for("index"))

    # GET: mostrar formulario
    return render_template("registro.html")

def registrar_movimiento(usuario_id, accion, detalles):
    try:
        nuevo_log = {
            "id_usuario": ObjectId(usuario_id) if usuario_id else None,
            "accion": accion,
            "detalles": detalles,
            "fecha_evento": datetime.utcnow()
        }
        logs_col.insert_one(nuevo_log)
    except Exception as e:
        print(f"Error guardando log: {e}")

@app.route('/registro_proveedor', methods=['GET', 'POST'])
def registro_proveedor():
    # Si es GET, mostramos el formulario
    if request.method == 'GET':
        # Pasamos los datos de sesión (si existen) para pre-llenar
        datos_usuario = {}
        if "usuario_id" in session:
            # Buscamos los datos frescos de la BD
            import consultas # Asegúrate de tener esto o usar mongo directamente
            usuario_db = usuarios.find_one({"_id": ObjectId(session["usuario_id"])}) if "usuario_id" in session else None
            if usuario_db:
                datos_usuario = usuario_db
        
        return render_template('registro_proveedor.html', user={})

    # Si es POST (Enviaron el formulario)
    if request.method == 'POST':
        data = request.form.to_dict()
        correo = data.get("correo_electronico")
        contrasena_ingresada = data.get("contrasena")
        contrasena = data.get("contrasena")

        # Validar confirmación de contraseña (solo si está creando cuenta nueva o cambiando pass)
        if data.get("contrasena") and data["contrasena"] != data.get("confirmar_contrasena"):
             flash("Las contraseñas no coinciden.", "error")
             return render_template('registro_proveedor.html', user=data)
        
        # VALIDAR CONTRASEÑA SEGURA
        if not validar_contrasena_segura(data["contrasena"]):
            flash("La contraseña no es segura (Faltan mayúsculas, números o símbolos).", "error")
            return render_template('registro_proveedor.html', user=data)

        # 1. Buscar si el usuario ya existe
        usuario_existente = usuarios.find_one({"correo_electronico": correo})

        datos_extra = {
            "telefono": data.get("telefono"),
            "codigo_postal": data.get("codigo_postal"), # NUEVO
            "rfc_curp": data.get("rfc_curp"),           # NUEVO
            "nombre_inmobiliaria": data.get("inmobiliaria", ""),
            "url_facebook": data.get("url_facebook", ""),
            "url_instagram": data.get("url_instagram", ""),
            "url_whatsapp": data.get("url_whatsapp", ""),
            "verificado": False
        }
        if usuario_existente:
            # Usuario ya existe, actualizar datos y cambiar rol
            usuario_id = usuario_existente["_id"]

            # Actualizar datos
            usuarios.update_one(
                {"_id": usuario_id},
                {
                    "$set": {
                        **datos_extra,
                        "rol": "proveedor"
                    }
                }
            )
            registrar_movimiento(
                usuario_id, 
                "CAMBIO_ROL", 
                f"El usuario actualizó su cuenta a Proveedor. Inmobiliaria: {data.get('inmobiliaria', 'N/A')}"
            )

            # Actualizar sesión
            session["usuario_id"] = str(usuario_id)
            session["rol"] = "proveedor"

            flash("¡Felicidades! Tu cuenta ahora es de Proveedor.", "success")
            return redirect(url_for("home"))
        else:
            # Nuevo usuario, crear cuenta de proveedor
            hashed_password = bcrypt.generate_password_hash(contrasena).decode("utf-8")

            nuevo_usuario = {
                "nombre": data.get("nombre", ""),
                "primer_apellido": data.get("primer_apellido", ""),
                "segundo_apellido": data.get("segundo_apellido", ""),
                "correo_electronico": correo,
                "contrasena": hashed_password,
                "rol": "proveedor",
                "estado": "activo",
                **datos_extra
            }

            resultado = usuarios.insert_one(nuevo_usuario)
            usuario_id = resultado.inserted_id

            registrar_movimiento(
                usuario_id, 
                "CREACION_CUENTA_PROVEEDOR", 
                f"Se creó una nueva cuenta de Proveedor. Inmobiliaria: {data.get('inmobiliaria', 'N/A')}"
            )

            # Crear sesión
            session["usuario_id"] = str(usuario_id)
            session["rol"] = "proveedor"

            flash("¡Registro como Proveedor exitoso!", "success")
            return redirect(url_for("inicio"))
    # Si llegamos aquí, hubo un error
    usuario_db = data if 'data' in locals() else {}
    return render_template('registro_proveedor.html', user=usuario_db)

@app.route("/propiedad/<id_propiedad>")
def detalle_propiedad(id_propiedad):
    try:
        # 1. Buscar la propiedad
        propiedades.update_one({"_id": ObjectId(id_propiedad)}, {"$inc": {"visitas": 1}})
        prop = propiedades.find_one({"_id": ObjectId(id_propiedad)})
        if not prop:
            flash("La propiedad no existe o fue eliminada.", "error")
            return redirect(url_for('home'))

        # 2. Buscar al propietario
        propietario = usuarios.find_one({"_id": prop.get("id_propietario")})
        
        # 3. Preparar datos seguros para mostrar
        datos_propietario = {}
        if propietario:
            datos_propietario = {
                "nombre": f"{propietario.get('nombre', 'Anfitrión')} {propietario.get('primer_apellido', '')}",
                "nombre_raw": propietario.get("nombre", "U"), # Para sacar la letra inicial
                "telefono": propietario.get("telefono", "No disponible"),
                "correo": propietario.get("correo_electronico", ""),
                "fecha_registro": propietario.get("_id").generation_time.strftime('%Y'),
                "foto": propietario.get("foto_perfil", ""), # Obtiene la URL de Cloudinary si existe
                "url_facebook": propietario.get("url_facebook", ""),
                "url_instagram": propietario.get("url_instagram", ""),
                "url_whatsapp": propietario.get("url_whatsapp", "")
            }
        else:
            datos_propietario = {
                "nombre": "Usuario Desconocido",
                "nombre_raw": "U",
                "telefono": "---",
                "foto": ""
            }

        # LEER RESEÑAS DESDE LA COLECCIÓN INDEPENDIENTE ---
        comentarios_cursor = resenas.find({
            "$and": [
                {"$or": [
                    {"id_propiedad": str(id_propiedad)}, 
                    {"id_propiedad": ObjectId(id_propiedad)}
                ]},
                {"esta_eliminado": {"$ne": True}}
            ]
        }).sort("fecha_resena", -1) # Ordenamos por la fecha correcta
        
        comentarios = []
        suma_calificaciones = 0
        total_calificaciones = 0
        
        for c in comentarios_cursor:
            # Buscamos el nombre del usuario que hizo esta reseña
            usr = usuarios.find_one({"_id": c["id_usuario"]})
            nombre_usr = f"{usr.get('nombre', 'Usuario')} {usr.get('primer_apellido', '')}" if usr else "Usuario Anónimo"
            
            # Formateamos los datos para que el HTML los entienda como antes
            comentarios.append({
                "nombre_usuario": nombre_usr,
                "calificacion": c.get("puntuacion", 0),
                "comentario": c.get("comentario", ""),
                # Convertimos la fecha de la base de datos a texto legible
                "fecha": c["fecha_resena"].strftime('%d/%m/%Y %H:%M') if "fecha_resena" in c else ""
            })
            
            suma_calificaciones += c.get("puntuacion", 0)
            total_calificaciones += 1
        
        # Calcular promedio global
        promedio_calificacion = (suma_calificaciones / total_calificaciones) if total_calificaciones > 0 else 0
        
        # 4. Comprobar si está en favoritos del usuario actual
        es_favorito = False
        if "usuario_id" in session:
            usuario_actual = usuarios.find_one({"_id": ObjectId(session["usuario_id"])})
            if usuario_actual and id_propiedad in usuario_actual.get("favoritos", []):
                es_favorito = True

        return render_template("detalle_propiedad.html", 
                               prop=prop, 
                               propietario=datos_propietario,
                               comentarios=comentarios,
                               promedio_calificacion=round(promedio_calificacion, 1),
                               total_calificaciones=total_calificaciones,
                               es_favorito=es_favorito)

    except Exception as e:
        print(f"Error cargando propiedad: {e}")
        flash("Ocurrió un error al cargar la propiedad.", "error")
        return redirect(url_for('home'))       
        
@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario_id_str = session["usuario_id"]
    usuario_id_obj = ObjectId(usuario_id_str)
    usuario = usuarios.find_one({"_id": usuario_id_obj})

    if not usuario:
        session.clear()
        return redirect(url_for("home"))

    # 1. Procesar la Edición de Datos
    if request.method == 'POST':
        tipo_form = request.form.get("tipo_form")

        if tipo_form == "basico":
            # Datos generales para todos
            datos_actualizar = {
                "nombre": request.form.get("nombre", usuario.get("nombre")),
                "primer_apellido": request.form.get("primer_apellido", usuario.get("primer_apellido")),
                "telefono": request.form.get("telefono", usuario.get("telefono"))
            }

            # Si es proveedor, actualizamos también sus datos extra
            if usuario.get("rol") == "proveedor":
                datos_actualizar.update({
                    "nombre_inmobiliaria": request.form.get("inmobiliaria", ""),
                    "rfc_curp": request.form.get("rfc_curp", ""), # <--- CORREGIDO AQUÍ
                    "url_facebook": request.form.get("url_facebook", ""),
                    "url_instagram": request.form.get("url_instagram", ""),
                    "url_whatsapp": request.form.get("url_whatsapp", "")
                })

            usuarios.update_one({"_id": usuario_id_obj}, {"$set": datos_actualizar})
            flash("Datos actualizados correctamente.", "success")
            return redirect(url_for("perfil"))

        elif tipo_form == "sensible":
            pass_actual = request.form.get("contrasena_actual")
            if not bcrypt.check_password_hash(usuario["contrasena"], pass_actual):
                flash("Contraseña actual incorrecta.", "error")
                return redirect(url_for("perfil"))
            
            # (Aquí va tu lógica de cambiar correo/contraseña)
            nuevo_correo = request.form.get("correo_electronico")
            nueva_pass = request.form.get("nueva_contrasena")
            updates = {}
            if nuevo_correo and nuevo_correo != usuario.get("correo_electronico"):
                updates["correo_electronico"] = nuevo_correo
            if nueva_pass:
                updates["contrasena"] = bcrypt.generate_password_hash(nueva_pass).decode('utf-8')
            
            if updates:
                usuarios.update_one({"_id": usuario_id_obj}, {"$set": updates})
                flash("Seguridad actualizada.", "success")
            return redirect(url_for("perfil"))
        
        # --- LA FOTO DE PERFIL ---
        elif tipo_form == "foto_perfil":
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto.filename != '':
                    try:
                        # Subir a Cloudinary en una carpeta especial
                        upload_result = cloudinary.uploader.upload(
                            foto,
                            folder="homi_perfiles" 
                        )
                        url_foto = upload_result['secure_url']
                        
                        # Guardar la URL en el usuario
                        usuarios.update_one({"_id": usuario_id_obj}, {"$set": {"foto_perfil": url_foto}})
                        flash("Foto de perfil actualizada con éxito.", "success")
                    except Exception as e:
                        print(f"Error subiendo foto de perfil: {e}")
                        flash("Hubo un error al subir la foto.", "error")
                        
            return redirect(url_for("perfil"))

    # 2. Buscar Publicaciones del Proveedor 
    mis_publicaciones = []
    if usuario.get("rol") == "proveedor":
        # Buscamos tanto por String como por ObjectId para asegurar que encuentre las publicaciones
        mis_publicaciones = list(propiedades.find({
            "$or": [
                {"id_propietario": usuario_id_str},
                {"id_propietario": usuario_id_obj}
            ]
        }))
        for p in mis_publicaciones:
            imagen_principal = ""
            if "imagenes" in p and len(p["imagenes"]) > 0:
                primera_img = p["imagenes"][0]
                imagen_principal = primera_img.get("url_imagen", "") if isinstance(primera_img, dict) else primera_img
            p["imagen_principal_url"] = imagen_principal

    # 3. Buscar Favoritos
    mis_favoritos = []
    favoritos_ids_str = usuario.get("favoritos", [])
    if favoritos_ids_str:
        favoritos_ids = [ObjectId(fid) for fid in favoritos_ids_str if ObjectId.is_valid(fid)]
        mis_favoritos = list(propiedades.find({"_id": {"$in": favoritos_ids}}))
        for p in mis_favoritos:
            imagen_principal = ""
            if "imagenes" in p and len(p["imagenes"]) > 0:
                primera_img = p["imagenes"][0]
                imagen_principal = primera_img.get("url_imagen", "") if isinstance(primera_img, dict) else primera_img
            p["imagen_principal_url"] = imagen_principal

    return render_template("perfil.html", usuario=usuario, mis_publicaciones=mis_publicaciones, mis_favoritos=mis_favoritos)

@app.route('/admin_dashboard')
def admin_dashboard():
    # Verificar permisos de Admin
    if 'usuario_id' not in session or session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))

    # Pipeline para obtener los movimientos (Igual que tenías)
    pipeline = [
        {
            "$lookup": {
                "from": "Usuarios",
                "localField": "id_usuario",
                "foreignField": "_id",
                "as": "usuario_info"
            }
        },
        { "$unwind": { "path": "$usuario_info", "preserveNullAndEmptyArrays": True } },
        { "$sort": { "fecha_evento": -1 } }
    ]

    movimientos = list(logs_col.aggregate(pipeline))

    # CAMBIO IMPORTANTE: Renderizamos index.html activando el modo admin
    return render_template('index.html', movimientos=movimientos, mostrar_admin=True)

# --- RUTA DEL DASHBOARD DE PROVEEDOR ---
@app.route("/dashboard_proveedor")
def dashboard_proveedor():
    if "usuario_id" not in session or session.get("rol") != "proveedor":
        return redirect(url_for("index"))

    proveedor_id_str = session["usuario_id"]
    mis_propiedades = list(propiedades.find({
        "$or": [{"id_propietario": proveedor_id_str}, {"id_propietario": ObjectId(proveedor_id_str)}]
    }))

    ids_mis_propiedades_obj = []
    ids_mis_propiedades_str = []
    total_visitas = 0

    for p in mis_propiedades:
        total_visitas += p.get("visitas", 0) # Suma las vistas reales
        ids_mis_propiedades_obj.append(p["_id"])
        ids_mis_propiedades_str.append(str(p["_id"]))
        
        # Imagen principal (igual que antes)
        p["imagen_principal_url"] = p["imagenes"][0].get("url_imagen", "") if ("imagenes" in p and p["imagenes"] and isinstance(p["imagenes"][0], dict)) else (p["imagenes"][0] if "imagenes" in p and p["imagenes"] else "")

    # --- COMENTARIOS RECIENTES PARA EL DASHBOARD ---
    comentarios_recientes_cursor = resenas.find({
        "$and": [
            {"$or": [
                {"id_propiedad": {"$in": ids_mis_propiedades_obj}},
                {"id_propiedad": {"$in": ids_mis_propiedades_str}}
            ]},
            {"esta_eliminado": {"$ne": True}}
        ]
    }).sort("fecha_resena", -1).limit(5)
    
    comentarios_dashboard = []

    for c in comentarios_recientes_cursor:
        # 1. Ponerle el título de la propiedad al comentario
        prop_info = propiedades.find_one({
            "$or": [{"_id": ObjectId(c["id_propiedad"])}, {"_id": str(c["id_propiedad"])}]
        })
        titulo_prop = prop_info["titulo"] if prop_info else "Propiedad eliminada"
        
        # 2. Buscar el nombre de quién hizo el comentario
        usr = usuarios.find_one({"_id": c.get("id_usuario")})
        nombre_autor = f"{usr.get('nombre', 'Usuario')} {usr.get('primer_apellido', '')}" if usr else "Anónimo"
        
        # 3. Formatear la fecha/hora
        fecha_texto = c["fecha_resena"].strftime('%d/%m/%Y a las %H:%M') if "fecha_resena" in c else "Sin fecha"
        
        # 4. Guardarlo en la lista
        comentarios_dashboard.append({
            "id_propiedad": c["id_propiedad"],
            "titulo_propiedad": titulo_prop,
            "nombre_usuario": nombre_autor,
            "fecha_formateada": fecha_texto,
            "comentario_texto": c.get("comentario", ""),
            "calificacion_num": c.get("puntuacion", 5)
        })

    total_favoritos = usuarios.count_documents({"favoritos": {"$in": ids_mis_propiedades_str}})

    return render_template("dashboard_proveedor.html", 
                           total_publicaciones=len(mis_propiedades),
                           total_visitas=total_visitas,
                           total_favoritos=total_favoritos,
                           comentarios=comentarios_dashboard,
                           propiedades=mis_propiedades)

@app.route("/eliminar_propiedad/<id_propiedad>", methods=["POST"])
def eliminar_propiedad(id_propiedad):
    if "usuario_id" not in session or session.get("rol") != "proveedor":
        return redirect(url_for("index"))
    
    id_propietario_actual = session["usuario_id"]

    # Buscar propiedad PERO asegurando que el propietario sea quien hace la petición
    prop = propiedades.find_one({
        "_id": ObjectId(id_propiedad),
        "$or": [
            {"id_propietario": id_propietario_actual},
            {"id_propietario": ObjectId(id_propietario_actual)}
        ]
    })

    if not prop:
        flash("No tienes permiso o la propiedad no existe.", "error")
        return redirect(url_for("dashboard_proveedor"))
    
    # Eliminación real en la base de datos
    propiedades.delete_one({"_id": ObjectId(id_propiedad)})
    
    # También borramos sus comentarios
    db.comentarios.delete_many({"id_propiedad": id_propiedad})
    
    flash("Publicación eliminada para siempre.", "success")
    return redirect(url_for("dashboard_proveedor"))

@app.route("/editar_propiedad/<id_propiedad>", methods=["GET", "POST"])
def editar_propiedad(id_propiedad):
    if "usuario_id" not in session or session.get("rol") != "proveedor":
        return redirect(url_for("index"))
    
    id_propietario_actual = session["usuario_id"]

    # Buscar propiedad PERO asegurando que el propietario sea quien hace la petición
    prop = propiedades.find_one({
        "_id": ObjectId(id_propiedad),
        "$or": [
            {"id_propietario": id_propietario_actual},
            {"id_propietario": ObjectId(id_propietario_actual)}
        ]
    })

    if not prop:
        flash("No tienes permiso o la propiedad no existe.", "error")
        return redirect(url_for("dashboard_proveedor"))

    try:
        prop = propiedades.find_one({"_id": ObjectId(id_propiedad)})
        if not prop:
            flash("Propiedad no encontrada.", "error")
            return redirect(url_for("dashboard_proveedor"))

        if request.method == "POST":
            # Convertidor seguro
            def safe_float(val, default=0.0):
                try: 
                    return float(val) if val else default
                except ValueError: 
                    return default

            precio_final = safe_float(request.form.get("precio"), prop.get("precio", 0))
            habs_final = safe_float(request.form.get("numero_habitaciones"), prop.get("numero_habitaciones", 0))
            # FORZAMOS A QUE LOS BAÑOS SEAN ENTEROS (int) PARA CUMPLIR LA REGLA DE MONGO
            banos_final = safe_float(request.form.get("numero_banos"), prop.get("numero_banos", 0))
            m2_final = safe_float(request.form.get("superficie_m2"), prop.get("superficie_m2", 0))

            datos_actualizados = {
                "titulo": request.form.get("titulo", prop.get("titulo")),
                "descripcion": request.form.get("descripcion", prop.get("descripcion")),
                
                # CREADO NUEVO CAMPO "disponibilidad" EN VEZ DE SOBRESCRIBIR "estado_publicacion"
                "disponibilidad": request.form.get("disponibilidad", prop.get("disponibilidad", "Disponible")),
                
                "precio": precio_final,
                "numero_habitaciones": int(habs_final),
                "numero_banos": int(banos_final), # <-- Pasado a int()
                "superficie_m2": int(m2_final),
                "calle": request.form.get("calle", prop.get("calle")),
                "numero_ext_int": request.form.get("numero_ext_int", prop.get("numero_ext_int")),
                "colonia": request.form.get("colonia", prop.get("colonia")),
                "codigo_postal": request.form.get("codigo_postal", prop.get("codigo_postal")),
                "ciudad": request.form.get("ciudad", prop.get("ciudad"))
            }

            # 2. Manejo de Imágenes (Con Try-Except para evitar crash si falla Cloudinary)
            nuevas_imagenes = []
            try:
                import cloudinary.uploader
                for i in range(1, 6):
                    foto_campo = f"foto{i}"
                    if foto_campo in request.files:
                        foto = request.files[foto_campo]
                        if foto.filename != '':
                            upload_result = cloudinary.uploader.upload(foto, folder="homi_propiedades")
                            nuevas_imagenes.append({
                                "url_imagen": upload_result['secure_url'],
                                "public_id": upload_result['public_id'],
                                "es_principal": False
                            })
            except Exception as e_cloud:
                print(f"Error de Cloudinary (Ignorado para no tumbar la app): {e_cloud}")
                flash("Aviso: No se pudieron subir las imágenes. Revisa tu conexión a Cloudinary.", "error")

            # Combinar o reemplazar imágenes
            if nuevas_imagenes:
                if request.form.get("reemplazar_imagenes") == "si":
                    nuevas_imagenes[0]["es_principal"] = True
                    datos_actualizados["imagenes"] = nuevas_imagenes
                else:
                    imagenes_actuales = prop.get("imagenes", [])
                    datos_actualizados["imagenes"] = imagenes_actuales + nuevas_imagenes

            # 3. Guardar cambios en MongoDB
            propiedades.update_one({"_id": ObjectId(id_propiedad)}, {"$set": datos_actualizados})
            flash("¡Publicación actualizada con éxito!", "success")
            return redirect(url_for("dashboard_proveedor"))

        return render_template("editar_propiedad.html", prop=prop)
        
    except Exception as e:
        # ¡ESTO IMPRIMIRÁ EL ERROR EXACTO EN TU TERMINAL EN VEZ DE PANTALLA BLANCA!
        print("\n" + "="*50)
        print("ERROR CRÍTICO AL EDITAR PROPIEDAD:")
        traceback.print_exc() 
        print("="*50 + "\n")
        flash(f"Error interno: {str(e)}", "error")
        return redirect(url_for("dashboard_proveedor"))

# Login
@app.route("/index", methods=["POST", "GET"])
@limiter.limit("5 per minute", methods=["POST"])
def index():

    if request.method == "GET":
        # Si el usuario ya es admin y tiene sesión abierta, redirigir al dashboard directamente
        if session.get("rol") == "admin":
             return redirect(url_for("admin_dashboard"))
        
        # Si no, mostrar el Login (index.html en modo normal)
        return render_template("index.html", mostrar_admin=False)

    correo = request.form.get("correo_electronico")
    contrasena = request.form.get("contrasena")

    usuario = usuarios.find_one({"correo_electronico": correo})

    if not usuario:
        flash("Correo o contraseña incorrectos.", "error")
        return redirect(url_for("home"))

    if not bcrypt.check_password_hash(usuario["contrasena"], contrasena):
        flash("Correo o contraseña incorrectos.", "error")
        return redirect(url_for("home"))

    # Guardar sesión
    session["usuario_id"] = str(usuario["_id"])
    session["nombre"] = usuario["nombre"]
    session["rol"] = usuario["rol"]

    flash("Inicio de sesión exitoso", "success")

    # REDIRECCIÓN INTELIGENTE POR ROL
    if usuario["rol"] == "admin":
        return redirect(url_for("admin_dashboard"))
    
    # Usuarios normales van a su dashboard estándar
    return redirect(url_for("home"))

# --- NUEVA RUTA PARA COMENTAR Y CALIFICAR ---
@app.route("/comentar_propiedad/<id_propiedad>", methods=["POST"])
def comentar_propiedad(id_propiedad):
    # Si no está registrado, lo mandamos a iniciar sesión
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para comentar y calificar.", "error")
        return redirect(url_for("index"))

    comentario_texto = request.form.get("comentario")
    # Convertimos a entero para cumplir con bsonType: 'int' de tu esquema
    puntuacion = int(request.form.get("calificacion", 0))

    # Estructura exacta basada en tu JSON Schema
    nueva_resena = {
        "id_usuario": ObjectId(session["usuario_id"]),
        "id_propiedad": str(id_propiedad), # Guardamos como string para evitar problemas de búsqueda
        "puntuacion": puntuacion,
        "comentario": comentario_texto,
        "fecha_resena": datetime.utcnow(), # bsonType: 'date'
        "fecha_edicion": None,             # bsonType: ['date', 'null']
        "esta_eliminado": False            # bsonType: 'bool'
    }

    # Insertamos en la nueva colección
    resenas.insert_one(nueva_resena)
    
    flash("Tu calificación y comentario han sido guardados.", "success")
    return redirect(url_for('detalle_propiedad', id_propiedad=id_propiedad))


# --- NUEVA RUTA PARA FAVORITOS ---
@app.route("/toggle_favorito/<id_propiedad>", methods=["POST"])
def toggle_favorito(id_propiedad):
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario_id = ObjectId(session["usuario_id"])
    usuario = usuarios.find_one({"_id": usuario_id})
    favoritos = usuario.get("favoritos", [])

    if id_propiedad in favoritos:
        favoritos.remove(id_propiedad)
        msg = "Eliminado de favoritos"
    else:
        favoritos.append(id_propiedad)
        msg = "Agregado a favoritos"

    usuarios.update_one({"_id": usuario_id}, {"$set": {"favoritos": favoritos}})
    flash(msg, "success")
    return redirect(url_for("detalle_propiedad", id_propiedad=id_propiedad))

# --- NUEVA RUTA: VER FAVORITOS ---
@app.route("/favorites")
def mis_favoritos():
    # 1. Validar que el usuario haya iniciado sesión
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para ver tus favoritos.", "error")
        return redirect(url_for("index"))

    # 2. Buscar al usuario y obtener su lista de favoritos
    usuario_actual = usuarios.find_one({"_id": ObjectId(session["usuario_id"])})
    lista_ids_favoritos = usuario_actual.get("favoritos", [])

    # 3. Convertir los IDs de texto a ObjectId para que MongoDB los entienda
    ids_obj = []
    for fid in lista_ids_favoritos:
        try:
            ids_obj.append(ObjectId(fid))
        except:
            pass

    # 4. Buscar todas las propiedades que coincidan con esos IDs
    propiedades_favoritas = list(propiedades.find({"_id": {"$in": ids_obj}}))

    # 5. Mandar a la nueva pantalla
    return render_template("favoritos.html", propiedades=propiedades_favoritas, mis_favoritos=lista_ids_favoritos)

# Logout
@app.route("/logout")
def logout():
    session.clear()  # borra la sesión del servidor

    # fuerza expiración de cookie
    response = redirect(url_for("home"))
    response.set_cookie("session", "", expires=0)

    flash("Sesión cerrada correctamente.", "success")
    return response

if __name__ == "__main__":
    app.run(debug=False, port=5000)
