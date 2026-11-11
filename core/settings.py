# core/settings.py
import sys
from pathlib import Path

import dj_database_url
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

# True cuando se ejecuta `python manage.py test`
TESTING = 'test' in sys.argv

# ── Variables de entorno ──────────────────────────────────────────────────
env = environ.Env(DEBUG=(bool, True))
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='dev-key-insegura-solo-para-desarrollo')
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# Render asigna su propio hostname en esta variable.
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default='')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Cualquier subdominio de Render (gios-wax-cellar.onrender.com, etc.)
ALLOWED_HOSTS.append('.onrender.com')

# Orígenes de confianza para POST (CSRF). Django exige el esquema https://
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://*.onrender.com',
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')

# ── HTTPS detrás del proxy de Render ──────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookies seguras solo en producción (en local con http:// no se enviarían)
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

# ── Almacenamiento de media en Cloudinary (solo si USE_CLOUDINARY=True) ──
USE_CLOUDINARY = (not TESTING) and env.bool('USE_CLOUDINARY', default=False)

# ── Apps instaladas ───────────────────────────────────────────────────────
# jazzmin debe ir ANTES de django.contrib.admin.
# whitenoise.runserver_nostatic debe ir ANTES de django.contrib.staticfiles.
# cloudinary_storage debe ir ANTES de django.contrib.staticfiles.
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    *(['cloudinary_storage'] if USE_CLOUDINARY else []),
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Terceros
    *(['cloudinary'] if USE_CLOUDINARY else []),
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    # Apps del ERP
    'clientes',
    'proveedores',
    'productos',
    'ventas',
    'reportes',
    'configuracion',
    'catalogo',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'core.urls'

# ── Templates ─────────────────────────────────────────────────────────────
# Django busca primero en BASE_DIR/templates/ (base.html, home.html, partials/)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Contador del carrito (carrito_total_items) — W13
                'catalogo.context_processors.carrito_info',
            ],
        },
    },
]

# ── Base de datos ─────────────────────────────────────────────────────────
# Local: si no hay DATABASE_URL, usa db.sqlite3 en la carpeta del proyecto.
# Render: define DATABASE_URL con la Internal Database URL de tu PostgreSQL.
DATABASES = {
    'default': dj_database_url.config(
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
        conn_max_age=600,
    )
}

# ── Internacionalización ──────────────────────────────────────────────────
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

# ── Archivos estáticos ────────────────────────────────────────────────────
# La música de los vinilos va en static/musica/ (sabrina.mp3, olivia.mp3, ...)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'           # destino de collectstatic
STATICFILES_DIRS = [BASE_DIR / 'static']         # fuentes adicionales

# WhiteNoise sirve los estáticos directo desde las carpetas del proyecto
# (admin, Jazzmin, static/img, etc.) aunque collectstatic no los haya copiado.
WHITENOISE_USE_FINDERS = True

# ── Archivos media (por defecto: disco local) ─────────────────────────────
# En Render el disco es efímero: para que las fotos no se pierdan,
# activa USE_CLOUDINARY=True (ver bloque Cloudinary más abajo).
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        # Sin compresión: WhiteNoise sirve los estáticos igual, y evita el
        # FileNotFoundError de collectstatic con los archivos de admin/Jazzmin.
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}

if USE_CLOUDINARY:
    CLOUDINARY_CLOUD_NAME = env('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = env('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = env('CLOUDINARY_API_SECRET')

    import cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )

    # Configuración que lee django-cloudinary-storage
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
        'API_KEY': CLOUDINARY_API_KEY,
        'API_SECRET': CLOUDINARY_API_SECRET,
    }

    STORAGES['default'] = {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    }

# ── Autenticación ─────────────────────────────────────────────────────────
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/catalogo/'      # tras iniciar sesión, la tienda
LOGOUT_REDIRECT_URL = '/'

# ── DRF ──────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',   # navegador
        'rest_framework.authentication.TokenAuthentication',     # clientes externos
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── JAZZMIN — Admin con la identidad de Gio's Wax Cellar ──────────────────
JAZZMIN_SETTINGS = {
    # Identidad
    'site_title': "Gio's Wax Cellar",
    'site_header': "Gio's Wax Cellar",
    'site_brand': "💿 Gio's Wax Cellar",
    'welcome_sign': "Bienvenido al sótano del vinilo",
    'copyright': "Gio Torres · Gio's Wax Cellar · UTEC Celaya",

    # Logo (ruta relativa a static/)
    'site_icon': None,
    'site_logo': None,

    # Búsqueda global en el admin
    'search_model': ['clientes.Cliente', 'productos.Producto'],

    # Menú superior
    'topmenu_links': [
        {'name': 'La tienda', 'url': '/catalogo/', 'new_window': False},
        {'name': 'Productos', 'url': '/productos/'},
        {'name': 'Clientes', 'url': '/clientes/'},
        {'name': 'Ventas', 'url': '/ventas/'},
    ],

    # Menú de usuario
    'usermenu_links': [
        {'name': 'Ver la tienda', 'url': '/catalogo/', 'new_window': False},
    ],

    # Orden del menú lateral
    'order_with_respect_to': [
        'clientes', 'proveedores', 'productos',
        'ventas', 'configuracion', 'auth',
    ],

    # Iconos de Font Awesome
    'icons': {
        'auth': 'fas fa-users-cog',
        'auth.user': 'fas fa-user',
        'auth.Group': 'fas fa-users',
        'clientes.Cliente': 'fas fa-user-tie',
        'proveedores.Proveedor': 'fas fa-truck',
        'productos.Categoria': 'fas fa-tags',
        'productos.Producto': 'fas fa-compact-disc',
        'ventas.Venta': 'fas fa-file-invoice-dollar',
        'ventas.DetalleVenta': 'fas fa-list',
        'ventas.Pedido': 'fas fa-shopping-cart',
        # Debe coincidir con el nombre real de la clase en configuracion/models.py
        'configuracion.ConfiguracionERP': 'fas fa-cogs',
    },
    'default_icon_parents': 'fas fa-folder',
    'default_icon_children': 'fas fa-circle',

    # Apariencia
    'related_modal_active': True,
    'custom_css': 'erp_custom.css',   # archivo en static/
    'show_sidebar': True,
    'navigation_expanded': True,
    'hide_apps': [],
    'hide_models': [],

    # UI
    'changeform_format': 'horizontal_tabs',
    'language_chooser': False,
}

JAZZMIN_UI_TWEAKS = {
    'navbar_small_text': False,
    'footer_small_text': False,
    'body_small_text': False,
    'brand_small_text': False,
    'brand_colour': 'navbar-orange',
    'accent': 'accent-warning',
    'navbar': 'navbar-dark',
    'no_navbar_border': False,
    'navbar_fixed': True,
    'layout_boxed': False,
    'footer_fixed': False,
    'sidebar_fixed': True,
    'sidebar': 'sidebar-dark-warning',
    'sidebar_nav_small_text': False,
    'sidebar_disable_expand': False,
    'sidebar_nav_child_indent': True,
    'sidebar_nav_compact_style': False,
    'sidebar_nav_legacy_style': False,
    'sidebar_nav_flat_style': False,
    'theme': 'default',
    'default_theme_mode': 'dark',   # 'auto', 'light' o 'dark'
    'button_classes': {
        'primary': 'btn-warning',
        'secondary': 'btn-secondary',
        'info': 'btn-info',
        'warning': 'btn-warning',
        'danger': 'btn-danger',
        'success': 'btn-success',
    },
}

# ── DJANGO SITES (requerido por allauth) ──────────────────────────────────
SITE_ID = 1

# ── AUTHENTICATION BACKENDS ───────────────────────────────────────────────
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ── ALLAUTH: configuración para desarrollo académico ──────────────────────
ACCOUNT_LOGIN_METHODS = {'username'}
ACCOUNT_EMAIL_REQUIRED = False
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_SESSION_REMEMBER = True

# ── STRIPE (pasarela de pago) ─────────────────────────────────────────────
# Las claves reales van SOLO en .env (nunca en este archivo ni en Git).
STRIPE_SECRET_KEY      = env('STRIPE_SECRET_KEY',      default='sk_test_placeholder')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='pk_test_placeholder')
STRIPE_WEBHOOK_SECRET  = env('STRIPE_WEBHOOK_SECRET',  default='whsec_placeholder')

# ── LOGGING: muestra los errores 500 en Render → Logs ─────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
    },
}