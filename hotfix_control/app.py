import os
from datetime import datetime, timezone
from io import BytesIO
import bcrypt
import pandas as pd
import streamlit as st
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from db import Session, init_db, User, Machine, Campaign, Patch, Event, utcnow

st.set_page_config(page_title='Hotfix Control | CI', page_icon='🛡️', layout='wide')
st.markdown('''<style>.block-container{padding-top:1.5rem;max-width:1450px}h1{letter-spacing:-.03em}div[data-testid="stMetric"]{background:#f4f6f9;border-radius:12px;padding:15px}</style>''', unsafe_allow_html=True)
NETWORKS = ['Red Corporativa', 'Red de Servicios', 'Red de Control']
STATUSES = ['Pendiente', 'Contactando con responsable', 'Primer reinicio', 'Aplicando parches', 'Reiniciando tras aplicación', 'Verificando servicios', 'Finalizado', 'Incidencia / Bloqueado']
METHODS = ['Manual', 'WSUS', 'BladeLogic']
MONTHS = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def current_user():
    uid = st.session_state.get('uid')
    if not uid:
        return None
    with Session() as db:
        return db.get(User, uid)

def audit(db, patch, actor, old, comment=''):
    db.add(Event(patch_id=patch.id, actor=actor, old_status=old, new_status=patch.status, comment=comment))

def setup():
    with Session() as db:
        if db.scalar(select(func.count(User.id))) == 0:
            st.title('Configuración inicial')
            st.info('Crea el primer administrador. Configura PostgreSQL antes de iniciar la aplicación.')
            with st.form('setup'):
                username = st.text_input('Usuario administrador')
                password = st.text_input('Contraseña (mínimo 12 caracteres)', type='password')
                confirm = st.text_input('Confirmar contraseña', type='password')
                submitted = st.form_submit_button('Crear administrador')
            if submitted:
                if not username.strip() or len(password) < 12 or password != confirm:
                    st.error('Revisa usuario y contraseñas (mínimo 12 caracteres).')
                else:
                    db.add(User(username=username.strip(), password_hash=hash_password(password), role='admin'))
                    db.commit()
                    st.success('Administrador creado. Inicia sesión.')
                    st.rerun()
            st.stop()

def login():
    st.title('🛡️ Hotfix Control')
    st.caption('Gestión de campañas de parcheo · Acceso restringido')
    with st.form('login'):
        username = st.text_input('Usuario')
        password = st.text_input('Contraseña', type='password')
        submitted = st.form_submit_button('Entrar')
    if submitted:
        with Session() as db:
            user = db.scalar(select(User).where(User.username == username.strip(), User.active == 1))
            if user and verify(password, user.password_hash):
                st.session_state.uid = user.id
                st.rerun()
        st.error('Credenciales incorrectas.')
    st.stop()

init_db()
setup()
user = current_user()
if not user or not user.active:
    st.session_state.pop('uid', None)
    login()
admin = user.role == 'admin'
with st.sidebar:
    st.title('🛡️ Hotfix Control')
    st.caption(f'Conectado: {user.username} · {user.role}')
    pages = ['Dashboard', 'Inventario', 'Campañas', 'Seguimiento', 'Histórico', 'Informes'] + (['Usuarios'] if admin else [])
    page = st.radio('Navegación', pages)
    if st.button('Cerrar sesión'):
        st.session_state.pop('uid', None)
        st.rerun()

if page == 'Dashboard':
    st.title('Panel de control')
    with Session() as db:
        campaigns = db.scalars(select(Campaign).order_by(Campaign.year.desc(), Campaign.month.desc(), Campaign.id.desc())).all()
        if not campaigns:
            st.info('Crea una campaña en el apartado Campañas para comenzar.')
        else:
            chosen = st.selectbox('Campaña', campaigns, format_func=lambda c: f'{c.name} · {MONTHS[c.month-1]} {c.year}')
            rows = db.execute(select(Patch, Machine).join(Machine, Patch.machine_id == Machine.id).where(Patch.campaign_id == chosen.id)).all()
            total = len(rows)
            done = sum(p.status == 'Finalizado' for p,m in rows)
            blocked = sum(p.status == 'Incidencia / Bloqueado' for p,m in rows)
            a,b,c,d = st.columns(4)
            a.metric('Equipos planificados', total)
            b.metric('Finalizados', done)
            c.metric('En curso', sum(p.status not in ('Pendiente','Finalizado','Incidencia / Bloqueado') for p,m in rows))
            d.metric('Incidencias', blocked)
            st.progress(done / total if total else 0, text=f'{done}/{total} finalizados')
            for network in NETWORKS:
                subset = [p for p,m in rows if m.network == network]
                complete = sum(p.status == 'Finalizado' for p in subset)
                st.write(f'**{network}** · {complete}/{len(subset)}')
                st.progress(complete / len(subset) if subset else 0)

elif page == 'Inventario':
    st.title('Inventario de equipos')
    with Session() as db:
        machines = db.scalars(select(Machine).order_by(Machine.hostname)).all()
        st.dataframe(pd.DataFrame([{'ID':m.id,'Hostname':m.hostname,'IP':m.ip,'Red':m.network,'Responsable':m.responsible,'Contacto':m.contact,'Observaciones':m.notes,'Activo':bool(m.active)} for m in machines]), use_container_width=True, hide_index=True)
        if admin:
            st.subheader('Alta / edición de equipo')
            ids = [0] + [m.id for m in machines]
            selected = st.selectbox('Equipo', ids, format_func=lambda x: 'Nuevo equipo' if x == 0 else next(m.hostname for m in machines if m.id == x))
            existing = next((m for m in machines if m.id == selected), None)
            with st.form('machine'):
                hostname = st.text_input('Hostname', value=existing.hostname if existing else '')
                ip = st.text_input('Dirección IP', value=existing.ip if existing else '')
                network = st.selectbox('Red', NETWORKS, index=NETWORKS.index(existing.network) if existing else 0)
                responsible = st.text_input('Responsable', value=existing.responsible if existing else '')
                contact = st.text_input('Contacto', value=existing.contact if existing else '')
                notes = st.text_area('Observaciones', value=existing.notes if existing else '')
                active = st.checkbox('Equipo activo', value=bool(existing.active) if existing else True)
                save = st.form_submit_button('Guardar equipo')
            if save:
                if not hostname.strip():
                    st.error('El hostname es obligatorio.')
                else:
                    m = db.get(Machine, selected) if selected else Machine()
                    m.hostname, m.ip, m.network = hostname.strip(), ip.strip(), network
                    m.responsible, m.contact, m.notes, m.active = responsible, contact, notes, int(active)
                    db.add(m)
                    try:
                        db.commit()
                        st.success('Equipo guardado.')
                        st.rerun()
                    except IntegrityError:
                        db.rollback()
                        st.error('El hostname ya existe.')

elif page == 'Campañas':
    st.title('Campañas mensuales')
    with Session() as db:
        campaigns = db.scalars(select(Campaign).order_by(Campaign.year.desc(), Campaign.month.desc())).all()
        st.dataframe(pd.DataFrame([{'ID':c.id,'Campaña':c.name,'Mes':MONTHS[c.month-1],'Año':c.year} for c in campaigns]), use_container_width=True, hide_index=True)
        if admin:
            with st.expander('Crear campaña', expanded=not bool(campaigns)):
                with st.form('newcampaign'):
                    name = st.text_input('Nombre', value='Hotfixes mensual')
                    month = st.selectbox('Mes', range(1,13), index=datetime.now().month-1, format_func=lambda m: MONTHS[m-1])
                    year = st.number_input('Año', min_value=2020, max_value=2100, value=datetime.now().year)
                    save = st.form_submit_button('Crear')
                if save and name.strip():
                    db.add(Campaign(name=name.strip(),month=int(month),year=int(year)))
                    db.commit()
                    st.rerun()
            if campaigns:
                chosen = st.selectbox('Selecciona campaña para añadir equipos', campaigns, format_func=lambda c:f'{c.name} · {MONTHS[c.month-1]} {c.year}')
                already = set(db.scalars(select(Patch.machine_id).where(Patch.campaign_id == chosen.id)).all())
                available = db.scalars(select(Machine).where(Machine.active == 1).order_by(Machine.hostname)).all()
                available = [m for m in available if m.id not in already]
                selected = st.multiselect('Máquinas a incorporar', available, format_func=lambda m:f'{m.hostname} · {m.network}')
                if st.button('Añadir equipos seleccionados', disabled=not selected):
                    for m in selected:
                        db.add(Patch(campaign_id=chosen.id, machine_id=m.id, patch_month=f'{MONTHS[chosen.month-1]} {chosen.year}'))
                    db.commit()
                    st.success(f'Añadidos {len(selected)} equipos.')
                    st.rerun()

elif page == 'Seguimiento':
    st.title('Seguimiento de parcheos')
    with Session() as db:
        campaigns = db.scalars(select(Campaign).order_by(Campaign.year.desc(),Campaign.month.desc())).all()
        if not campaigns:
            st.info('No hay campañas.')
        else:
            chosen = st.selectbox('Campaña', campaigns, format_func=lambda c:f'{c.name} · {MONTHS[c.month-1]} {c.year}')
            network = st.selectbox('Filtrar por red', ['Todas'] + NETWORKS)
            status = st.selectbox('Filtrar por estado', ['Todos'] + STATUSES)
            rows = db.execute(select(Patch,Machine).join(Machine).where(Patch.campaign_id == chosen.id).order_by(Machine.hostname)).all()
            rows = [(p,m) for p,m in rows if (network == 'Todas' or m.network == network) and (status == 'Todos' or p.status == status)]
            st.dataframe(pd.DataFrame([{'ID':p.id,'Equipo':m.hostname,'Red':m.network,'Responsable':m.responsible,'Contacto':m.contact,'Estado':p.status,'Método':p.method,'KB':p.kb,'Mes aplicado':p.patch_month,'Técnico':p.technician,'Observaciones':p.notes} for p,m in rows]), use_container_width=True, hide_index=True)
            if rows:
                patch_id = st.selectbox('Editar actuación', [p.id for p,m in rows], format_func=lambda x:next(m.hostname for p,m in rows if p.id == x))
                p,m = next((p,m) for p,m in rows if p.id == patch_id)
                st.caption(f'Responsable: {m.responsible or "Sin asignar"} · Contacto: {m.contact or "Sin datos"}')
                with st.form(f'edit_{p.id}'):
                    new_status = st.selectbox('Estado', STATUSES, index=STATUSES.index(p.status))
                    method = st.selectbox('Método', METHODS, index=METHODS.index(p.method) if p.method in METHODS else 0)
                    kb = st.text_input('KB aplicada', value=p.kb)
                    patch_month = st.text_input('Mes del acumulativo', value=p.patch_month)
                    technician = st.text_input('Técnico responsable', value=p.technician or user.username)
                    notes = st.text_area('Observaciones actuales', value=p.notes)
                    comment = st.text_area('Comentario de la actuación (se guarda en el histórico)')
                    save = st.form_submit_button('Guardar cambios')
                if save:
                    old = p.status
                    p.status,p.method,p.kb,p.patch_month,p.technician,p.notes = new_status,method,kb,patch_month,technician,notes
                    now = utcnow()
                    if new_status != 'Pendiente' and p.started_at is None:
                        p.started_at = now
                    if new_status == 'Finalizado' and p.finished_at is None:
                        p.finished_at = now
                    if new_status != 'Finalizado':
                        p.finished_at = None
                    p.updated_at = now
                    audit(db,p,user.username,old,comment)
                    db.commit()
                    st.success('Cambios guardados y auditados.')
                    st.rerun()

elif page == 'Histórico':
    st.title('Histórico de actuaciones')
    with Session() as db:
        rows = db.execute(select(Event,Patch,Machine,Campaign).join(Patch,Event.patch_id==Patch.id).join(Machine,Patch.machine_id==Machine.id).join(Campaign,Patch.campaign_id==Campaign.id).order_by(Event.created_at.desc()).limit(5000)).all()
        st.dataframe(pd.DataFrame([{'Fecha UTC':e.created_at,'Equipo':m.hostname,'Campaña':f'{c.name} {MONTHS[c.month-1]} {c.year}','Usuario':e.actor,'Estado anterior':e.old_status,'Estado nuevo':e.new_status,'Comentario':e.comment} for e,p,m,c in rows]), use_container_width=True, hide_index=True)

elif page == 'Informes':
    st.title('Exportación de informes')
    with Session() as db:
        campaigns = db.scalars(select(Campaign).order_by(Campaign.year.desc(),Campaign.month.desc())).all()
        if not campaigns:
            st.info('No hay campañas.')
        else:
            chosen = st.selectbox('Campaña', campaigns, format_func=lambda c:f'{c.name} · {MONTHS[c.month-1]} {c.year}')
            rows = db.execute(select(Patch,Machine).join(Machine).where(Patch.campaign_id==chosen.id)).all()
            df = pd.DataFrame([{'Hostname':m.hostname,'IP':m.ip,'Red':m.network,'Responsable':m.responsible,'Contacto':m.contact,'Estado':p.status,'Método':p.method,'KB':p.kb,'Mes acumulativo':p.patch_month,'Técnico':p.technician,'Observaciones':p.notes,'Inicio UTC':p.started_at,'Fin UTC':p.finished_at} for p,m in rows])
            events = db.execute(select(Event,Patch,Machine).join(Patch,Event.patch_id==Patch.id).join(Machine,Patch.machine_id==Machine.id).where(Patch.campaign_id==chosen.id).order_by(Event.created_at)).all()
            hist = pd.DataFrame([{'Fecha UTC':e.created_at,'Equipo':m.hostname,'Usuario':e.actor,'Estado anterior':e.old_status,'Estado nuevo':e.new_status,'Comentario':e.comment} for e,p,m in events])
            for frame in (df,hist):
                for col in frame.columns:
                    if 'UTC' in col:
                        frame[col] = frame[col].map(lambda x:x.replace(tzinfo=None) if isinstance(x,datetime) and x.tzinfo else x)
            output = BytesIO()
            with pd.ExcelWriter(output,engine='openpyxl') as writer:
                df.to_excel(writer,index=False,sheet_name='Equipos')
                hist.to_excel(writer,index=False,sheet_name='Histórico')
            st.download_button('📥 Descargar Excel',data=output.getvalue(),file_name=f'hotfixes_{chosen.year}_{chosen.month:02d}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

elif page == 'Usuarios' and admin:
    st.title('Administración de usuarios')
    with Session() as db:
        users = db.scalars(select(User).order_by(User.username)).all()
        st.dataframe(pd.DataFrame([{'ID':u.id,'Usuario':u.username,'Rol':u.role,'Activo':bool(u.active)} for u in users]),use_container_width=True,hide_index=True)
        with st.form('adduser'):
            username = st.text_input('Nuevo usuario')
            password = st.text_input('Contraseña inicial (mínimo 12 caracteres)',type='password')
            role = st.selectbox('Rol',['tecnico','admin'])
            save = st.form_submit_button('Crear usuario')
        if save:
            if not username.strip() or len(password)<12:
                st.error('Introduce usuario y contraseña de al menos 12 caracteres.')
            else:
                db.add(User(username=username.strip(),password_hash=hash_password(password),role=role))
                try:
                    db.commit()
                    st.rerun()
                except IntegrityError:
                    db.rollback()
                    st.error('El usuario ya existe.')
        st.subheader('Modificar usuarios')
        target = st.selectbox('Seleccionar usuario',users,format_func=lambda u:u.username)
        with st.form('updateuser'):
            new_role = st.selectbox('Rol', ['tecnico','admin'],index=['tecnico','admin'].index(target.role))
            active = st.checkbox('Activo',value=bool(target.active),disabled=target.id==user.id)
            new_password = st.text_input('Nueva contraseña (dejar en blanco para mantener)',type='password')
            update = st.form_submit_button('Actualizar')
        if update:
            if new_password and len(new_password)<12:
                st.error('La nueva contraseña debe tener al menos 12 caracteres.')
            elif target.id==user.id and new_role!='admin':
                st.error('No puedes quitarte tu propio rol de administrador.')
            else:
                target.role = new_role
                if target.id != user.id:
                    target.active = int(active)
                if new_password:
                    target.password_hash = hash_password(new_password)
                db.commit()
                st.rerun()
