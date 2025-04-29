import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional


def import_module_from_local_path(
    module_name: str, module_path: Path, add_to_sys_modules: bool = True
) -> Optional[ModuleType]:
    """Imports a module using a local path.

    Args:
        module_name: name that it will have in `sys.modules`.
        module_path: module path.
        add_to_sys_modules (bool, optional): True to add the module to `sys.modules`,
            False otherwise. Defaults to True.

    Returns:
        imported module, None if it can not be imported.
    """
    # Check if it is already loaded
    module = sys.modules.get(module_name)
    if module is not None and hasattr(module, "__file__") and Path(module.__file__) == module_path:
        return sys.modules[module_name]

    # Load the module and add it to sys modules if required
    if module_path.is_dir():
        module_name = module_path.name
        module_path /= "__init__.py"
        if not module_path.exists():
            return None
    else:
        module_name = module_path.stem

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if add_to_sys_modules:
        sys.modules[module_name] = module
    return module


def dynamic_loader(module_path: Path) -> None:
    """Dynamically loads the modules that are not part of the package.

    Should only be used if import mode is `importlib`.

    Args:
        module_path: path to the module to be loaded.

    Raises:
        RuntimeError: if the provided path is not a directory with a valid `__init__.py` file.
    """
    if not (module_path / "__init__.py").exists():
        raise RuntimeError("Only directories with init path can be added in the dynamic loader")

    import_module_from_local_path(module_name=module_path.name, module_path=module_path)

    # Import all the submodules and files from the indicated module
    for path in module_path.rglob("*"):
        if "__pycache__" in path.parts:
            continue  # Skip __pycache__ and its contents
        elif path.is_dir():
            if not (path / "__init__.py").exists():
                continue  # Ignore directories without init ifle
            sys_module_name = ".".join(path.relative_to(module_path).parts)
        elif path.suffix == ".py":
            if path.name == "__init__.py" or path.name.startswith("test_"):
                continue  # Skip init file and avoid including all tests as modules
            sys_module_name = ".".join(path.relative_to(module_path).with_suffix("").parts)
        else:
            continue

        import_module_from_local_path(module_name=sys_module_name, module_path=path)
