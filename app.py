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
    app=app, 
    default_limits=["50 per day", "15 per hour"] # Opcional: límites por defecto
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
    # Propiedades destacadas (tu lógica existente)
    propiedades_destacadas = consultas.obtener_propiedades_destacadas(mongo)

    # Colonias dinámicas desde MongoDB (solo Acapulco)
    colonias = propiedades.distinct(
        "colonia",
        {"ciudad": "Acapulco"}
    )
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
    if 'usuario_id' not in session or session.get('rol') != 'admin':
        flash("Acceso denegado.", "error")
        return redirect(url_for('home'))

    # Pipeline para unir Logs con Usuarios
    pipeline = [
        {
            "$lookup": {
                "from": "Usuarios",
                "localField": "id_usuario",
                "foreignField": "_id",
                "as": "usuario_info"
            }
        },
        # Descomponemos el array (preserveNullAndEmptyArrays para ver logs del sistema sin usuario)
        { "$unwind": { "path": "$usuario_info", "preserveNullAndEmptyArrays": True } },
        { "$sort": { "fecha_evento": -1 } }
    ]

    movimientos = list(logs_col.aggregate(pipeline))

    return render_template('admin_dashboard.html', movimientos=movimientos)

# Login
@app.route("/index", methods=["POST", "GET"])
@limiter.limit("5 per minute")
def index():

    if request.method == "GET":
        return render_template("index.html")

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
    return redirect(url_for("dashboard"))

# Dashboard
@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión primero.", "error")
        return redirect(url_for("home"))

    return render_template("Inicio.html", nombre=session["nombre"], rol=session["rol"])

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
