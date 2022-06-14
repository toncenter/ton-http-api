import os

from setuptools import setup, find_packages
from os.path import dirname, join, pardir


with open(join(dirname(__file__), "README.md"), "r") as f:
    long_description = f.read()

version = os.environ.get('TON_HTTP_API_VERSION', '0.0.0')

setup(
    author='K-Dimentional Tree',
    author_email='kdimentionaltree@gmail.com',
    name='ton-http-api',
    version=version,
    packages=find_packages('.', exclude=['tests']),
    install_requires=[
        'aioprocessing>=2.0.0',
        'aioredis>=2.0.1',
        'loguru>=0.6.0',
        'fastapi>=0.78.0',
        'pydantic>=1.9.1',
        'requests>=2.28.0',
        'ring>=0.9.1',
        'uvicorn>=0.17.6',
        'gunicorn>=20.1.0',
        'pytonlib>=0.0.11',
        'inject>=4.3.1'
    ],
    package_data={},
    zip_safe=True,
    python_requires='>=3.7',
    classifiers=[
         "Development Status :: 3 - Alpha",
         "Intended Audience :: Developers",
         "Programming Language :: Python :: 3.7",
         "Programming Language :: Python :: 3.8",
         "Programming Language :: Python :: 3.9",
         "License :: Other/Proprietary License",
         "Topic :: Software Development :: Libraries"
    ],
    url="https://github.com/toncenter/ton-http-api",
    description="HTTP API for TON (The Open Network)",
    long_description_content_type="text/markdown",
    long_description=long_description,
    entry_points={
        'console_scripts': [
            'ton-http-api = pyTON.cli:main'
        ]
    }
)
