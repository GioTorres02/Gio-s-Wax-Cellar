from django.shortcuts import render
from productos.models import Producto  # ajusta si tu modelo está en otra app


def bienvenida(request):
    modulos = [
        {'nombre': 'Clientes',     'url': '/clientes/',     'icono': 'fas fa-user-tie'},
        {'nombre': 'Proveedores',  'url': '/proveedores/',  'icono': 'fas fa-truck'},
        {'nombre': 'Productos',    'url': '/productos/',    'icono': 'fas fa-compact-disc'},
        {'nombre': 'Ventas',       'url': '/ventas/',       'icono': 'fas fa-file-invoice-dollar'},
        {'nombre': 'Reportes',     'url': '/reportes/',     'icono': 'fas fa-chart-bar'},
        {'nombre': 'Configuración', 'url': '/configuracion/', 'icono': 'fas fa-cogs'},
    ]

    resumen = {
        "ventas_hoy": 0,                       # aquí tu suma de ventas del día
        "productos": Producto.objects.count(),
        "clientes_nuevos": 0,                  # aquí tus clientes creados hoy
    }
    return render(request, 'bienvenida.html', {'modulos': modulos, 'resumen': resumen})