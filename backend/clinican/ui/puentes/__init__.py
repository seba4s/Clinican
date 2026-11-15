"""Puentes entre QML y los casos de uso.

Cada pantalla y cada diálogo tiene aquí un objeto de presentación (``QObject``) que
lee la base a través de ``servicios``, prepara los textos que QML dibuja y recibe
sus acciones. Los archivos ``.qml`` solo dibujan: no conocen la base ni las reglas.
"""
