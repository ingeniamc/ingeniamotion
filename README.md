Ingeniamotion
=============

Build Module
------------

Install locally:
```bash
python setup.py build_ext -i
python setup.py install
```

Generate .whl file:
```bash
python setup.py build_ext -i
python setup.py bdist_wheel
```

Generate documentation
----------------------

For develop the documentation it's recommended uninstall the ingeniamotion in the pipenv
and remove all the .pyd files. Now we can ensure sphinx will get the data from the source.

### Build HTML documentation

It's recommended remove first the _docs folder.

```bash
sphinx-build -b html docs _docs
```

### Build PDF documentation

It's recommended remove first the _pdf folder.

```bash
sphinx-build -b pdf docs _pdf
```

Run PyTest
----------

Fill configuration json ``tests/config.json``.

Run tests with target protocol (eoe, soem). For example:

``pytest --protocol soem``
