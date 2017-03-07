from __future__ import unicode_literals

import ConfigParser
from os.path import join, dirname
import logging.config

configFile = join(dirname(__file__), 'settings.ini')
Config = ConfigParser.SafeConfigParser(
    dict(WAVES_TEST_GALAXY_PORT='',
         LOG_LEVEL='DEBUG',)
)
Config.read(configFile)
WAVES_TEST_GALAXY_API_KEY = Config.get('galaxy', 'WAVES_TEST_GALAXY_API_KEY')
WAVES_TEST_GALAXY_HOST = Config.get('galaxy', 'WAVES_TEST_GALAXY_HOST')
WAVES_TEST_GALAXY_PROTOCOL = Config.get('galaxy', 'WAVES_TEST_GALAXY_PROTOCOL')
WAVES_TEST_GALAXY_PORT = Config.get('galaxy', 'WAVES_TEST_GALAXY_PORT')
WAVES_DEBUG_GALAXY = True

LOGGING_CONFIG = None
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '[%(levelname)s][%(asctime)s][%(name)s.%(funcName)s:line %(lineno)s] - %(message)s',
            'datefmt': "%d/%b/%Y %H:%M:%S"
        },
        'simple': {
            'format': '[%(levelname)s] - %(message)s'
        },
        'trace': {
            'format': '%(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    }
}

logging.config.dictConfig(LOGGING)
