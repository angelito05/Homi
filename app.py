from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from config import Config
from flask_limiter import Limiter
from flask_wtf.csrf import CSRFProtect
from flask_limiter.util import get_remote_address
import consultas
from datetime import datetime 
from forms import PublicacionForm, PerfilForm
import re
from flask_talisman import Talisman
from bson.objectid import ObjectId
from app_publicaciones import publicaciones_bp

app = Flask(__name__, template_folder="src/templates", static_folder="src/static")
app.config.from_object(Config)
app.register_blueprint(publicaciones_bp)

limiter = Limiter(
    get_remote_address, 
    app=app
)

Talisman(app, content_security_policy=None, force_https=False)

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

        # Hash de contraseña
        hashed_password = bcrypt.generate_password_hash(data["contrasena"]).decode("utf-8")

        nuevo_usuario = {
            "nombre": data["nombre"],
            "primer_apellido": data["primer_apellido"],
            "correo_electronico": data["correo_electronico"],
            "contrasena": hashed_password,
            "segundo_apellido": data.get("segundo_apellido"),
            "telefono": data.get("telefono"),
            "rol": rol,
            "estado": "activo"
        }

        usuarios.insert_one(nuevo_usuario)
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
            return redirect(url_for("dashboard"))
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
        prop = propiedades.find_one({"_id": ObjectId(id_propiedad)})
        if not prop:
            flash("La propiedad no existe o fue eliminada.", "error")
            return redirect(url_for('home'))

        # 2. Buscar al propietario
        propietario = usuarios.find_one({"_id": prop.get("id_propietario")})
        
        datos_propietario = {}
        if propietario:
            datos_propietario = {
                "nombre": f"{propietario.get('nombre', 'Anfitrión')} {propietario.get('primer_apellido', '')}",
                "telefono": propietario.get("telefono", "No disponible"),
                "correo": propietario.get("correo_electronico", ""),
                "fecha_registro": propietario.get("_id").generation_time.strftime('%Y'),
                "foto": url_for('static', filename='images/dashboard/profile-img.png') 
            }
        else:
            datos_propietario = {
                "nombre": "Usuario Desconocido",
                "telefono": "---",
                "foto": url_for('static', filename='images/dashboard/profile-img.png')
            }

        # 3. --- NUEVO: LEER RESEÑAS DESDE LA COLECCIÓN INDEPENDIENTE ---
        # Buscamos todas las reseñas de esta propiedad que no estén eliminadas y las ordenamos de la más nueva a la más vieja
        comentarios_cursor = resenas.find({
            "id_propiedad": ObjectId(id_propiedad), 
            "esta_eliminado": False
        }).sort("fecha_resena", -1)
        
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
    # 1. Verificar Sesión
    if "usuario_id" not in session:
        return redirect(url_for("home"))

    # 2. Obtener datos
    usuario_id = ObjectId(session["usuario_id"])
    usuario = usuarios.find_one({"_id": usuario_id})

    if not usuario:
        session.clear()
        return redirect(url_for("home"))

    form = PerfilForm()

    # 3. Pre-llenar el formulario
    if request.method == 'GET':
        form.correo_electronico.data = usuario.get('correo_electronico')
        form.telefono.data = usuario.get('telefono')

    # 4. Procesar Formulario 
    if form.validate_on_submit():
        # A) Verificar que la contraseña actual sea correcta (Seguridad)
        if not bcrypt.check_password_hash(usuario["contrasena"], form.contrasena_actual.data):
            flash("La contraseña actual es incorrecta. No se guardaron cambios.", "error")
            return render_template("perfil.html", form=form, usuario=usuario)

        # B) Validar duplicidad de correo (si lo cambió)
        if form.correo_electronico.data != usuario["correo_electronico"]:
            if usuarios.find_one({"correo_electronico": form.correo_electronico.data}):
                flash("Ese correo ya está registrado por otro usuario.", "error")
                return render_template("perfil.html", form=form, usuario=usuario)

        # C) Preparar datos a actualizar
        datos_actualizar = {
            "correo_electronico": form.correo_electronico.data,
            "telefono": form.telefono.data
        }

        # D) Cambio de Contraseña (si el usuario escribió algo en 'nueva_contrasena')
        if form.nueva_contrasena.data:
            # Usamos tu función existente para validar seguridad
            if not validar_contrasena_segura(form.nueva_contrasena.data):
                flash("La nueva contraseña debe tener mayúscula, número y símbolo.", "error")
                return render_template("perfil.html", form=form, usuario=usuario)

            hashed_pw = bcrypt.generate_password_hash(form.nueva_contrasena.data).decode('utf-8')
            datos_actualizar["contrasena"] = hashed_pw

        # E) Guardar en MongoDB
        usuarios.update_one({"_id": usuario_id}, {"$set": datos_actualizar})
        flash("¡Perfil actualizado correctamente!", "success")
        return redirect(url_for("perfil"))

    return render_template("perfil.html", form=form, usuario=usuario)

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
    return redirect(url_for("dashboard"))

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("home"))

    return render_template("Inicio.html", nombre=session["nombre"], rol=session["rol"])

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
        "id_propiedad": ObjectId(id_propiedad),
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
