from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'clave_secreta'

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'websimple'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT usuarios.id, usuarios.email, usuarios.password, usuarios.tipo_usuario, 
                   usuarios.nombre, usuarios.apellido, profesionales.nombre_perfil 
            FROM usuarios 
            LEFT JOIN profesionales ON usuarios.id = profesionales.usuario_id
            WHERE usuarios.email = %s
        """, (email,))
        user = cursor.fetchone()
        cursor.close()
        
        if user and check_password_hash(user[2], password):
            session['userId'] = user[0]
            session['email'] = user[1]
            session['tipoUsuario'] = user[3]
            session['nombre'] = user[4]
            session['apellido'] = user[5]
            session['nombrePerfil'] = user[6]

            flash('¡Login exitoso!', 'success')
            if user[6] is None:
                return redirect(url_for('crearPerfil'))
            else:
                return redirect(url_for('perfil', nombrePerfil=session['nombrePerfil']))
        else:
            flash('Usuario o contraseña incorrecta.', 'danger')

    return render_template('index.html')

@app.route('/recuperarPassword')
def recuperarPassword():
    return render_template('recuperarPassword.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.', 'success')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        apellido = request.form['apellido']
        dni = request.form['dni']
        telefono = request.form['telefono']
        email = request.form['email']
        password = request.form['password']
        confirmPassword = request.form['confirmPassword']

        if password != confirmPassword:
            flash('Las contraseñas no coinciden', 'danger')
            return render_template('index.html', registerModalOpen=True)

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = %s", (email,))
        existingUser = cursor.fetchone()
        if existingUser:
            flash('El email ya está registrado.', 'danger')
            return render_template('index.html', registerModalOpen=True)

        passwordHash = generate_password_hash(password)
        sql = "INSERT INTO usuarios (nombre, apellido, email, password, dni, telefono) VALUES (%s, %s, %s, %s, %s, %s)"
        cursor.execute(sql, (nombre, apellido, email, passwordHash, dni, telefono))
        mysql.connection.commit()
        cursor.close()

        flash('Usuario registrado exitosamente', 'success')
        return redirect(url_for('index'))

    return render_template('index.html')

@app.route('/crearPerfil', methods=['GET', 'POST'])
def crearPerfil():
    if 'userId' not in session:
        flash('Por favor, inicia sesión para crear un perfil.', 'danger')
        return redirect(url_for('login'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, nombre FROM rubros")
        rubros = cursor.fetchall()

        if request.method == 'POST':
            rubrosSeleccionados = request.form.getlist('rubros')
            if not rubrosSeleccionados:
                flash("Debes seleccionar al menos un rubro.", "danger")
                return render_template('crearPerfil.html', rubros=rubros)

            nombrePerfil = request.form['nombrePerfil']
            descripcion = request.form.get('descripcion', '')
            genero = request.form['genero']
            telefono1 = request.form.get('telefono1', '')
            telefono2 = request.form.get('telefono2', '')
            localidad = request.form['localidad']
            partido = request.form['partido']
            provincia = request.form['provincia']
            pais = request.form['pais']
            codPostal = request.form['codPostal']

            cursor.execute(""" 
                SELECT id FROM ubicaciones WHERE localidad=%s AND partido=%s AND provincia=%s AND pais=%s AND cod_postal=%s
            """, (localidad, partido, provincia, pais, codPostal))
            ubicacion = cursor.fetchone()

            if not ubicacion:
                cursor.execute(""" 
                    INSERT INTO ubicaciones (localidad, partido, provincia, pais, cod_postal) 
                    VALUES (%s, %s, %s, %s, %s)
                """, (localidad, partido, provincia, pais, codPostal))
                mysql.connection.commit()
                ubicacionId = cursor.lastrowid
            else:
                ubicacionId = ubicacion[0]

            cursor.execute(""" 
                INSERT INTO profesionales (nombre_perfil, descripcion, genero, ubicacion_id, telefono1, telefono2, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nombrePerfil, descripcion, genero, ubicacionId, telefono1, telefono2, session['userId']))
            mysql.connection.commit()
            profesionalId = cursor.lastrowid

            for rubroId in rubrosSeleccionados:
                cursor.execute(""" 
                    INSERT INTO profesionales_rubros (profesional_id, rubro_id)
                    VALUES (%s, %s)
                """, (profesionalId, rubroId))

            mysql.connection.commit()
            flash('Perfil profesional creado exitosamente', 'success')
            return redirect(url_for('perfil', nombrePerfil=nombrePerfil))

    except Exception as e:
        mysql.connection.rollback()
        flash(f'Ocurrió un error: {e}', 'danger')
        print(f"Error al crear perfil: {e}")
    finally:
        cursor.close()
    
    return render_template('crearPerfil.html', rubros=rubros)

def timedelta_to_hours(td):
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02}:{minutes:02}"


@app.route('/<nombrePerfil>')
def perfil(nombrePerfil):
    try:
        cursor = mysql.connection.cursor()


        cursor.execute("""
            SELECT u.id, u.nombre, u.apellido, u.email, u.telefono,
                   p.nombre_perfil, p.descripcion, p.genero, p.telefono1, p.telefono2,
                   ub.localidad, ub.partido, ub.provincia, ub.pais, ub.cod_postal
            FROM usuarios u
            JOIN profesionales p ON u.id = p.usuario_id
            LEFT JOIN ubicaciones ub ON p.ubicacion_id = ub.id
            WHERE p.nombre_perfil = %s
        """, (nombrePerfil,))
        perfilData = cursor.fetchone()

        if not perfilData:
            flash("No se encontró un perfil para este usuario.", "warning")
            return redirect(url_for('crearPerfil'))

        usuario = {
            'id': perfilData[0],
            'nombre': perfilData[1],
            'apellido': perfilData[2],
            'email': perfilData[3],
            'telefono': perfilData[4],
            'nombrePerfil': perfilData[5],
            'descripcion': perfilData[6],
            'genero': perfilData[7],
            'telefono1': perfilData[8],
            'telefono2': perfilData[9],
            'localidad': perfilData[10],
            'partido': perfilData[11],
            'provincia': perfilData[12],
            'pais': perfilData[13],
            'codPostal': perfilData[14]
        }

        cursor.execute("""
            SELECT r.nombre, pr.anios_experiencia, pr.descripcion_trabajo
            FROM rubros r
            JOIN profesionales_rubros pr ON r.id = pr.rubro_id
            JOIN profesionales p ON p.id = pr.profesional_id
            WHERE p.nombre_perfil = %s
        """, (nombrePerfil,))
        rubrosData = cursor.fetchall()

        rubros = [
            {
                'nombre': rubro[0],
                'aniosExperiencia': rubro[1],
                'descripcionTrabajo': rubro[2]
            }
            for rubro in rubrosData
        ]

        cursor.execute("""
            SELECT dia_semana, 
                   hora_inicio, hora_fin, 
                   hora_inicio_2, hora_fin_2
            FROM horarios_disponibilidad 
            JOIN profesionales p ON p.id = horarios_disponibilidad.profesional_id 
            WHERE p.nombre_perfil = %s 
            ORDER BY FIELD(dia_semana, 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo');

        """, (nombrePerfil,))
        horariosData = cursor.fetchall()

        horarios = []
        for horario in horariosData:
            diaSemana = horario[0]
            horaInicio = timedelta_to_hours(horario[1])
            horaFin = timedelta_to_hours(horario[2])

            if horario[3] and horario[4]:
                horaInicio2 = timedelta_to_hours(horario[3])
                horaFin2 = timedelta_to_hours(horario[4])
                horarioString = f"{diaSemana}: {horaInicio} - {horaFin} y {horaInicio2} - {horaFin2}"
            else:
                horarioString = f"{diaSemana}: {horaInicio} - {horaFin}"

            horarios.append(horarioString)

        print(horarios)
        cursor.close()

        return render_template('perfil.html', usuario=usuario, rubros=rubros, horarios=horarios)

    except Exception as e:
        flash(f"Ocurrió un error: {e}", "danger")
        print(f"Error al obtener perfil: {e}")
    finally:
        cursor.close()

    return render_template('perfil.html', usuario=None)


@app.route('/editarPerfil/<nombrePerfil>', methods=['GET', 'POST'])
def editarPerfil(nombrePerfil):    
    if 'userId' not in session:
        flash('Por favor, inicia sesión para editar el perfil.', 'danger')
        return redirect(url_for('login'))

    try:
        cursor = mysql.connection.cursor()
        print(f"nombrePerfil: {nombrePerfil}, userId: {session['userId']}")
        cursor.execute("""
            SELECT p.nombre_perfil, p.descripcion, p.genero, p.telefono1, p.telefono2, 
                   u.localidad, u.partido, u.provincia, u.pais, u.cod_postal
            FROM profesionales p
            JOIN ubicaciones u ON p.ubicacion_id = u.id
            WHERE p.nombre_perfil = %s AND p.usuario_id = %s
        """, (nombrePerfil, session['userId']))
        perfilData = cursor.fetchone()
        print(f"perfilData: {perfilData}")

        if perfilData is None or not perfilData[0]:
            flash('No se encontró el perfil para editar.', 'warning')
            return redirect(url_for('crearPerfil'))
        
        cursor.execute("""
            SELECT rubro_id
            FROM profesionales_rubros
            WHERE profesional_id = (SELECT id FROM profesionales WHERE nombre_perfil = %s AND usuario_id = %s)
        """, (nombrePerfil, session['userId']))
        selectRubros = [r[0] for r in cursor.fetchall()]

        if request.method == 'POST':
            rubrosSeleccionados = request.form.getlist('rubros')
            if not rubrosSeleccionados:
                flash("Debes seleccionar al menos un rubro.", "danger")
                return render_template('editarPerfil.html', perfilData=perfilData, rubros=rubros, selectRubros=selectRubros)

            descripcion = request.form.get('descripcion', '')
            genero = request.form['genero']
            telefono1 = request.form.get('telefono1', '')
            telefono2 = request.form.get('telefono2', '')
            localidad = request.form['localidad']
            partido = request.form['partido']
            provincia = request.form['provincia']
            pais = request.form['pais']
            codPostal = request.form['cod_postal']

            cursor.execute("""
                UPDATE profesionales
                SET descripcion = %s, genero = %s, telefono1 = %s, telefono2 = %s
                WHERE nombre_perfil = %s AND usuario_id = %s
            """, (descripcion, genero, telefono1, telefono2, nombrePerfil, session['userId']))

            cursor.execute("""
                UPDATE ubicaciones
                SET localidad = %s, partido = %s, provincia = %s, pais = %s, cod_postal = %s
                WHERE id = (SELECT ubicacion_id FROM profesionales WHERE nombre_perfil = %s AND usuario_id = %s)
            """, (localidad, partido, provincia, pais, codPostal, nombrePerfil, session['userId']))

            cursor.execute("""
                DELETE FROM profesionales_rubros
                WHERE profesional_id = (SELECT id FROM profesionales WHERE nombre_perfil = %s AND usuario_id = %s)
            """, (nombrePerfil, session['userId']))
            for rubroId in rubrosSeleccionados:
                cursor.execute("""
                    INSERT INTO profesionales_rubros (profesional_id, rubro_id)
                    VALUES ((SELECT id FROM profesionales WHERE nombre_perfil = %s AND usuario_id = %s), %s)
                """, (nombrePerfil, session['userId'], rubroId))

            mysql.connection.commit()
            flash('Perfil actualizado exitosamente.', 'success')
            return redirect(url_for('perfil', nombrePerfil=nombrePerfil))

    except Exception as e:
        flash(f"Ocurrió un error: {e}", "danger")
        print(f"Error al editar perfil: {e}")
    finally:
        cursor.close()

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombre FROM rubros")
    rubros = cursor.fetchall()
    cursor.close()

    return render_template('editarPerfil.html', perfilData=perfilData, rubros=rubros, selectRubros=selectRubros)

@app.route('/')
def eliminarPerfil():
    return render_template('index.html')

@app.route('/terminos-de-uso')
def terminosDeUso():
    return render_template('terminosDeUso.html')

@app.route('/politicas-de-privacidad')
def politicasDePrivacidad():
    return render_template('politicasDePrivacidad.html')

@app.route('/nosotros')
def nosotros():
    return render_template('nosotros.html')

@app.route('/buscar', methods=['GET', 'POST'])
def buscar():
    cursor = mysql.connection.cursor()

    # Obtener el término de búsqueda
    buscar = request.args.get('buscar')

    # Si el campo de búsqueda está vacío, no ejecutar la consulta
    if not buscar:
        # Aquí puedes mostrar un mensaje o simplemente retornar la página en blanco
        return render_template('buscar.html', resultados=[], rubros=[])

    # Consulta base
    query = """
        SELECT p.nombre_perfil, p.descripcion, 
               CONCAT(ub.localidad, ', ', ub.partido, ', ', ub.provincia) AS ubicacion, 
               COALESCE(GROUP_CONCAT(r.nombre SEPARATOR ', '), 'Sin rubros') AS rubros
        FROM profesionales p
        LEFT JOIN ubicaciones ub ON p.ubicacion_id = ub.id
        LEFT JOIN profesionales_rubros pr ON p.id = pr.profesional_id
        LEFT JOIN rubros r ON pr.rubro_id = r.id
    """

    # Lista de parámetros para la consulta
    params = []
    query_conditions = []

    # Agregar condiciones de búsqueda con LIKE para nombre_perfil, localidad, partido, provincia y rubros
    query_conditions.append("(p.nombre_perfil LIKE %s OR ub.localidad LIKE %s OR ub.partido LIKE %s OR ub.provincia LIKE %s OR r.nombre LIKE %s)")
    params.extend([f"%{buscar}%", f"%{buscar}%", f"%{buscar}%", f"%{buscar}%", f"%{buscar}%"])

    # Si hay filtros de búsqueda, agregarlos al WHERE
    if query_conditions:
        query += " WHERE " + " AND ".join(query_conditions)

    query += " GROUP BY p.id"

    # Ejecutar la consulta
    cursor.execute(query, tuple(params))
    resultados = cursor.fetchall()
    cursor.close()

    # Formatear los resultados para pasarlos a la plantilla
    resultados_formateados = [
        {
            'nombre_perfil': resultado[0],
            'descripcion': resultado[1],
            'ubicacion': resultado[2],
            'rubro': resultado[3]
        }
        for resultado in resultados
    ]

    # Obtener la lista de rubros para el formulario de búsqueda
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, nombre FROM rubros")
    rubros = cursor.fetchall()
    cursor.close()

    return render_template('buscar.html', resultados=resultados_formateados, rubros=rubros)


if __name__ == '__main__':
    app.run(port=3000, debug=True)
