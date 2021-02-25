import re
import setuptools
from setuptools import setup
from setuptools import Extension

from Cython.Distutils import build_ext
from Cython.Build import cythonize

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('ingeniamotion/__init__.py') as f:
    __version = re.search(r"__version__\s+=\s+'(.*)'", f.read()).group(1)

setuptools.setup(
    name="ingeniamotion",
    version=__version,
    cmdclass={'build_ext': build_ext},
    packages=setuptools.find_packages(),
    author="Ingenia Motion Control",
    author_email="support@ingeniamc.com",
    description="Motion library for Ingenia servo drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'ingenialink>=5.1.0',
    ],
    python_requires='>=3.6',
    ext_modules=cythonize(["ingeniamotion/*.py", "ingeniamotion/wizard_tests/*.py"])
)
