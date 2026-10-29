# Deploy — Publicación en Render

> Guía de despliegue (SDD · Fase 0). Detalle técnico de la decisión en
> [design.md §5](../design.md).

## Resumen

- **Runtime**: gunicorn (WSGI) + whitenoise (staticfiles sin CDN).
- **Config**: variables de entorno (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`).
- **Build**: `uv sync` → `collectstatic` → `migrate`.
- **DB**: SQLite por defecto (no hay modelos de negocio; suficiente para el examen).

## 1. Variables de entorno

| Variable | Ejemplo | Descripción |
|----------|---------|-------------|
| `SECRET_KEY` | (generar una larga) | Clave secreta de Django. Obligatoria. |
| `DEBUG` | `False` | `False` en producción. |
| `ALLOWED_HOSTS` | `mi-app.onrender.com` | Hosts permitidos, separados por coma. |
| `PYTHON_VERSION` | `3.12` | Debe coincidir con `.python-version`. |

## 2. Pasos en Render

### 2.1 Subir el código a un repo git

Render despliega desde Git. Este proyecto aún no tiene repo inicializado:

```bash
git init
git add .
git commit -m "Simuladores de SO: base + inodes + processes"
# Crear un repo vacío en GitHub y:
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
```

> El `.gitignore` ya excluye `.venv/`, `__pycache__/`, `db.sqlite3`, `.ruff_cache/`.

### 2.2 Crear el servicio en Render

1. Dashboard → **New** → **Blueprint** (lee `render.yaml`) o **Web Service**.
2. Conectar el repositorio.
3. Si usas Blueprint: Render detecta `render.yaml` y crea el servicio.
4. Si usas Web Service manual, configurar:

| Campo | Valor |
|-------|-------|
| Runtime | `Python` |
| Build Command | `uv sync && uv run python manage.py migrate --noinput && uv run python manage.py collectstatic --noinput` |
| Start Command | `uv run gunicorn config.wsgi:application` |

### 2.3 Añadir las variables de entorno

En **Environment** del servicio, añadir las de la §1. Genera `SECRET_KEY` con:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 2.4 Deploy

Guardar → Render construye y despliega. La app queda en
`https://<nombre-servicio>.onrender.com/`.

## 3. Notas

- **Static**: whitenoise sirve los ficheros de `STATIC_ROOT` (`staticfiles/`) generados en
  el build por `collectstatic`. No hace falta CDN para el examen.
- **DB efímera**: el disco de Render free se borra al redeployar. Como las simulaciones
  son stateless y no hay modelos de negocio, esto **no afecta**. Si en el futuro se
  necesitara persistencia, añadir un Postgres managed y `dj-database-url`.
- **Admin**: disponible en `/admin/`; requiere crear un superusuario
  (`createsuperuser`) si se necesita usarlo.
- **Dominio**: el plan free asigna `*.onrender.com`; para dominio propio se configura en
  el servicio.

## 4. Checklist post-deploy

- ☐ La landing carga y lista las simulaciones.
- ☐ `/<slug>/` carga con 200 para inodes y processes.
- ☐ Las acciones JSON responden (p. ej. `POST /inodes/api/action/`).
- ☐ `DEBUG=False` y `ALLOWED_HOSTS` correctos (sin `DisallowedHost`).
