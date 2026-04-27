"""File operations — create, move, rename, delete, list."""

import os
import re
import shutil

FILE_PATTERNS = [
    re.compile(r"^create (?:a )?file (?:called |named )?(.+)$", re.I),
    re.compile(r"^(?:make|touch) (?:a )?file (.+)$", re.I),
    re.compile(r"^delete (?:the )?file (.+)$", re.I),
    re.compile(r"^remove (?:the )?file (.+)$", re.I),
    re.compile(r"^move (?:the )?file (.+?) to (.+)$", re.I),
    re.compile(r"^rename (?:the )?file (.+?) to (.+)$", re.I),
    re.compile(r"^list files (?:in )?(.+)$", re.I),
    re.compile(r"^(?:show|what(?:'s| is) in) (?:the )?folder (.+)$", re.I),
    re.compile(r"^read (?:the )?file (.+)$", re.I),
]


def _safe_path(path_str):
    path_str = path_str.strip().strip("'\"")
    expanded = os.path.expanduser(os.path.expandvars(path_str))
    return os.path.abspath(expanded)


def write_to_file(path_str, content):
    path = _safe_path(path_str)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False


def is_file_request(text):
    normalized = " ".join(str(text).strip().split())
    return any(p.match(normalized) for p in FILE_PATTERNS)


def handle_file_command(text):
    normalized = " ".join(str(text).strip().split())

    # Create
    m = re.match(r"^(?:create|make|touch) (?:a )?file (?:called |named )?(.+)$", normalized, re.I)
    if m:
        path = _safe_path(m.group(1))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a"):
                pass
            return {"action": "file_create", "reply": f"Created file: {path}"}
        except Exception as e:
            return {"action": "file_create", "reply": f"Could not create file: {e}", "success": False, "error": str(e)}

    # Write content (Internal/Direct)
    m = re.match(r"^write (?:text |content )?\"(.+?)\" to (?:the )?file (.+)$", normalized, re.I)
    if m:
        content = m.group(1)
        path = m.group(2)
        if write_to_file(path, content):
            return {"action": "file_write", "reply": f"Written content to {path}", "success": True}
        return {"action": "file_write", "reply": f"Failed to write to {path}", "success": False, "error": "Unknown write error"}

    # Delete
    m = re.match(r"^(?:delete|remove) (?:the )?file (.+)$", normalized, re.I)
    if m:
        path = _safe_path(m.group(1))
        if not os.path.exists(path):
            return {"action": "file_delete", "reply": f"File not found: {path}"}
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"action": "file_delete", "reply": f"Deleted: {path}"}
        except Exception as e:
            return {"action": "file_delete", "reply": f"Could not delete: {e}", "success": False, "error": str(e)}

    # Move
    m = re.match(r"^move (?:the )?file (.+?) to (.+)$", normalized, re.I)
    if m:
        src = _safe_path(m.group(1))
        dst = _safe_path(m.group(2))
        try:
            shutil.move(src, dst)
            return {"action": "file_move", "reply": f"Moved {src} to {dst}"}
        except Exception as e:
            return {"action": "file_move", "reply": f"Could not move: {e}", "success": False, "error": str(e)}

    # Rename
    m = re.match(r"^rename (?:the )?file (.+?) to (.+)$", normalized, re.I)
    if m:
        src = _safe_path(m.group(1))
        dst = _safe_path(m.group(2))
        try:
            os.rename(src, dst)
            return {"action": "file_rename", "reply": f"Renamed to {dst}"}
        except Exception as e:
            return {"action": "file_rename", "reply": f"Could not rename: {e}", "success": False, "error": str(e)}

    # List
    m = re.match(r"^(?:list files (?:in )?|(?:show|what(?:'s| is) in) (?:the )?folder )(.+)$", normalized, re.I)
    if m:
        path = _safe_path(m.group(1))
        if not os.path.isdir(path):
            return {"action": "file_list", "reply": f"Not a directory: {path}"}
        try:
            entries = os.listdir(path)[:25]
            if not entries:
                return {"action": "file_list", "reply": f"{path} is empty."}
            listing = ", ".join(entries)
            return {"action": "file_list", "reply": f"Contents of {path}: {listing}"}
        except Exception as e:
            return {"action": "file_list", "reply": f"Could not list: {e}"}

    # Read
    m = re.match(r"^read (?:the )?file (.+)$", normalized, re.I)
    if m:
        path = _safe_path(m.group(1))
        if not os.path.isfile(path):
            return {"action": "file_read", "reply": f"File not found: {path}"}
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(2000)
            preview = content[:500]
            return {"action": "file_read", "reply": f"File contents: {preview}"}
        except Exception as e:
            return {"action": "file_read", "reply": f"Could not read: {e}"}

    return None
