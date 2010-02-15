#!/usr/bin/env python

from distutils.core import setup

setup(
    name='Pyff',
    description='Small web "framework"',
    author='Tomasz Kowalczyk', 
    py_modules=['pyff'],
    package_dir = {'': 'src'},
)
