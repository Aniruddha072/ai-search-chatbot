import logging
import sys

import pytest

from src.utils.logging import _TurnIdFilter, configure_logging, get_logger, set_turn_id


@pytest.fixture(autouse=True)
def reset_turn_id():
    """ContextVars are process-global; without an explicit reset after every
    test (even a failing one), a turn_id set in one test would leak into
    whichever test runs next.
    """
    yield
    set_turn_id("-")


def _make_record() -> logging.LogRecord:
    return logging.LogRecord("test", logging.INFO, __file__, 0, "msg", (), None)


def test_get_logger_returns_named_logger():
    logger = get_logger("some.module")

    assert logger.name == "some.module"


def test_turn_id_filter_injects_current_turn_id():
    set_turn_id("turn-abc")

    record = _make_record()
    _TurnIdFilter().filter(record)

    assert record.turn_id == "turn-abc"


def test_turn_id_defaults_to_dash_when_unset():
    record = _make_record()
    _TurnIdFilter().filter(record)

    assert record.turn_id == "-"


def test_configure_logging_attaches_one_formatted_handler_to_root():
    configure_logging()
    root = logging.getLogger()

    assert len(root.handlers) == 1
    assert any(isinstance(f, _TurnIdFilter) for f in root.handlers[0].filters)


def test_configure_logging_writes_to_stderr_not_stdout():
    """cli.py streams answer text to stdout - logs must land on stderr so
    the two never interleave, even though both show up in one terminal.
    """
    configure_logging()
    root = logging.getLogger()

    assert root.handlers[0].stream is sys.stderr
