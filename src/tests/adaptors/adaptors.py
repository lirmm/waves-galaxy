from __future__ import unicode_literals, absolute_import

import unittest
import inspect

class TestCompphyAdaptor(unittest.TestCase):

    def test_load_implementation(self):
        from waves.adaptors.loader import load_addons, load_core
        print load_core()
        addons = load_addons()
        self.assertTrue(all([not inspect.isabstract(clazz) for name, clazz in addons]))
        print addons
