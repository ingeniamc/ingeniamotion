import re

import setuptools

with open("docs/what_is_ingeniamotion.rst", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("ingeniamotion/__init__.py") as f:
    __version = re.search(r"__version__\s+=\s+\"(.*)\"", f.read()).group(1)


def get_docs_url():
    return "https://distext.ingeniamc.com/doc/ingeniamotion/{}".format(__version)


setuptools.setup(
    name="ingeniamotion",
    version=__version,
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={"ingeniamotion": ["py.typed"]},
    author="Ingenia Motion Control",
    author_email="support@ingeniamc.com",
    description="Motion library for Ingenia servo drives",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://www.ingeniamc.com",
    project_urls={
        "Documentation": get_docs_url(),
        "Source": "https://github.com/ingeniamc/ingeniamotion",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "ingenialink>=7.2.0, < 7.3.0",
        "ingenialogger>=0.2.1",
        "ifaddr==0.1.7",
    ],
    python_requires=">=3.9",
)
