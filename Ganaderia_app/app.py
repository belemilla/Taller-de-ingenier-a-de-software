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

# Modelos existentes
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

# --- NUEVOS MODELOS ---
class Proveedor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))

class Alimento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text)
    stock_kg = db.Column(db.Float, nullable=False, default=0)

class Potrero(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    area_hectareas = db.Column(db.Float)
    estado_pasto = db.Column(db.String(50)) # Ej: Bueno, Regular, Malo
    ultimo_uso = db.Column(db.Date)

class Equipamiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(50)) # Ej: Operativo, En mantenimiento, Roto
    fecha_adquisicion = db.Column(db.Date)
    proximo_mantenimiento = db.Column(db.Date)


# --- RUTAS ---

# Rutas de Autenticación y Dashboards
@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_rol'] = user.rol
            if user.rol == 'Administrador':
                return redirect(url_for('dashboard_admin'))
            else:
                return redirect(url_for('dashboard_cuidador'))
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
    flash('Has cerrado la sesión.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard_admin')
def dashboard_admin():
    if 'user_id' not in session or session['user_rol'] != 'Administrador':
        flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
        return redirect(url_for('login'))
    return render_template('dashboard_admin.html')

@app.route('/dashboard_cuidador')
def dashboard_cuidador():
    if 'user_id' not in session or session['user_rol'] != 'Cuidador':
        flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
        return redirect(url_for('login'))
    ultimo_conteo = Conteo.query.filter_by(user_id=session['user_id']).order_by(Conteo.fecha_hora.desc()).first()
    return render_template('dashboard_cuidador.html', ultimo_conteo=ultimo_conteo)

# CRUD Animales
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
    flash(f'El animal {animal_a_borrar.codigo_unico} ha sido marcado como inactivo.', 'success')
    return redirect(url_for('gestionar_animales'))

# Rutas de Conteos y Alertas
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

# CRUD Usuarios
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

# CRUD Corrales
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

# CRUD Tratamientos (Historial Médico)
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
    animal_id = tratamiento_a_borrar.animal_id
    db.session.delete(tratamiento_a_borrar)
    db.session.commit()
    flash('Registro de tratamiento borrado permanentemente.', 'success')
    return redirect(url_for('historial_medico', animal_id=animal_id))

# --- NUEVAS RUTAS CRUD ---

# CRUD Proveedores
@app.route('/gestionar_proveedores')
def gestionar_proveedores():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    proveedores = Proveedor.query.all()
    return render_template('gestionar_proveedores.html', proveedores=proveedores)

@app.route('/proveedor/add', methods=['GET', 'POST'])
def add_proveedor():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        nuevo_proveedor = Proveedor(
            nombre=request.form['nombre'],
            contacto=request.form['contacto'],
            telefono=request.form['telefono'],
            direccion=request.form['direccion']
        )
        db.session.add(nuevo_proveedor)
        db.session.commit()
        flash('Proveedor añadido exitosamente.', 'success')
        return redirect(url_for('gestionar_proveedores'))
    return render_template('add_proveedor.html')

@app.route('/proveedor/edit/<int:id>', methods=['GET', 'POST'])
def edit_proveedor(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    proveedor = Proveedor.query.get_or_404(id)
    if request.method == 'POST':
        proveedor.nombre = request.form['nombre']
        proveedor.contacto = request.form['contacto']
        proveedor.telefono = request.form['telefono']
        proveedor.direccion = request.form['direccion']
        db.session.commit()
        flash('Proveedor actualizado exitosamente.', 'success')
        return redirect(url_for('gestionar_proveedores'))
    return render_template('edit_proveedor.html', proveedor=proveedor)

@app.route('/proveedor/delete/<int:id>')
def delete_proveedor(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    proveedor = Proveedor.query.get_or_404(id)
    db.session.delete(proveedor)
    db.session.commit()
    flash('Proveedor eliminado permanentemente.', 'success')
    return redirect(url_for('gestionar_proveedores'))

# CRUD Alimentos
@app.route('/gestionar_alimentos')
def gestionar_alimentos():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    alimentos = Alimento.query.all()
    return render_template('gestionar_alimentos.html', alimentos=alimentos)

@app.route('/alimento/add', methods=['GET', 'POST'])
def add_alimento():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        nuevo_alimento = Alimento(
            nombre=request.form['nombre'],
            descripcion=request.form['descripcion'],
            stock_kg=float(request.form['stock_kg'])
        )
        db.session.add(nuevo_alimento)
        db.session.commit()
        flash('Alimento añadido al inventario.', 'success')
        return redirect(url_for('gestionar_alimentos'))
    return render_template('add_alimento.html')

@app.route('/alimento/edit/<int:id>', methods=['GET', 'POST'])
def edit_alimento(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    alimento = Alimento.query.get_or_404(id)
    if request.method == 'POST':
        alimento.nombre = request.form['nombre']
        alimento.descripcion = request.form['descripcion']
        alimento.stock_kg = float(request.form['stock_kg'])
        db.session.commit()
        flash('Inventario de alimento actualizado.', 'success')
        return redirect(url_for('gestionar_alimentos'))
    return render_template('edit_alimento.html', alimento=alimento)

@app.route('/alimento/delete/<int:id>')
def delete_alimento(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    alimento = Alimento.query.get_or_404(id)
    db.session.delete(alimento)
    db.session.commit()
    flash('Alimento eliminado del inventario.', 'success')
    return redirect(url_for('gestionar_alimentos'))

# CRUD Potreros
@app.route('/gestionar_potreros')
def gestionar_potreros():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    potreros = Potrero.query.all()
    return render_template('gestionar_potreros.html', potreros=potreros)

@app.route('/potrero/add', methods=['GET', 'POST'])
def add_potrero():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        ultimo_uso = request.form['ultimo_uso']
        nuevo_potrero = Potrero(
            nombre=request.form['nombre'],
            area_hectareas=float(request.form['area_hectareas']) if request.form['area_hectareas'] else None,
            estado_pasto=request.form['estado_pasto'],
            ultimo_uso=datetime.strptime(ultimo_uso, '%Y-%m-%d').date() if ultimo_uso else None
        )
        db.session.add(nuevo_potrero)
        db.session.commit()
        flash('Potrero añadido exitosamente.', 'success')
        return redirect(url_for('gestionar_potreros'))
    return render_template('add_potrero.html')

@app.route('/potrero/edit/<int:id>', methods=['GET', 'POST'])
def edit_potrero(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    potrero = Potrero.query.get_or_404(id)
    if request.method == 'POST':
        potrero.nombre = request.form['nombre']
        potrero.area_hectareas = float(request.form['area_hectareas']) if request.form['area_hectareas'] else None
        potrero.estado_pasto = request.form['estado_pasto']
        ultimo_uso = request.form['ultimo_uso']
        potrero.ultimo_uso = datetime.strptime(ultimo_uso, '%Y-%m-%d').date() if ultimo_uso else None
        db.session.commit()
        flash('Potrero actualizado exitosamente.', 'success')
        return redirect(url_for('gestionar_potreros'))
    return render_template('edit_potrero.html', potrero=potrero)

@app.route('/potrero/delete/<int:id>')
def delete_potrero(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    potrero = Potrero.query.get_or_404(id)
    db.session.delete(potrero)
    db.session.commit()
    flash('Potrero eliminado permanentemente.', 'success')
    return redirect(url_for('gestionar_potreros'))

# CRUD Equipamiento
@app.route('/gestionar_equipamiento')
def gestionar_equipamiento():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    equipos = Equipamiento.query.all()
    return render_template('gestionar_equipamiento.html', equipos=equipos)

@app.route('/equipamiento/add', methods=['GET', 'POST'])
def add_equipamiento():
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    if request.method == 'POST':
        fecha_adquisicion = request.form['fecha_adquisicion']
        proximo_mantenimiento = request.form['proximo_mantenimiento']
        nuevo_equipo = Equipamiento(
            nombre=request.form['nombre'],
            estado=request.form['estado'],
            fecha_adquisicion=datetime.strptime(fecha_adquisicion, '%Y-%m-%d').date() if fecha_adquisicion else None,
            proximo_mantenimiento=datetime.strptime(proximo_mantenimiento, '%Y-%m-%d').date() if proximo_mantenimiento else None
        )
        db.session.add(nuevo_equipo)
        db.session.commit()
        flash('Equipo añadido exitosamente.', 'success')
        return redirect(url_for('gestionar_equipamiento'))
    return render_template('add_equipamiento.html')

@app.route('/equipamiento/edit/<int:id>', methods=['GET', 'POST'])
def edit_equipamiento(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    equipo = Equipamiento.query.get_or_404(id)
    if request.method == 'POST':
        equipo.nombre = request.form['nombre']
        equipo.estado = request.form['estado']
        fecha_adquisicion = request.form['fecha_adquisicion']
        proximo_mantenimiento = request.form['proximo_mantenimiento']
        equipo.fecha_adquisicion = datetime.strptime(fecha_adquisicion, '%Y-%m-%d').date() if fecha_adquisicion else None
        equipo.proximo_mantenimiento = datetime.strptime(proximo_mantenimiento, '%Y-%m-%d').date() if proximo_mantenimiento else None
        db.session.commit()
        flash('Equipo actualizado exitosamente.', 'success')
        return redirect(url_for('gestionar_equipamiento'))
    return render_template('edit_equipamiento.html', equipo=equipo)

@app.route('/equipamiento/delete/<int:id>')
def delete_equipamiento(id):
    if 'user_id' not in session or session['user_rol'] != 'Administrador': return redirect(url_for('login'))
    equipo = Equipamiento.query.get_or_404(id)
    db.session.delete(equipo)
    db.session.commit()
    flash('Equipo eliminado permanentemente.', 'success')
    return redirect(url_for('gestionar_equipamiento'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
