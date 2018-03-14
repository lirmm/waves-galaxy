from setuptools import setup, find_packages
import os

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


def import_version():
    from waves.adaptors.galaxy import __version_detail__
    return __version_detail__


setup(
    name='waves-galaxy-adaptors',
    version=import_version(),
    packages=find_packages(),
    url='https://github.com/lirmm/waves-galaxy',
    license='GPLv3',
    author='Marc Chakiachvili',
    author_email='marc.chakiachvili@lirmm.fr',
    description='WAVES adaptor to interact with Galaxy remote platform',
    long_description=README,
    maintainer='LIRMM - MAB Laboratory - France',
    maintainer_email='vincent.lefort@lirmm.fr',
    include_package_data=True,
    install_requires=[
        'bioblend==0.9.0',
        'waves-core>=1.1.8'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Framework :: Django',
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'Topic :: System :: Distributed Computing',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Operating System :: Unix'
    ],
)
