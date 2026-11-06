from django.shortcuts import render
from productos.models import Producto  # ajusta si tu modelo está en otra app


def bienvenida(request):
    modulos = [
        # ... deja aquí tu lista actual de módulos sin cambios ...
    ]

    resumen = {
        "ventas_hoy": 0,                       # aquí tu suma de ventas del día
        "productos": Producto.objects.count(),
        "clientes_nuevos": 0,                  # aquí tus clientes creados hoy
    }
    return render(request, 'bienvenida.html', {'modulos': modulos, 'resumen': resumen})