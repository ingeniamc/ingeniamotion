from pathlib import Path
from typing import Callable, Optional

import pytest
from ingenialink.dictionary import Interface
from summit_testing_framework.setups.specifiers import DictionaryType, DictionaryVersion


@pytest.fixture(scope="session")
def sample_safe_ph1_xdfv3_dictionary(
    product_dictionary: Callable[[str, DictionaryVersion, Optional[Interface]], Path],
) -> Path:
    return product_dictionary(
        "DEN-S-NET-E",
        DictionaryVersion("2.9.1", DictionaryType.XDF_V3),
    )


@pytest.fixture(scope="session")
def sample_safe_ph2_xdfv3_dictionary(
    product_dictionary: Callable[[str, DictionaryVersion, Optional[Interface]], Path],
) -> Path:
    return product_dictionary(
        "EVS-S-NET-E",
        DictionaryVersion("2.9.1", DictionaryType.XDF_V3),
    )
