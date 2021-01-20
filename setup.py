import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open('ingeniamotion/__init__.py') as f:
    __version = re.search(r'__version__\s+=\s+\'(.*)\'', f.read()).group(1)

setuptools.setup(
    name="ingeniamotion",
    version=__version,
    packages=find_packages(),
    author="Ingenia Motion Control",
    author_email="support@ingeniamc.com",
    description="Motion library for Ingenia servo drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'ingenialink>=5.1.0'
    ]
    python_requires='>=3.6',
)