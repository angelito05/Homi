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

# En app.py

@app.route('/registro_proveedor', methods=['GET', 'POST'])
def registro_proveedor():
    # 1. SEGURIDAD: Solo usuarios logueados pueden entrar aquí
    if "usuario_id" not in session:
        flash("Por favor, inicia sesión como cliente antes de registrarte como proveedor.", "error")
        return redirect(url_for("home")) # O a login

    usuario_id = ObjectId(session["usuario_id"])

    # 2. PROCESAR FORMULARIO (POST)
    if request.method == 'POST':
        data = request.form.to_dict()
        
        # Preparamos solo los campos nuevos/actualizables
        datos_actualizar = {
            "telefono": data.get("telefono"),
            "codigo_postal": data.get("codigo_postal"),
            "rfc_curp": data.get("rfc_curp"),
            "nombre_inmobiliaria": data.get("inmobiliaria"),
            "url_facebook": data.get("url_facebook"),
            "url_instagram": data.get("url_instagram"),
            "url_whatsapp": data.get("url_whatsapp"),
            
            # CAMBIO DE ROL
            "rol": "proveedor",
            "verificado": False
        }

        # ACTUALIZAMOS EL REGISTRO EXISTENTE
        usuarios.update_one(
            {"_id": usuario_id},
            {"$set": datos_actualizar}
        )

        # Actualizamos la sesión
        session["rol"] = "proveedor"
        flash("¡Felicidades! Tu cuenta ahora es de Proveedor.", "success")
        return redirect(url_for("dashboard"))

    # 3. CARGAR DATOS (GET)
    usuario_db = usuarios.find_one({"_id": usuario_id})
    # Pasamos 'user' al template para que llene los inputs automáticamente
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
