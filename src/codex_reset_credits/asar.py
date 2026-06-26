from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AsarFile:
    path: Path
    header_size: int
    header_json_size: int
    header_json_string_size: int
    header: dict[str, Any]
    data_offset: int
    raw: bytes


def read_asar(path: Path) -> AsarFile:
    raw = path.read_bytes()
    if len(raw) < 16:
        raise ValueError(f"not an asar archive or too small: {path}")

    first, header_size, header_json_size, header_json_string_size = struct.unpack_from("<IIII", raw, 0)
    if first != 4:
        raise ValueError(f"unsupported asar header marker {first}: {path}")

    header_start = 16
    header_end = header_start + header_json_string_size
    header = json.loads(raw[header_start:header_end].decode("utf-8"))
    return AsarFile(
        path=path,
        header_size=header_size,
        header_json_size=header_json_size,
        header_json_string_size=header_json_string_size,
        header=header,
        data_offset=8 + header_size,
        raw=raw,
    )


def get_file(archive: AsarFile, archive_path: str) -> bytes:
    metadata = _metadata_for(archive.header, archive_path)
    if "offset" not in metadata or "size" not in metadata:
        raise KeyError(f"asar file has no offset/size metadata: {archive_path}")
    start = archive.data_offset + int(metadata["offset"])
    end = start + int(metadata["size"])
    return archive.raw[start:end]


def replace_file(archive: AsarFile, archive_path: str, content: bytes) -> bytes:
    metadata = _metadata_for(archive.header, archive_path)
    old_offset = int(metadata["offset"])
    old_size = int(metadata["size"])
    old_start = archive.data_offset + old_offset
    old_end = old_start + old_size
    delta = len(content) - old_size

    metadata["size"] = len(content)
    integrity = metadata.get("integrity")
    if isinstance(integrity, dict):
        import hashlib

        digest = hashlib.sha256(content).digest()
        integrity["hash"] = hashlib.sha256(content).hexdigest()
        integrity["blockSize"] = len(content)
        integrity["blocks"] = [hashlib.sha256(content).hexdigest()]

    if delta:
        for file_metadata in _iter_file_metadata(archive.header):
            if file_metadata is metadata or "offset" not in file_metadata:
                continue
            offset = int(file_metadata["offset"])
            if offset > old_offset:
                file_metadata["offset"] = str(offset + delta)

    packed_header = _pack_header(archive.header)
    return packed_header + archive.raw[archive.data_offset:old_start] + content + archive.raw[old_end:]


def iter_file_paths(archive: AsarFile):
    yield from _iter_file_paths(archive.header)


def _pack_header(header: dict[str, Any]) -> bytes:
    header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
    padded_len = (len(header_json) + 3) & ~3
    padded_json = header_json + b"\0" * (padded_len - len(header_json))
    return struct.pack("<IIII", 4, padded_len + 8, padded_len + 4, len(header_json)) + padded_json


def _metadata_for(header: dict[str, Any], archive_path: str) -> dict[str, Any]:
    node: dict[str, Any] = header
    for part in archive_path.strip("/").split("/"):
        files = node.get("files")
        if not isinstance(files, dict) or part not in files:
            raise KeyError(f"asar file not found: {archive_path}")
        child = files[part]
        if not isinstance(child, dict):
            raise KeyError(f"asar node is invalid: {archive_path}")
        node = child
    return node


def _iter_file_metadata(node: dict[str, Any]):
    files = node.get("files")
    if isinstance(files, dict):
        for child in files.values():
            if isinstance(child, dict):
                yield from _iter_file_metadata(child)
    elif "size" in node:
        yield node


def _iter_file_paths(node: dict[str, Any], prefix: str = ""):
    files = node.get("files")
    if not isinstance(files, dict):
        return

    for name, child in files.items():
        if not isinstance(child, dict):
            continue
        path = f"{prefix}/{name}" if prefix else name
        if "files" in child:
            yield from _iter_file_paths(child, path)
        elif "offset" in child and "size" in child:
            yield path
