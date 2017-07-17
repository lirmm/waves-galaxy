"""
WAVES app Django application descriptor

"""
from __future__ import unicode_literals

from django.apps import AppConfig


class GalaxyConfig(AppConfig):
    """
    WAVES main application AppConfig, add signals for waves_webapp
    """
    name = "waves.adaptors.galaxy"
    verbose_name = 'WAVES Galaxy adaptors'
