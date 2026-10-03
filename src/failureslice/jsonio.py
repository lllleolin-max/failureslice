"""Strict finite JSON, shared by files and the SDK."""
import json
import math
from pathlib import Path

MAX_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_INTEGER = 2**53 - 1


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def checked(value, depth=0):
    if depth > MAX_DEPTH:
        raise ValueError("JSON depth exceeds 32")
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return integer(value, "JSON integer", -MAX_INTEGER, MAX_INTEGER)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        return value
    if type(value) is str:
        value.encode("utf-8")
        return value
    if type(value) is list or type(value) is tuple:
        return [checked(x, depth + 1) for x in value]
    if type(value) is dict:
        if any(type(k) is not str for k in value):
            raise ValueError("JSON object keys must be strings")
        return {k: checked(v, depth + 1) for k, v in value.items()}
    raise ValueError("unsupported JSON type")


def canonical(value):
    raw = json.dumps(checked(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON byte budget exceeded")
    return raw


def _pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("duplicate JSON key")
        result[k] = v
    return result


def loads(raw):
    try:
        if type(raw) in (bytes, bytearray):
            if len(raw) > MAX_BYTES:
                raise ValueError("JSON byte budget exceeded")
            # json.loads(bytes) auto-detects UTF-16/32. External inputs and the
            # oracle protocol require UTF-8, so parse only explicitly decoded text.
            text = raw.decode("utf-8", errors="strict")
        elif type(raw) is str:
            if len(raw.encode("utf-8")) > MAX_BYTES:
                raise ValueError("JSON byte budget exceeded")
            text = raw
        else:
            raise ValueError("JSON input must be UTF-8 bytes or text")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        canonical(value)
        return value
    except (RecursionError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc


def read(path):
    with Path(path).open("rb") as stream:
        return loads(stream.read(MAX_BYTES + 1))


def exact_keys(value, required, optional=()):
    if type(value) is not dict or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError("object has missing or unknown fields")
