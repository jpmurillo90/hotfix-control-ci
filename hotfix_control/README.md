# Hotfix Control | CI

Aplicación Streamlit independiente para seguimiento colaborativo de campañas de parcheo. No ejecuta parches ni reinicios.

## Instalación

1. Instala Python 3.11+ y PostgreSQL 15+ en infraestructura autorizada.
2. Crea una base de datos y un usuario PostgreSQL con permisos sobre ella.
3. En la carpeta del proyecto:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
pip install -r requirements.txt
```

4. Configura la variable de entorno `DATABASE_URL` (ver `.env.example`). El archivo `.env` **no se carga automáticamente**. En PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg://hotfix_user:CLAVE@localhost:5432/hotfix_control"
streamlit run app.py
```

5. Accede al enlace mostrado y crea el primer administrador.

## Módulos
Dashboard, inventario, campañas, seguimiento, histórico y exportación Excel; administración de usuarios con roles `admin` y `tecnico`.

## Seguridad y despliegue

**Versión inicial / piloto**. Para producción corporativa se requiere revisión por TI/Seguridad, HTTPS mediante proxy inverso, acceso solo desde red/VPN autorizada, copias de seguridad PostgreSQL, política de contraseñas y recuperación de acceso, protección frente a intentos de login, sesiones con expiración, controles de auditoría reforzados, gestión de migraciones y pruebas de concurrencia. Streamlit no proporciona por sí solo un sistema corporativo de identidad; valorar SSO corporativo. No subir inventarios, IP ni contactos reales a repositorios públicos o servicios externos sin autorización.

Los cambios de estado y comentarios se registran en histórico, pero los cambios de otros campos de las actuaciones aún no tienen auditoría detallada. La zona horaria de los eventos es UTC.
