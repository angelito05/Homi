from flask import Flask, render_template

app = Flask(__name__, 
            template_folder='src/templates', 
            static_folder='src/static')

@app.route('/')
def ver_publicaciones():
    # Simulamos un usuario propietario para la "media conexión" que pediste
    usuario_mock = {
        'nombre': 'Juan Pérez',
        'foto_perfil': 'img/default_avatar.png' # Ruta simulada
    }
    
    return render_template('Publicaciones.html', propietario=usuario_mock)

if __name__ == '__main__':
    app.run(debug=True, port=5001)