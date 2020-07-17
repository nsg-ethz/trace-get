# !/usr/bin/env python

"Setuptools params"

from setuptools import setup, find_packages

VERSION = '0.1'

modname = distname = 'traceget'


def readme():
    with open('README.md', 'r') as f:
        return f.read()

setup(
    name=distname,
    version=VERSION,
    description='Packet Traces Download Helper',
    author='Edgar Costa',
    author_email='cedgar@ethz.ch',
    packages=find_packages(),
    long_description=readme(),
    entry_points={'console_scripts': ['traceget = traceget.caida_frontend:main']},
    include_package_data=True,
    classifiers=[
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python 3.7",
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Topic :: System :: Networking",
    ],
    keywords='networking pcap traces',
    license='GPLv2',
    install_requires=[
        'setuptools',
        'bs4',
        'npyscreen',
        'dill',
        'requests',
        'appdirs'
    ],
    extras_require={}
)
