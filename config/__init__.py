"""
Se usa PyMySQL (pure Python) en lugar de mysqlclient porque en hosting
compartido con cPanel no siempre es posible compilar extensiones C que
dependen de los headers de desarrollo de MySQL. PyMySQL se declara aqui
como sustituto de MySQLdb para que el backend 'django.db.backends.mysql'
funcione sin esa dependencia. Ver docs/arquitectura.md.
"""
import pymysql

pymysql.install_as_MySQLdb()
pymysql.version_info = (1, 4, 6, 'final', 0)
