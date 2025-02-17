from Cython.Build import cythonize
from setuptools import Extension, setup

extensions = [
    Extension(
        "get_adapters_info",
        ["get_adapters_info.pyx"],
        language="c++",
        extra_compile_args=["/TP"],
        libraries=["Iphlpapi"],
    )
]

setup(
    name="CyGetAdaptersInfo",
    ext_modules=cythonize(extensions, compiler_directives={"language_level": "3"}),
)
