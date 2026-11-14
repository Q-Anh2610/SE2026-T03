"""Kiểm tra test isolation theo thứ tự ngược, không cần plugin mới."""


def pytest_addoption(parser):
    parser.addoption("--vt012-reverse", action="store_true", help="reverse collected order to probe shared-state/order flakiness")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--vt012-reverse"):
        items.reverse()
