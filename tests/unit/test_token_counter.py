from src.utils.token_counter import count_tokens, truncate_to_token_count


def test_empty_text_is_zero_tokens():
    assert count_tokens("") == 0


def test_short_nonempty_text_is_at_least_one_token():
    assert count_tokens("hi") == 1


def test_longer_text_scales_with_length():
    short = count_tokens("a" * 40)
    long = count_tokens("a" * 400)

    assert long > short
    assert long == 100
    assert short == 10


def test_truncate_never_exceeds_requested_token_count():
    text = "word " * 1000

    truncated = truncate_to_token_count(text, max_tokens=50)

    assert count_tokens(truncated) <= 50


def test_truncate_is_a_prefix_of_the_original_text():
    text = "The quick brown fox jumps over the lazy dog. " * 20

    truncated = truncate_to_token_count(text, max_tokens=10)

    assert text.startswith(truncated)
