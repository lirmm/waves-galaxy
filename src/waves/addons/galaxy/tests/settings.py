from __future__ import unicode_literals

import ConfigParser
from os.path import join, dirname
import logging.config

configFile = join(dirname(__file__), 'settings.ini')
Config = ConfigParser.SafeConfigParser(
    dict(WAVES_TEST_GALAXY_PORT=None,
         LOG_LEVEL='DEBUG',)
)
Config.read(configFile)
WAVES_TEST_GALAXY_API_KEY = Config.get('galaxy', 'WAVES_TEST_GALAXY_API_KEY')
WAVES_TEST_GALAXY_URL = Config.get('galaxy', 'WAVES_TEST_GALAXY_URL')
WAVES_TEST_GALAXY_PORT = Config.get('galaxy', 'WAVES_TEST_GALAXY_PORT')


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
