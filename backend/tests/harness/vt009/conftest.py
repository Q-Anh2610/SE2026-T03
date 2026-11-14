import os
import random


def pytest_collection_modifyitems(items):
    seed = os.environ.get("VT009_ORDER_SEED")
    if seed is not None:
        random.Random(int(seed)).shuffle(items)
