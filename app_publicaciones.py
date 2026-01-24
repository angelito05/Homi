import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app, request
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
from config import Config
from forms import PublicacionForm 

# Definimos el Blueprint
publicaciones_bp = Blueprint('publicaciones', __name__, template_folder='src/templates', static_folder='src/static')

# Conexión a BD
client = MongoClient(Config.MONGODB_URI)
db = client["HomiDB"]
propiedades_col = db["propiedades"]

@publicaciones_bp.route('/crear-publicacion', methods=['GET', 'POST'])
def crear_publicacion():
    # 1. Seguridad de Sesión
    if 'usuario_id' not in session:
        flash("Debes iniciar sesión para publicar.", "error")
        return redirect(url_for('index'))

    form = PublicacionForm()
    
    # Datos visuales para el template
    propietario_data = {
        'nombre': session.get('nombre', 'Usuario'),
        'foto_perfil': 'images/dashboard/profile-img.png' 
    }

    if request.method == 'POST':
        print("--- [DIAGNÓSTICO] DATOS RECIBIDOS (RAW) ---")
        print(request.form) # Imprime todo lo que manda el HTML
        print("--- [DIAGNÓSTICO] LATITUD EN FORMULARIO:", form.latitud.data)

    if form.validate_on_submit():
        try:
            # Configurar carpeta de subida
            upload_folder = os.path.join(current_app.static_folder, 'images', 'uploads')
            os.makedirs(upload_folder, exist_ok=True)

            imagenes_guardadas = []
            files = [form.foto1.data, form.foto2.data, form.foto3.data, form.foto4.data, form.foto5.data]
            
            for i, file in enumerate(files):
                if file:
                    filename = secure_filename(file.filename)
                    unique_name = f"{datetime.now().timestamp()}_{i}_{filename}"
                    path_completo = os.path.join(upload_folder, unique_name)
                    file.save(path_completo)
                    
                    imagenes_guardadas.append({
                        "url_imagen": f"images/uploads/{unique_name}",
                        "es_principal": (i == 0)
                    })

            # --- AQUÍ ESTÁ LA SOLUCIÓN AL PROBLEMA DE DATOS ---
            # Convertimos explícitamente los datos al tipo que MongoDB espera
            
            try:
                precio_final = float(form.precio.data)      # Convierte a Double
                latitud_final = float(form.latitud.data)    # Convierte a Double
                longitud_final = float(form.longitud.data)  # Convierte a Double
                
                habs_final = int(form.numero_habitaciones.data or 0) # Convierte a Int
                banos_final = int(form.numero_banos.data or 0)       # Convierte a Int
                m2_final = int(form.superficie_m2.data or 0)         # Convierte a Int
            except ValueError as e:
                flash("Error en el formato de números (precio o coordenadas).", "error")
                return render_template('Publicaciones.html', form=form, propietario=propietario_data)

            # Objeto listo para MongoDB
            nueva_propiedad = {
                "id_propietario": ObjectId(session['usuario_id']),
                "titulo": form.titulo.data,
                "descripcion": form.descripcion.data,
                "tipo_operacion": form.tipo_operacion.data,
                "tipo_propiedad": form.tipo_propiedad.data,
                
                "precio": precio_final,  # <--- Ahora sí es un Double
                
                "calle": form.calle.data,
                "numero_ext_int": form.numero_ext_int.data,
                "colonia": form.colonia.data,
                "codigo_postal": form.codigo_postal.data,
                "ciudad": form.ciudad.data,
                "google_place_id": "ND",
                
                "latitud": latitud_final,   # <--- Ahora sí es un Double
                "longitud": longitud_final, # <--- Ahora sí es un Double
                
                "numero_habitaciones": habs_final, # <--- Ahora sí es Int
                "numero_banos": banos_final,       # <--- Ahora sí es Int
                "superficie_m2": m2_final,         # <--- Ahora sí es Int
                
                "estado_publicacion": "pendiente",
                "es_destacada": False,
                "fecha_destacado_expira": None,
                "disponible": True,
                "fecha_publicacion": datetime.utcnow(),
                "imagenes": imagenes_guardadas
            }

            propiedades_col.insert_one(nueva_propiedad)
            flash("¡Propiedad enviada a revisión!", "success")
            return redirect(url_for('publicaciones.crear_publicacion'))

        except Exception as e:
            flash(f"Error técnico: {str(e)}", "error")
            print(f"Error BD: {e}")
    else:
        if request.method == 'POST':
            print("--- [DIAGNÓSTICO] ERRORES DE VALIDACIÓN:", form.errors)

    # Si falla la validación, imprimimos por qué
    if form.errors:
        print("ERRORES FORMULARIO:", form.errors)

    return render_template('Publicaciones.html', form=form, propietario=propietario_data)