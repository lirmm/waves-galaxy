"""
WAVES app Django application descriptor

"""
from __future__ import unicode_literals

from os.path import dirname

from django.apps import AppConfig


class GalaxyConfig(AppConfig):
    """
    WAVES main application AppConfig, add signals for waves_webapp
    """
    name = "galaxy.adaptors"
    verbose_name = 'WAVES Galaxy adaptors'
    path = dirname(__file__)
