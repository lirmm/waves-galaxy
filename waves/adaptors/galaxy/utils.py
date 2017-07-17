"""
A copy of bioblend libraty unit tests decorators, with added few functionality
Based on https://github.com/galaxyproject/bioblend/
Author : Marc Chakiachvili
"""
from __future__ import unicode_literals

import unittest

from bioblend.galaxy.client import ConnectionError
from bioblend.galaxy.objects import *
from django.conf import settings

NO_GALAXY_MESSAGE = "Externally configured Galaxy, but connection failed. %s"
WRONG_GALAXY_KEY = "A Galaxy server is running, but provided api key is wrong."
MISSING_SETTINGS = "Some settings are required to run Galaxy test : WAVES_TEST_GALAXY_HOST, " \
                   "WAVES_TEST_GALAXY_PROTOCOL, " \
                   "WAVES_TEST_GALAXY_PORT, WAVES_TEST_GALAXY_API_KEY."
MISSING_TOOL_MESSAGE = "Externally configured Galaxy instance requires tool %s to run test."


def skip_unless_galaxy():
    try:
        galaxy_key = settings.WAVES_TEST_GALAXY_API_KEY
        galaxy_url = '%s://%s' % (settings.WAVES_TEST_GALAXY_PROTOCOL, settings.WAVES_TEST_GALAXY_HOST)
        if settings.WAVES_TEST_GALAXY_PORT:
            galaxy_url += ':%s' % settings.WAVES_TEST_GALAXY_PORT
        gi_obj = GalaxyInstance(url=str(galaxy_url), api_key=galaxy_key)
        gi_obj.gi.users.get_current_user()
    except ConnectionError as e:
        return unittest.skip(NO_GALAXY_MESSAGE % e + ' [' + galaxy_url + '][' + galaxy_key + ']')
    except AttributeError as e:
        return unittest.skip(MISSING_SETTINGS)
    return lambda f: f


def skip_unless_tool(command):
    """ Decorate a Galaxy test method as requiring a specific tool,
    skip the test case if the tool is unavailable.
    """
    galaxy_key = settings.WAVES_TEST_GALAXY_API_KEY
    galaxy_url = '%s://%s' % (settings.WAVES_TEST_GALAXY_PROTOCOL, settings.WAVES_TEST_GALAXY_HOST)
    if settings.WAVES_TEST_GALAXY_PORT:
        galaxy_url += ':%s' % settings.WAVES_TEST_GALAXY_PORT
    gi = GalaxyInstance(url=str(galaxy_url), api_key=galaxy_key)

    def method_wrapper(method):
        def wrapped_method(has_gi, *args, **kwargs):
            tools = gi.tools.list()
            # In panels by default, so flatten out sections...
            tool_ids = [_.id for _ in tools]
            tool_names = [_.name for _ in tools]
            if command not in tool_ids and not command not in tool_names:
                raise unittest.SkipTest(MISSING_TOOL_MESSAGE % command)
            return method(has_gi, *args, **kwargs)

        # Must preserve method name so nose can detect and report tests by
        # name.
        wrapped_method.__name__ = method.__name__
        return wrapped_method

    return method_wrapper
