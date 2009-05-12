#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    from ez_setup import use_setuptools
except ImportError:
    pass
else:
    use_setuptools()

from setuptools import setup, find_packages


setup(
    name='ZenQueue',
    version='0.4.2',
    description='An incredibly simple (but fast) network message queueing system, written in Python.',
    author='Zachary Voase',
    author_email='disturbyte@gmail.com',
    url='http://github.com/disturbyte/zenqueue',
    packages=find_packages(),
    install_requires=['simplejson'],
)
