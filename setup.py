from setuptools import setup, find_packages
import os

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))


setup(
    name='waves_adaptors-galaxy',
    version='0.0.4',
    package_dir={'': 'src'},
    packages=find_packages('src'),
    url='https://github.com/lirmm/waves_adaptors-galaxy-adaptors',
    license='GPLV3',
    author='Marc Chakiachvili',
    author_email='marc.chakiachvili@lirmm.fr',
    description='WAVES adaptor to interact with Galaxy remote platform',
    long_description=README,
    maintainer='LIRMM - MAB Laboratory - France',
    maintainer_email='vincent.lefort@lirmm.fr',
    include_package_data=True,
    # namespace_packages=['waves_adaptors', 'waves_adaptors.addons', 'waves_adaptors.importers'],
    install_requires=[
        'waves_adaptors-core>=0.0.2',
        'bioblend>=0.8.0'
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
