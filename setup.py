#!/usr/bin/env python
import os
import uuid
from setuptools import setup, find_packages
from pip.req import parse_requirements

install_reqs = parse_requirements(os.path.join(os.path.dirname(__file__), 'requirements.txt'), session=uuid.uuid1())

setup(name='fedoralink',
      version='0.5.0',
      description='Django-like link to Fedora Commons 4',
      author='Mirek Simek',
      author_email='miroslav.simek@gmail.com',
      url='TODO',
      packages=find_packages(),
      use_2to3 = False,
      install_requires=[str(ir.req) for ir in install_reqs]
)
