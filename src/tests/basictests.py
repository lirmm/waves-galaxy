from __future__ import unicode_literals, absolute_import

import unittest
import inspect
from waves_adaptors.core.base import AdaptorImporter


class TestGalaxyAdaptors(unittest.TestCase):

    def test_load_implementation(self):
        from waves_adaptors.loader import load_addons, load_core
        self.assertTrue(all([not inspect.isabstract(clazz) for name, clazz in load_core()]))
        addons = load_addons()
        self.assertTrue(all([not inspect.isabstract(clazz) for name, clazz in addons]))
        # Be sure at least both new classes are added to addons
        self.assertGreaterEqual(len(addons), 2)

    def test_load_importers(self):
        from waves_adaptors.loader import load_importers
        imps = load_importers()
        self.assertTrue(all([issubclass(clazz, AdaptorImporter) for name, clazz in imps]))
        # Be sure at least both new classes are added to imps
        self.assertGreaterEqual(len(imps), 2)
