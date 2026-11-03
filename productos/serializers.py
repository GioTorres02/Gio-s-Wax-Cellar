# productos/serializers.py
"""Serializers de la app productos — W10 y W11.

Expone Categoria y Producto como recursos JSON para la API REST.
Producto incluye la URL absoluta de la imagen (imagen_url) para clientes externos.
"""
from rest_framework import serializers

from .models import Categoria, Producto


class CategoriaSerializer(serializers.ModelSerializer):
    """Serializer de Categoria — campos completos."""

    class Meta:
        model            = Categoria
        fields           = ['id', 'nombre', 'descripcion']
        read_only_fields = ['id']


class ProductoSerializer(serializers.ModelSerializer):
    """Serializer de Producto con nombre de categoría, proveedor e imagen.

    Campos adicionales:
        categoria_nombre: nombre legible de la FK categoria.
        proveedor_nombre: nombre legible de la FK proveedor (nullable).
        imagen_url: URL absoluta de la imagen, o None si no tiene imagen.
    """

    categoria_nombre = serializers.CharField(
        source='categoria.nombre',
        read_only=True
    )
    proveedor_nombre = serializers.CharField(
        source='proveedor.nombre',
        read_only=True,
        allow_null=True
    )
    imagen_url = serializers.SerializerMethodField()

    class Meta:
        model  = Producto
        fields = [
            'id', 'nombre', 'precio', 'stock',
            'categoria', 'categoria_nombre',
            'proveedor', 'proveedor_nombre',
            'activo', 'imagen', 'imagen_url', 'creado',
        ]
        read_only_fields = [
            'id', 'creado', 'categoria_nombre',
            'proveedor_nombre', 'imagen_url',
        ]

    def get_imagen_url(self, obj):
        request = self.context.get('request')
        if obj.imagen and request:
            return request.build_absolute_uri(obj.imagen.url)
        return None