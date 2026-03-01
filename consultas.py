from bson.objectid import ObjectId

def obtener_propiedades_destacadas(db, limite=9):
    """
    Obtiene las propiedades más recientes publicadas en la plataforma.
    """
    try:
        # 1. Cambiamos db.Propiedades por db.propiedades (minúscula)
        # 2. Quitamos el filtro {"estado_publicacion": "aprobada"} dejándolo como {} para traer TODAS
        # 3. Ordenamos por "_id" descendente (-1) para traer siempre las más nuevas primero
        propiedades_cursor = db.propiedades.find({}).sort("_id", -1).limit(limite)

        propiedades_lista = []
        for prop in propiedades_cursor:
            imagen_principal = ""
            
            # Verificamos si tiene imágenes
            if "imagenes" in prop and len(prop["imagenes"]) > 0:
                # Buscamos si alguna está marcada como principal
                for img in prop["imagenes"]:
                    if isinstance(img, dict) and img.get("es_principal", False):
                        imagen_principal = img.get("url_imagen", "")
                        break
                
                # Si no hay principal, tomamos la primera
                if not imagen_principal:
                    primera_img = prop["imagenes"][0]
                    # Soporta si guardaste la imagen como Diccionario o como Texto directo
                    imagen_principal = primera_img.get("url_imagen", "") if isinstance(primera_img, dict) else primera_img
            
            # Guardamos la url para que el HTML la pueda leer fácilmente
            prop["imagen_principal_url"] = imagen_principal
            propiedades_lista.append(prop)
            
        return propiedades_lista
    
    except Exception as e:
        print(f"Error al obtener propiedades destacadas: {e}")
        return []

def obtener_usuario_por_id(db, user_id):
    """
    Obtiene un usuario por su ID de MongoDB.
    """
    try:
        return db.Usuarios.find_one({"_id": ObjectId(user_id)})
    except Exception as e:
        print(f"Error al obtener usuario: {e}")
        return None