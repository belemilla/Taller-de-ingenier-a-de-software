from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime

app = Flask(__name__)

# --- CONFIGURACIÓN Y MODELOS ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.urandom(24) 
db = SQLAlchemy(app)

class Animal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_unico = db.Column(db.String(20), unique=True, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    nombre = db.Column(db.String(100), nullable=True)
    estado = db.Column(db.String(50), nullable=False)
    tratamientos = db.relationship('Tratamiento', backref='animal', lazy=True, cascade="all, delete-orphan")

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    rol = db.Column(db.String(50), nullable=False)
    conteos = db.relationship('Conteo', backref='cuidador', lazy=True)

class Conteo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    animales_esperados = db.Column(db.Integer, nullable=False)
    animales_contados = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    alerta = db.relationship('Alerta', backref='conteo', uselist=False, cascade="all, delete-orphan")

class Alerta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mensaje = db.Column(db.Text, nullable=False)
    resuelta = db.Column(db.Boolean, default=False, nullable=False)
    conteo_id = db.Column(db.Integer, db.ForeignKey('conteo.id'), nullable=False)

class Corral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    capacidad = db.Column(db.Integer, nullable=True)
    tipo_corral = db.Column(db.String(100), nullable=True)

class Tratamiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_tratamiento = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    fecha_aplicacion = db.Column(db.Date, nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animal.id'), nullable=False)

# --- RUTAS ---
# ... (Omito el código que no cambia para brevedad) ...
@app.route('/')
def index():
    if 'user_id' not in session: return redirect(url_for('login'))
    return redirect(url_for('dashboard_admin')) if session['user_rol'] == 'Administrador' else redirect(url_for('dashboard_cuidador'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'], session['username'], session['user_rol'] = user.id, user.username, user.rol
            return redirect(url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'warning')
            return redirect(url_for('register'))
        new_user = User(username=username, password_hash=generate_password_hash(request.form['password']), rol=request.form['rol'])
        db.session.add(new_user)
        db.session.commit()
        flash('Cuenta creada exitosamente. Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
@app.route('/dashboard_admin')
def dashboard_admin():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    return render_template('dashboard_admin.html')
@app.route('/dashboard_cuidador')
def dashboard_cuidador():
    if 'user_id' not in session or session['user_rol'] != 'Cuidador': return redirect(url_for('login'))
    return render_template('dashboard_cuidador.html')
@app.route('/gestionar_animales')
def gestionar_animales():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    animales_db = Animal.query.filter(Animal.estado != 'Inactivo').all()
    return render_template('gestionar_animales.html', animales=animales_db)
@app.route('/animal/add', methods=['GET', 'POST'])
def add_animal():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        tipo = request.form['tipo']
        count = Animal.query.filter_by(tipo=tipo).count() + 1
        codigo_unico = f"{tipo[:3].upper()}-{count:03d}"
        nuevo_animal = Animal(codigo_unico=codigo_unico, tipo=tipo, nombre=request.form['nombre'] or None, estado=request.form['estado'])
        db.session.add(nuevo_animal)
        db.session.commit()
        return redirect(url_for('gestionar_animales'))
    return render_template('add_animal.html')
@app.route('/animal/edit/<int:animal_id>', methods=['GET', 'POST'])
def edit_animal(animal_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    animal_a_editar = Animal.query.get_or_404(animal_id)
    if request.method == 'POST':
        animal_a_editar.tipo, animal_a_editar.nombre, animal_a_editar.estado = request.form['tipo'], request.form['nombre'] or None, request.form['estado']
        db.session.commit()
        return redirect(url_for('gestionar_animales'))
    return render_template('edit_animal.html', animal=animal_a_editar)
@app.route('/animal/delete/<int:animal_id>')
def delete_animal(animal_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    animal_a_borrar = Animal.query.get_or_404(animal_id)
    animal_a_borrar.estado = 'Inactivo'
    db.session.commit()
    flash(f'El animal {animal_a_borrar.codigo_unico} ha sido borrado.', 'success')
    return redirect(url_for('gestionar_animales'))
@app.route('/iniciar_conteo')
def iniciar_conteo():
    if 'user_id' not in session or session['user_rol'] != 'Cuidador':
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('login'))
    animales_a_contar = Animal.query.filter_by(estado='En rebaño').all()
    return render_template('iniciar_conteo.html', animales=animales_a_contar)
@app.route('/guardar_conteo', methods=['POST'])
def guardar_conteo():
    if 'user_id' not in session or session['user_rol'] != 'Cuidador': return redirect(url_for('login'))
    ids_presentes = [int(id_str) for id_str in request.form.getlist('animales_presentes')]
    animales_esperados = Animal.query.filter_by(estado='En rebaño').all()
    ids_esperados = {animal.id for animal in animales_esperados}
    nuevo_conteo = Conteo(animales_esperados=len(ids_esperados), animales_contados=len(ids_presentes), user_id=session['user_id'])
    db.session.add(nuevo_conteo)
    if len(ids_presentes) < len(ids_esperados):
        ids_faltantes = ids_esperados - set(ids_presentes)
        animales_faltantes = Animal.query.filter(Animal.id.in_(ids_faltantes)).all()
        codigos_faltantes = ", ".join([a.codigo_unico for a in animales_faltantes])
        mensaje_alerta = f"Discrepancia en conteo. Faltan {len(ids_faltantes)} animales: {codigos_faltantes}"
        nueva_alerta = Alerta(mensaje=mensaje_alerta, conteo=nuevo_conteo)
        db.session.add(nueva_alerta)
        flash(mensaje_alerta, 'danger')
    else:
        flash('Conteo guardado exitosamente. Todos los animales están presentes.', 'success')
    db.session.commit()
    return redirect(url_for('dashboard_cuidador'))
@app.route('/gestionar_usuarios')
def gestionar_usuarios():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    users = User.query.all()
    return render_template('gestionar_usuarios.html', users=users)
@app.route('/user/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    user_a_editar = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user_a_editar.rol = request.form['rol']
        db.session.commit()
        flash(f'El rol del usuario {user_a_editar.username} ha sido actualizado.', 'success')
        return redirect(url_for('gestionar_usuarios'))
    return render_template('edit_user.html', user=user_a_editar)
@app.route('/user/delete/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if user_id == session['user_id']:
        flash('No puedes borrar tu propia cuenta.', 'danger')
        return redirect(url_for('gestionar_usuarios'))
    user_a_borrar = User.query.get_or_404(user_id)
    db.session.delete(user_a_borrar)
    db.session.commit()
    flash(f'El usuario {user_a_borrar.username} ha sido borrado permanentemente.', 'success')
    return redirect(url_for('gestionar_usuarios'))
@app.route('/ver_reportes')
def ver_reportes():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    conteos = Conteo.query.order_by(Conteo.fecha_hora.desc()).all()
    return render_template('ver_reportes.html', conteos=conteos)
@app.route('/gestionar_alertas')
def gestionar_alertas():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    alertas_activas = Alerta.query.filter_by(resuelta=False).order_by(Alerta.id.desc()).all()
    return render_template('gestionar_alertas.html', alertas=alertas_activas)
@app.route('/alerta/resolver/<int:alerta_id>')
def resolver_alerta(alerta_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    alerta_a_resolver = Alerta.query.get_or_404(alerta_id)
    alerta_a_resolver.resuelta = True
    db.session.commit()
    flash(f'La alerta #{alerta_a_resolver.id} ha sido marcada como resuelta.', 'success')
    return redirect(url_for('gestionar_alertas'))
@app.route('/gestionar_corrales')
def gestionar_corrales():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    corrales = Corral.query.all()
    return render_template('gestionar_corrales.html', corrales=corrales)
@app.route('/corral/add', methods=['GET', 'POST'])
def add_corral():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        nuevo_corral = Corral(nombre=request.form['nombre'], capacidad=request.form['capacidad'] or None, tipo_corral=request.form['tipo_corral'] or None)
        db.session.add(nuevo_corral)
        db.session.commit()
        flash(f"Corral '{nuevo_corral.nombre}' añadido exitosamente.", 'success')
        return redirect(url_for('gestionar_corrales'))
    return render_template('add_corral.html')
@app.route('/corral/edit/<int:corral_id>', methods=['GET', 'POST'])
def edit_corral(corral_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    corral_a_editar = Corral.query.get_or_404(corral_id)
    if request.method == 'POST':
        corral_a_editar.nombre, corral_a_editar.capacidad, corral_a_editar.tipo_corral = request.form['nombre'], request.form['capacidad'] or None, request.form['tipo_corral'] or None
        db.session.commit()
        flash(f"Corral '{corral_a_editar.nombre}' actualizado.", 'success')
        return redirect(url_for('gestionar_corrales'))
    return render_template('edit_corral.html', corral=corral_a_editar)
@app.route('/corral/delete/<int:corral_id>')
def delete_corral(corral_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    corral_a_borrar = Corral.query.get_or_404(corral_id)
    db.session.delete(corral_a_borrar)
    db.session.commit()
    flash(f"Corral '{corral_a_borrar.nombre}' borrado permanentemente.", 'success')
    return redirect(url_for('gestionar_corrales'))
@app.route('/animal/<int:animal_id>/historial')
def historial_medico(animal_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    animal = Animal.query.get_or_404(animal_id)
    return render_template('historial_medico.html', animal=animal)
@app.route('/animal/<int:animal_id>/add_tratamiento', methods=['GET', 'POST'])
def add_tratamiento(animal_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    animal = Animal.query.get_or_404(animal_id)
    if request.method == 'POST':
        fecha_str = request.form['fecha_aplicacion']
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        nuevo_tratamiento = Tratamiento(nombre_tratamiento=request.form['nombre_tratamiento'], descripcion=request.form['descripcion'], fecha_aplicacion=fecha, animal_id=animal.id)
        db.session.add(nuevo_tratamiento)
        db.session.commit()
        flash('Tratamiento añadido al historial exitosamente.', 'success')
        return redirect(url_for('historial_medico', animal_id=animal.id))
    return render_template('add_tratamiento.html', animal=animal)

# --- NUEVAS RUTAS PARA EDITAR Y BORRAR TRATAMIENTOS ---
@app.route('/tratamiento/edit/<int:tratamiento_id>', methods=['GET', 'POST'])
def edit_tratamiento(tratamiento_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    tratamiento_a_editar = Tratamiento.query.get_or_404(tratamiento_id)
    if request.method == 'POST':
        fecha_str = request.form['fecha_aplicacion']
        tratamiento_a_editar.fecha_aplicacion = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        tratamiento_a_editar.nombre_tratamiento = request.form['nombre_tratamiento']
        tratamiento_a_editar.descripcion = request.form['descripcion']
        db.session.commit()
        flash('Tratamiento actualizado.', 'success')
        return redirect(url_for('historial_medico', animal_id=tratamiento_a_editar.animal_id))
    return render_template('edit_tratamiento.html', tratamiento=tratamiento_a_editar)

@app.route('/tratamiento/delete/<int:tratamiento_id>')
def delete_tratamiento(tratamiento_id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    tratamiento_a_borrar = Tratamiento.query.get_or_404(tratamiento_id)
    animal_id = tratamiento_a_borrar.animal_id # Guardamos el ID del animal antes de borrar
    db.session.delete(tratamiento_a_borrar)
    db.session.commit()
    flash('Registro de tratamiento borrado permanentemente.', 'success')
    return redirect(url_for('historial_medico', animal_id=animal_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)