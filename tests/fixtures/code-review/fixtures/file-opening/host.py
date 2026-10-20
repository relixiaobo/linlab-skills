from pathlib import Path


def open_file(sender, path, trusted_senders):
    if sender not in trusted_senders:
        raise PermissionError("Untrusted sender")
    if not isinstance(path, str) or not Path(path).is_absolute():
        raise ValueError("Expected an absolute path")
    return Path(path).read_bytes()
