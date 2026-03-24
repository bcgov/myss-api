from app.routers.attachments import _sanitize_filename


def test_sanitize_strips_special_chars():
    assert _sanitize_filename('my"file<name>.pdf') == "my_file_name_.pdf"


def test_sanitize_strips_unicode():
    assert _sanitize_filename("r\u00e9sum\u00e9.pdf") == "r_sum_.pdf"


def test_sanitize_preserves_safe_chars():
    assert _sanitize_filename("my-file_name.2024.pdf") == "my-file_name.2024.pdf"


def test_sanitize_empty_returns_attachment():
    assert _sanitize_filename("") == "attachment"


def test_sanitize_strips_path_separators():
    # Slashes are replaced with _, dots are kept (they're in the allowlist)
    assert _sanitize_filename("../../etc/passwd") == ".._.._etc_passwd"
