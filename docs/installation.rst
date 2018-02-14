Installation
============

Add WAVES adaptors to communicate with Galaxy server

.. WARNING::
    To run WAVES, it is strongly recommended to read dedicated doc:
    `waves-core <http://waves-core.readthedocs.io/en/latest/>`_.


.. note::
    You need to install waves-core packages in your app before running this setup
    Once created your Django application, with waves-core, simply add waves-galaxy package

Add package to your virtual env

    ``pip install waves-galaxy``


1. Configure WAVES
------------------

    You simply enable waves-galaxy adapters in your settings.py file

    .. code-block:: python

        WAVES_CORE = {
           ...
           'ADAPTORS_CLASSES': (
                ...
                'waves.adaptors.galaxy.tool.GalaxyJobAdaptor',
                'waves.adaptors.galaxy.workflow.GalaxyWorkFlowAdaptor',
            ),
        }

