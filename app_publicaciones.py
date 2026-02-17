import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, session, current_app, request
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
from config import Config
from forms import PublicacionForm 

# Definimos el Blueprint
publicaciones_bp = Blueprint('publicaciones', __name__, template_folder='src/templates', static_folder='src/static')

# Conexión a BD
client = MongoClient(Config.MONGODB_URI)
db = client["HomiDB"]
propiedades_col = db["propiedades"]
logs_col = db["log_audotoria"]

cloudinary.config(
    cloud_name = Config.CLOUDINARY_CLOUD_NAME,
    api_key = Config.CLOUDINARY_API_KEY,
    api_secret = Config.CLOUDINARY_API_SECRET,
    secure = True
)

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
        'foto_perfil': 'static/images/dashboard/profile-img.png' # Ajusté la ruta para que sea consistente
    }

    if form.validate_on_submit():
        try:
            imagenes_guardadas = []
            # Lista de campos de archivo del formulario
            files = [form.foto1.data, form.foto2.data, form.foto3.data, form.foto4.data, form.foto5.data]
            
            for i, file in enumerate(files):
                if file:
                    # --- CAMBIO PRINCIPAL: Subida a Cloudinary ---
                    # Ya no guardamos en disco local, enviamos directo a la nube
                    try:
                        upload_result = cloudinary.uploader.upload(
                            file, 
                            folder="homi_propiedades" # Carpeta dentro de Cloudinary
                        )
                        
                        # Guardamos la URL segura (HTTPS) que nos devuelve Cloudinary
                        imagenes_guardadas.append({
                            "url_imagen": upload_result['secure_url'],
                            "public_id": upload_result['public_id'], # Guardamos ID por si queremos borrarla luego
                            "es_principal": (i == 0)
                        })
                    except Exception as e_cloud:
                        print(f"Error subiendo imagen a Cloudinary: {e_cloud}")
                        flash("Error al subir una de las imágenes. Intenta de nuevo.", "error")
                        return render_template('Publicaciones.html', form=form, propietario=propietario_data)

            # Conversión de Datos (Igual que antes)
            try:
                precio_final = float(form.precio.data)
                latitud_final = float(form.latitud.data)
                longitud_final = float(form.longitud.data)
                
                habs_final = int(form.numero_habitaciones.data or 0)
                banos_final = int(form.numero_banos.data or 0)
                m2_final = int(form.superficie_m2.data or 0)
            except ValueError:
                flash("Error en el formato de números (precio o coordenadas).", "error")
                return render_template('Publicaciones.html', form=form, propietario=propietario_data)

            # Objeto para MongoDB
            nueva_propiedad = {
                "id_propietario": ObjectId(session['usuario_id']),
                "titulo": form.titulo.data,
                "descripcion": form.descripcion.data,
                "tipo_operacion": form.tipo_operacion.data,
                "tipo_propiedad": form.tipo_propiedad.data,
                "precio": precio_final,
                "calle": form.calle.data,
                "numero_ext_int": form.numero_ext_int.data,
                "colonia": form.colonia.data,
                "codigo_postal": form.codigo_postal.data,
                "ciudad": form.ciudad.data,
                "google_place_id": "ND",
                "latitud": latitud_final,
                "longitud": longitud_final,
                "numero_habitaciones": habs_final,
                "numero_banos": banos_final,
                "superficie_m2": m2_final,
                "estado_publicacion": "pendiente",
                "es_destacada": False,
                "fecha_destacado_expira": None,
                "disponible": True,
                "fecha_publicacion": datetime.utcnow(),
                
                "imagenes": imagenes_guardadas # <--- Ahora contiene URLs de Cloudinary
            }
            
            # Registrar Log
            logs_col.insert_one({
                "id_usuario": ObjectId(session['usuario_id']),
                "accion": "NUEVA_PROPIEDAD",
                "detalles": f"Publicó propiedad: {form.titulo.data} en {form.ciudad.data}. Precio: {precio_final}",
                "fecha_evento": datetime.utcnow()
            })

            # Guardar Propiedad
            propiedades_col.insert_one(nueva_propiedad)
            
            flash("¡Propiedad publicada con éxito!", "success")
            return redirect(url_for('publicaciones.crear_publicacion'))

        except Exception as e:
            flash(f"Error técnico: {str(e)}", "error")
            print(f"Error General: {e}")

    # Manejo de errores de validación
    if form.errors:
        print("ERRORES FORMULARIO:", form.errors)
        flash("Revisa los campos del formulario.", "error")

    return render_template('Publicaciones.html', form=form, propietario=propietario_data)