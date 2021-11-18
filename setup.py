import re
import os
import glob
import sysconfig
import setuptools


with open("docs/what_is_ingeniamotion.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('ingeniamotion/__init__.py') as f:
    __version = re.search(r"__version__\s+=\s+'(.*)'", f.read()).group(1)


def get_docs_url():
    return "https://distext.ingeniamc.com/doc/ingeniamotion/{}".format(__version)


if "SKIP_CYTHON" not in os.environ:
    from Cython.Build import cythonize
    from setuptools.command.build_py import build_py as _build_py
    class build_py(_build_py):
        def find_package_modules(self, package, package_dir):
            ext_suffix = sysconfig.get_config_var('EXT_SUFFIX')
            modules = super().find_package_modules(package, package_dir)
            return [(pkg, mod, filepath) for (pkg, mod, filepath) in modules
                    if not glob.glob(filepath.replace('.py', f".*{ext_suffix}"))
            ]
    ext_modules = cythonize(["ingeniamotion/*.py", "ingeniamotion/wizard_tests/*.py"])
else:
    from setuptools.command.build_py import build_py
    ext_modules = None


setuptools.setup(
    name="ingeniamotion",
    version=__version,
    cmdclass={'build_py': build_py},
    packages=setuptools.find_packages(),
    author="Ingenia Motion Control",
    author_email="support@ingeniamc.com",
    description="Motion library for Ingenia servo drives",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url='https://www.ingeniamc.com',
    project_urls={
                "Documentation": get_docs_url(),
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'ingenialink>=6.1.1',
        'ingenialogger==0.2.1',
        'ifaddr==0.1.7'
    ],
    python_requires='>=3.6',
    ext_modules=ext_modules
)
