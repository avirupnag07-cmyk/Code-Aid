import pytest

from app.engine.traceback_parser import TracebackParseError, parse_traceback


@pytest.mark.parametrize(
    "exception_line, expected",
    [
        ("AttributeError: 'NoneType' object has no attribute 'name'", "AttributeError"),
        ("TypeError: unsupported operand type(s)", "TypeError"),
        ("NameError: name 'missing' is not defined", "NameError"),
        ("ImportError: cannot import name 'x'", "ImportError"),
        ("ModuleNotFoundError: No module named 'x'", "ModuleNotFoundError"),
        ("KeyError: 'timeout'", "KeyError"),
        ("IndexError: list index out of range", "IndexError"),
        ("ValueError: invalid literal", "ValueError"),
        ("FileNotFoundError: [Errno 2] missing", "FileNotFoundError"),
        ("ZeroDivisionError: division by zero", "ZeroDivisionError"),
        ("AssertionError: expected value", "AssertionError"),
    ],
)
def test_supported_exception_families_are_classified(exception_line, expected):
    info = parse_traceback(
        'Traceback (most recent call last):\n'
        '  File "src/worker.py", line 19, in run\n'
        '    do_work()\n'
        f"{exception_line}\n"
    )
    assert info.exception_type == expected
    assert info.innermost_frame is not None
    assert info.innermost_frame.file == "src/worker.py"
    assert info.innermost_frame.line == 19
    assert info.innermost_frame.function == "run"


def test_parser_handles_pytest_error_prefix_and_empty_message():
    info = parse_traceback('E   AssertionError\n')
    assert info.exception_type == "AssertionError"
    assert info.message == ""


@pytest.mark.parametrize("value", ["", "not a traceback", "Traceback (most recent call last):\n"])
def test_malformed_tracebacks_fail_with_a_user_error(value):
    with pytest.raises(TracebackParseError):
        parse_traceback(value)


def test_traceback_size_limit_is_enforced():
    with pytest.raises(TracebackParseError, match="size limit"):
        parse_traceback("TypeError: nope", max_chars=5)
