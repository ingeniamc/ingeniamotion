import re

import setuptools

__version = re.search(r"__version__\s+=\s+\"(.*)\"", open("ingeniamotion/__init__.py").read()).group(1)

def get_docs_url():
    return f"https://distext.ingeniamc.com/doc/ingeniamotion/{__version}"


setuptools.setup(
    url="https://www.ingeniamc.com",
    project_urls={
        "Documentation": get_docs_url(),
        "Source": "https://github.com/ingeniamc/ingeniamotion",
    },
)
