import os
from distutils.core import setup


def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

setup(
    name="tools4msp",
    version="1.0.0-beta.1",
    author="Stefano Menegon",
    author_email="stefano.menegon@ismar.cnr.it",
    description="Tools 4 MSP",
    long_description=(read('README.md')),
    # Full list of classifiers can be found at:
    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
    ],
    license="GPL3",
    keywords="Maritime Spatial Planning",
    url='http://data.adriplan.eu',
    packages=['tools4msp',],
    include_package_data=True,
    zip_safe=False,
    install_requires=['django-import-export',
                      'matplotlib',
                      'jsonfield',
                      'pandas',
                      'geopandas',
                      'django-extensions',
                      'django-filter',
                      'django-import-export',
                      'django-rest-swagger',
                      'djangorestframework',
                      'djangorestframework-gis',
                      ],
)
