from __future__ import unicode_literals

import ConfigParser

from os.path import join, dirname

configFile = join(dirname(__file__), 'settings.ini')
Config = ConfigParser.SafeConfigParser(
    dict(WAVES_TEST_GALAXY_PORT='')
)
Config.read(configFile)
WAVES_TEST_GALAXY_API_KEY = Config.get('galaxy', 'WAVES_TEST_GALAXY_API_KEY')
WAVES_TEST_GALAXY_HOST = Config.get('galaxy', 'WAVES_TEST_GALAXY_HOST')
WAVES_TEST_GALAXY_PROTOCOL = Config.get('galaxy', 'WAVES_TEST_GALAXY_PROTOCOL')
WAVES_TEST_GALAXY_PORT = Config.get('galaxy', 'WAVES_TEST_GALAXY_PORT')
WAVES_DEBUG_GALAXY = True

