# Homi/consultas.py
from bson.objectid import ObjectId

# --- Cons.ultas de Propiedades ---

def obtener_propiedades_destacadas(db, limite=6):
    """
    Obtiene una lista de propiedades para mostrar en la página de inicio.
    
    En MongoDB, esto sería buscar propiedades que estén 'aprobadas' 
    y opcionalmente 'es_destacada'.
    """
    try:
        # Buscamos propiedades aprobadas y las ordenamos por fecha de publicación
        propiedades_cursor = db.Propiedades.find(
            {"estado_publicacion": "aprobada"}
        ).sort("fecha_publicacion", -1).limit(limite) # -1 para descendente

        propiedades_lista = []
        for prop in propiedades_cursor:
            # Tu esquema SQL 'ImagenesPropiedad' en Mongo probablemente sea un array.
            # Buscamos la imagen principal o tomamos la primera.
            imagen_principal = ""
            if "imagenes" in prop and len(prop["imagenes"]) > 0:
                # Intentamos buscar la que está marcada como principal
                for img in prop["imagenes"]:
                    if img.get("es_principal", False):
                        imagen_principal = img.get("url_imagen")
                        break
                # Si no hay principal, tomamos la primera
                if not imagen_principal:
                    imagen_principal = prop["imagenes"][0].get("url_imagen")
            
            # Agregamos la URL de la imagen al diccionario principal
            prop["imagen_principal_url"] = imagen_principal
            propiedades_lista.append(prop)
            
        return propiedades_lista
    
    except Exception as e:
        print(f"Error al obtener propiedades destacadas: {e}")
        return []

# --- Consultas de Usuarios (Ejemplos para futuro) ---

def obtener_usuario_por_id(db, user_id):
    """
    Obtiene un usuario por su ID de MongoDB.
    """
    try:
        return db.Usuarios.find_one({"_id": ObjectId(user_id)})
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        return None