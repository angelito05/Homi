from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from config import Config
import consultas
from datetime import datetime 

app = Flask(__name__, template_folder="src/templates", static_folder="src/static")
app.config.from_object(Config)

bcrypt = Bcrypt(app)

# Conexión a MongoDB
client = MongoClient(app.config["MONGODB_URI"])
db = client["HomiDB"]
usuarios = db["usuarios"]
mongo = db


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
        # Usar el rol que viene del formulario, si no existe, por defecto "cliente"
        rol = data.get("rol", "cliente")

        # Campos obligatorios para clientes (incluyendo datos tipo proveedor)
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
    if request.method == 'POST':
        data = request.form.to_dict()
        correo = data.get("correo_electronico")
        contrasena_ingresada = data.get("contrasena")

        # 1. Buscar si el usuario ya existe
        usuario_existente = usuarios.find_one({"correo_electronico": correo})

        if usuario_existente:
            # === CASO: USUARIO EXISTENTE (CLIENTE QUE QUIERE SER PROVEEDOR) ===
            
            # Verificar contraseña para asegurar que es él
            if not bcrypt.check_password_hash(usuario_existente["contrasena"], contrasena_ingresada):
                flash("El correo ya está registrado pero la contraseña es incorrecta.", "error")
                return redirect(url_for("registro_proveedor"))
            
            # Si ya era proveedor o admin, avisar
            if usuario_existente.get("rol") in ["proveedor", "admin"]:
                flash("Ya tienes una cuenta registrada con este rol.", "info")
                return redirect(url_for("index"))

            # ACTUALIZAR ROL Y DATOS FALTANTES
            usuarios.update_one(
                {"_id": usuario_existente["_id"]},
                {
                    "$set": {
                        "rol": "proveedor",
                        "telefono": data.get("telefono"), # Actualizamos por si lo cambió
                        "nombre_inmobiliaria": data.get("inmobiliaria", ""),
                        "rfc": data.get("rfc", ""),
                        "url_facebook": data.get("url_facebook", ""),
                        "url_instagram": data.get("url_instagram", ""),
                        "url_whatsapp": data.get("url_whatsapp", ""),
                        # No tocamos la contraseña ni fecha de registro original
                    }
                }
            )
            flash("¡Tu cuenta ha sido actualizada a Proveedor exitosamente! Inicia sesión.", "success")
            return redirect(url_for("index"))

        else:
            # === CASO: USUARIO NUEVO (REGISTRO DESDE CERO) ===
            hashed_password = bcrypt.generate_password_hash(contrasena_ingresada).decode("utf-8")
            
            nuevo_proveedor = {
                "nombre": data["nombre"],
                "primer_apellido": data["primer_apellido"],
                "segundo_apellido": data.get("segundo_apellido", ""),
                "correo_electronico": correo,
                "contrasena": hashed_password,
                "telefono": data.get("telefono"),
                "rol": "proveedor", # Rol directo
                "estado": "activo",
                "fecha_registro": datetime.now(),
                
                # Datos extra de proveedor
                "nombre_inmobiliaria": data.get("inmobiliaria", ""),
                "rfc": data.get("rfc", ""),
                "url_facebook": data.get("url_facebook", ""),
                "url_instagram": data.get("url_instagram", ""),
                "url_whatsapp": data.get("url_whatsapp", "")
            }
            
            usuarios.insert_one(nuevo_proveedor)
            flash("Cuenta de proveedor creada exitosamente.", "success")
            return redirect(url_for("index"))

    # GET request: mostrar el HTML
    return render_template('registro_proveedor.html')

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
