from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from config import Config
import consultas
from datetime import datetime 
import re
from bson.objectid import ObjectId

app = Flask(__name__, template_folder="src/templates", static_folder="src/static")
app.config.from_object(Config)

bcrypt = Bcrypt(app)

# Conexión a MongoDB
client = MongoClient(app.config["MONGODB_URI"])
db = client["HomiDB"]
usuarios = db["usuarios"]
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

# Página principal - LOGIN
@app.route("/")
def home():
    propiedades = consultas.obtener_propiedades_destacadas(mongo.db)
    
    # Pasamos la sesión completa y las propiedades a la plantilla
    return render_template('Inicio.html', session=session,propiedades=propiedades)

@app.route('/buscar')
def buscar():
    """
    Ruta para procesar la búsqueda del formulario.
    Recoge los filtros y (en un futuro) consultará la BD.
    """
    # Obtenemos los parámetros de la URL (método GET)
    categoria = request.args.get('categoria', '')
    localizacion = request.args.get('localizacion', '')
    keyword = request.args.get('keyword', '')
   
    return render_template('resultados.html', categoria=categoria, localizacion=localizacion, keyword=keyword)

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
        contrasena = data.get("contrasena")

        # Validar confirmación de contraseña (solo si está creando cuenta nueva o cambiando pass)
        if data.get("contrasena") and data["contrasena"] != data.get("confirmar_contrasena"):
             flash("Las contraseñas no coinciden.", "error")
             return render_template('registro_proveedor.html', user=data)
        
        # VALIDAR CONTRASEÑA SEGURA
        if not validar_contrasena_segura(data["contrasena"]):
            flash("La contraseña no es segura (Faltan mayúsculas, números o símbolos).", "error")
            return render_template('registro_proveedor.html', user=data)

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
            # Validar que la contraseña coincida con la de la BD para confirmar identidad
            if not bcrypt.check_password_hash(usuario_existente["contrasena"], contrasena):
                flash("Contraseña incorrecta. Para convertir tu cuenta, ingresa tu contraseña actual.", "error")
                return render_template('registro_proveedor.html', user=data)

            # Actualizar rol y datos
            usuarios.update_one(
                {"_id": usuario_existente["_id"]},
                {
                    "$set": {
                        "rol": "proveedor",
                        **datos_extra # Desempaqueta los datos extra aquí
                    }
                }
            )
            # Actualizar sesión para que el cambio de rol se refleje inmediatamente
            session["rol"] = "proveedor"
            flash("¡Felicidades! Ahora eres proveedor.", "success")
            return redirect(url_for("home")) # Redirigir a Home (Inicio)

        else:
            # Usuario Nuevo
            hashed_password = bcrypt.generate_password_hash(contrasena).decode("utf-8")
            nuevo_proveedor = {
                "nombre": data["nombre"],
                "primer_apellido": data["primer_apellido"],
                "segundo_apellido": data.get("segundo_apellido", ""),
                "correo_electronico": correo,
                "contrasena": hashed_password,
                "rol": "proveedor",
                "estado": "activo",
                "fecha_registro": datetime.now(),
                **datos_extra
            }
            usuarios.insert_one(nuevo_proveedor)
            flash("Registro de proveedor exitoso.", "success")
            return redirect(url_for("index"))

# Login
@app.route("/index", methods=["POST", "GET"])
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
