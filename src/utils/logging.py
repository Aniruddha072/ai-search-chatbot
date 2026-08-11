import contextvars
import logging
import sys

# A ContextVar holds a value that's local to the current async task/thread
# rather than global to the whole process. That matters here because the
# pipeline will run several searches concurrently with asyncio.gather — a
# plain global variable would let concurrent turns overwrite each other's
# turn_id. A ContextVar keeps each concurrent call's value isolated.
_turn_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "turn_id", default="-"
)


class _TurnIdFilter(logging.Filter):
    """Injects the current turn_id into every log record automatically."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.turn_id = _turn_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Set up one formatted handler on the root logger. Call once at startup.

    Logs to stderr, not stdout - presentation.cli prints streamed answer
    text to stdout, and the two must stay logically separate even though
    both land in the same terminal by default (Decision 13.2).
    """
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | turn=%(turn_id)s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    handler.addFilter(_TurnIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Standard per-module logger, e.g. get_logger(__name__)."""
    return logging.getLogger(name)


def set_turn_id(turn_id: str) -> None:
    """Tag all subsequent log lines in this task with a turn/request ID,
    so one user turn's logs can be grepped out of concurrent/interleaved
    output even though search, ranking, and generation log from different
    components.
    """
    _turn_id_var.set(turn_id)
