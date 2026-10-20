from pathlib import Path


def open_clicked_path(path, ipc):
    if not isinstance(path, str) or not Path(path).is_absolute():
        return {"error": "Choose an absolute local file path"}
    return ipc.open_file(path)
