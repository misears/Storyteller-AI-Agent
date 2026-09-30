import gc
import os
from tempfile import TemporaryDirectory


_original_data_dir = os.environ.get("STORYTELLER_DATA_DIR")
_test_data_dir = None


def pytest_configure(config):
    global _test_data_dir
    _test_data_dir = TemporaryDirectory(prefix="storyteller-tests-")
    os.environ["STORYTELLER_DATA_DIR"] = _test_data_dir.name


def pytest_unconfigure(config):
    if _original_data_dir is None:
        os.environ.pop("STORYTELLER_DATA_DIR", None)
    else:
        os.environ["STORYTELLER_DATA_DIR"] = _original_data_dir
    if _test_data_dir is not None:
        gc.collect()
        _test_data_dir.cleanup()