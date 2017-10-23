""" Parse Bioblend connection errors """
from __future__ import unicode_literals

import json

import bioblend

from waves.wcore.adaptors.exceptions import AdaptorConnectException

__all__ = ['GalaxyAdaptorConnectionError']


class GalaxyAdaptorConnectionError(AdaptorConnectException):
    """
    Specific subclass for managing Galaxy service connection errors
    """
    def __init__(self, e):
        """
        Load and parse superclass ConnectionError message body
        :param e: The exception
        """

        class BaseError(Exception):
            def __init__(self, *args, **kwargs):
                super(BaseError, self).__init__(*args, **kwargs)

        if getattr(e, 'body'):
            error_data = json.loads(e.body)
        elif isinstance(e, bioblend.ConnectionError):
            error_data = dict(err_msg=e.message)
        elif e is str:
            try:
                error_data = json.loads(e)
            except ValueError:
                error_data = dict(err_msg="%s" % e)
        message = '{}'.format(error_data['err_msg'])
        super(GalaxyAdaptorConnectionError, self).__init__(message)
