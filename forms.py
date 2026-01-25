from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, TextAreaField, SelectField, DecimalField, IntegerField, HiddenField, SubmitField
from wtforms import StringField, PasswordField, SubmitField, FileField
from wtforms.validators import DataRequired, NumberRange, Length, Email, EqualTo, Optional

print("--- [DIAGNÓSTICO] EL ARCHIVO FORMS.PY SE HA CARGADO CORRECTAMENTE ---")

class PublicacionForm(FlaskForm):
    # Campos básicos
    titulo = StringField('Título', validators=[DataRequired(message="El título es obligatorio"), Length(max=100)])
    descripcion = TextAreaField('Descripción', validators=[DataRequired(message="La descripción es obligatoria")])
    
    # Selectores (Dropdowns)
    tipo_operacion = SelectField('Tipo de Operación', choices=[('venta', 'Venta'), ('renta', 'Renta')], validators=[DataRequired()])
    tipo_propiedad = SelectField('Tipo de Propiedad', choices=[('casa', 'Casa'), ('departamento', 'Departamento'), ('terreno', 'Terreno')], validators=[DataRequired()])
    
    # Datos numéricos (Validamos que sean números positivos)
    precio = DecimalField('Precio', validators=[DataRequired(), NumberRange(min=0)])
    numero_habitaciones = IntegerField('Habitaciones', validators=[NumberRange(min=0)], default=0)
    numero_banos = IntegerField('Baños', validators=[NumberRange(min=0)], default=0)
    superficie_m2 = IntegerField('Superficie (m²)', validators=[NumberRange(min=0)], default=0)
    
    # Dirección (Validación de textos)
    calle = StringField('Calle', validators=[DataRequired()])
    numero_ext_int = StringField('Número Ext/Int', validators=[DataRequired()])
    colonia = StringField('Colonia', validators=[DataRequired()])
    codigo_postal = StringField('Código Postal', validators=[DataRequired()])
    ciudad = StringField('Ciudad', validators=[DataRequired()])
    
    # Coordenadas (Ocultos, se llenan con JS)
    latitud = HiddenField('Latitud', validators=[DataRequired()])
    longitud = HiddenField('Longitud', validators=[DataRequired()])

    # Imágenes (Validamos extensiones seguras)
    foto1 = FileField('Foto 1', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes')])
    foto2 = FileField('Foto 2', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes')])
    foto3 = FileField('Foto 3', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes')])
    foto4 = FileField('Foto 4', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes')])
    foto5 = FileField('Foto 5', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes')])

    submit = SubmitField('PUBLICAR PROPIEDAD')

class PerfilForm(FlaskForm):
    # Datos editables
    correo_electronico = StringField('Correo Electrónico', validators=[DataRequired(), Email()])
    telefono = StringField('Teléfono', validators=[DataRequired(), Length(min=10, max=15)])
    
    # Seguridad (Requerimos la contraseña actual para guardar cualquier cambio)
    contrasena_actual = PasswordField('Contraseña Actual (Requerida)', validators=[DataRequired()])
    
    # Cambio de contraseña (Opcional)
    nueva_contrasena = PasswordField('Nueva Contraseña (Opcional)', validators=[Optional(), Length(min=8)])
    confirmar_contrasena = PasswordField('Confirmar Nueva Contraseña', validators=[EqualTo('nueva_contrasena', message='Las contraseñas no coinciden')])
    
    submit = SubmitField('Guardar Cambios')
