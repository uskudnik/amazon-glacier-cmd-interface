# -*- coding: utf-8 -*-
"""Installer for this package."""

from setuptools import setup
from setuptools import find_packages

import os

# shamlessly stolen from Hexagon IT guys
def read(*rnames):
    return open(os.path.join(os.path.dirname(__file__), *rnames)).read()

version = '0.2dev'

setup(name='glacier-cmd',
      version=version,
      description="Command line interface for Amazon Glacier",
      long_description=read('README.md')+read("LICENSE"),
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='amazon glacier cmd interface',
      author='Urban Škudnik',
      author_email='urban.skudnik@gmail.com',
      url='https://github.com/uskudnik/amazon-glacier-cmd-interface',
      license='MIT',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      dependency_links =
            ["https://github.com/boto/boto/tarball/master#egg=boto-2.5.9999"],
      install_requires=[
          # list project dependencies
          'boto',
          'python-dateutil',
          'pytz',
      ],
    entry_points="""
          [console_scripts]
          glacier-cmd = glacier_cmd.glaciercmd:main
          """,
      )
