from setuptools import setup, find_packages
import os

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

with open(os.path.join(os.path.dirname(__file__), 'VERSION')) as version:
    VERSION = version.readline()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name='galaxy-galaxy-adaptors',
    version=VERSION,
    package_dir={'': 'src'},
    packages=find_packages('src'),
    url='https://github.com/lirmm/galaxy.adaptors-galaxy-adaptors',
    license='GPLv3',
    author='Marc Chakiachvili',
    author_email='marc.chakiachvili@lirmm.fr',
    description='WAVES adaptor to interact with Galaxy remote platform',
    long_description=README,
    maintainer='LIRMM - MAB Laboratory - France',
    maintainer_email='vincent.lefort@lirmm.fr',
    include_package_data=True,
    install_requires=[
        'bioblend>=0.8.0',
        'waves-core>=1.1.1'
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Scientific/Engineering :: Interface Engine/Protocol Translator',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: Unix'
    ],
)
