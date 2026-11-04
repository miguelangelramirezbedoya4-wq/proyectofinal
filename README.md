# EcoInsumos

Aplicación web académica de reutilización e intercambio de objetos, construida con FastAPI, SQLAlchemy, SQLite y plantillas Jinja2.

## Requisitos

- Python 3.10 o superior
- pip

## Instalación en Windows

Desde PowerShell, en la carpeta raíz del proyecto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si PowerShell no permite activar el entorno, puedes ejecutar los comandos con `venv\Scripts\python.exe` sin activarlo.

## Ejecutar en desarrollo

```powershell
$env:APP_ENV = "development"
python -m uvicorn app.main:app --reload
```

Abre <http://127.0.0.1:8000/> para usar el sitio y <http://127.0.0.1:8000/docs> para consultar la documentación de la API. El modo de desarrollo solo debe usarse en la computadora local.

## Configuración para producción

No despliegues con `--reload` ni con el secreto de desarrollo. Genera un secreto aleatorio de al menos 32 caracteres y guárdalo en el gestor de secretos del entorno:

```powershell
$env:APP_ENV = "production"
$env:SESSION_SECRET = python -c "import secrets; print(secrets.token_urlsafe(48))"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

En producción, la aplicación exige `SESSION_SECRET` y marca las cookies de sesión como seguras para HTTPS. Ejecuta Uvicorn detrás de un proxy inverso configurado con TLS/HTTPS. No compartas ni guardes el secreto en el repositorio.

Las contraseñas nuevas se guardan con scrypt. Al iniciar la aplicación, las contraseñas existentes en texto plano se convierten a hashes; también se actualizan al iniciar sesión si una cuenta todavía conserva una contraseña antigua. Este cambio no altera las contraseñas que usan las personas.

## Pruebas

```powershell
python -m unittest discover -s tests
```

## Estructura principal

- `app/controllers/`: rutas y lógica de la aplicación.
- `app/models/`: modelos SQLAlchemy.
- `app/database/`: conexión y actualización compatible del esquema SQLite.
- `app/views/`: plantillas HTML.
- `app/static/`: CSS, JavaScript e imágenes.
- `ecoinsumos.db`: base de datos SQLite local.

El pago del proyecto es un simulador académico y no procesa dinero real. Antes de ofrecer el sitio públicamente, configura HTTPS, copias de seguridad y un proveedor de pago real; revisa también las políticas de privacidad y protección de datos aplicables.
