"""Parse the observed UE1 map-export subset without evaluating Unreal values.

Source order, spelling, property values, and the original text are retained.
Omitted properties remain omitted: class defaults are not part of a T3D export.
"""

from dataclasses import dataclass, field
import math
import re


class T3DError(ValueError):
    """An unsupported or malformed export, with a one-based source line."""

    def __init__(self, message: str, line: int):
        self.line = line
        super().__init__(f"line {line}: {message}")


@dataclass(frozen=True)
class Assignment:
    name: str
    value: str
    line: int


@dataclass(frozen=True)
class Record:
    name: str
    value: str
    line: int


@dataclass(frozen=True)
class Block:
    kind: str
    attributes: tuple[Assignment, ...]
    entries: tuple["Block | Assignment | Record", ...]
    line: int
    end_line: int

    def children(self, kind: str) -> tuple["Block", ...]:
        return tuple(e for e in self.entries if isinstance(e, Block) and e.kind == kind)

    @property
    def properties(self) -> tuple[Assignment, ...]:
        return tuple(e for e in self.entries if isinstance(e, Assignment))

    def attribute(self, name: str) -> str | None:
        return _single(self.attributes, name, self.line)

    def property(self, name: str) -> str | None:
        return _single(self.properties, name, self.line)


@dataclass(frozen=True)
class Document:
    root: Block
    source_text: str

    @property
    def actors(self) -> tuple[Block, ...]:
        return self.root.children("Actor")


@dataclass(frozen=True)
class Polygon:
    block: Block
    origin: tuple[float, float, float]
    normal: tuple[float, float, float]
    texture_u: tuple[float, float, float]
    texture_v: tuple[float, float, float]
    pan: tuple[int, int]
    vertices: tuple[tuple[float, float, float], ...]


_KEY = re.compile(r"[A-Za-z_]\w*(?:\(\d+\))?")
_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_CHILDREN = {None: {"Map"}, "Map": {"Actor"}, "Actor": {"Brush"},
             "Brush": {"PolyList"}, "PolyList": {"Polygon"}, "Polygon": set()}


def _single(values: tuple[Assignment, ...], name: str, line: int) -> str | None:
    matches = [v.value for v in values if v.name == name]
    if len(matches) > 1:
        raise T3DError(f"duplicate {name!r}; cannot choose a value", line)
    return matches[0] if matches else None


def _parts(text: str, separator: str | None, line: int) -> list[str]:
    """Split outside quoted strings and nested parentheses; retain raw values."""
    parts, start, depth = [], 0, 0
    quote = None
    escaped = False
    for index, char in enumerate(text):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                raise T3DError("unmatched closing parenthesis", line)
        elif depth == 0 and (char.isspace() if separator == "space" else char == separator):
            part = text[start:index].strip()
            if part:
                parts.append(part)
            elif separator != "space":
                raise T3DError("empty field", line)
            start = index + 1
    if quote or depth:
        raise T3DError("unterminated quote or parenthesis", line)
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    elif text.strip() and separator != "space":
        raise T3DError("empty final field", line)
    return parts


def _assignments(text: str, separator: str | None, line: int) -> tuple[Assignment, ...]:
    result = []
    for part in _parts(text, separator, line):
        key, equal, value = part.partition("=")
        key, value = key.strip(), value.strip()
        if not equal or not _KEY.fullmatch(key) or not value:
            raise T3DError(f"expected name=value, got {part!r}", line)
        result.append(Assignment(key, value, line))
    return tuple(result)


def parse_struct(value: str, line: int) -> tuple[Assignment, ...]:
    """Read specified fields only, including nested values kept as text."""
    if not value.startswith("(") or not value.endswith(")"):
        raise T3DError(f"expected parenthesized fields, got {value!r}", line)
    return _assignments(value[1:-1], ",", line)


def number(value: str, line: int) -> float:
    if not _NUMBER.fullmatch(value):
        raise T3DError(f"invalid numeric token {value!r}", line)
    result = float(value)
    if not math.isfinite(result):
        raise T3DError(f"non-finite numeric token {value!r}", line)
    return result


def integer(value: str, line: int) -> int:
    if not re.fullmatch(r"[+-]?\d+", value):
        raise T3DError(f"expected integer, got {value!r}", line)
    return int(value)


def vector(value: str, line: int) -> tuple[float, float, float]:
    fields = value.split(",")
    if len(fields) != 3:
        raise T3DError("polygon vector must contain three components", line)
    return tuple(number(v.strip(), line) for v in fields)


@dataclass
class _Builder:
    kind: str
    attributes: tuple[Assignment, ...]
    line: int
    entries: list[Block | Assignment | Record] = field(default_factory=list)


def parse_t3d(text: str) -> Document:
    stack: list[_Builder] = []
    root = None
    for line, source in enumerate(text.splitlines(), 1):
        row = source.strip()
        if not row or row.startswith("//"):
            continue
        begin = re.fullmatch(r"Begin (\w+)(?:\s+(.*))?", row)
        end = re.fullmatch(r"End (\w+)", row)
        if begin:
            kind, header = begin.groups()
            parent = stack[-1].kind if stack else None
            if kind not in _CHILDREN.get(parent, set()) or (parent is None and root):
                raise T3DError(f"unsupported {kind} block inside {parent or 'document'}", line)
            attrs = _assignments(header or "", "space", line)
            if len({a.name for a in attrs}) != len(attrs):
                raise T3DError("duplicate header attribute", line)
            if kind == "Actor" and not {"Class", "Name"} <= {a.name for a in attrs}:
                raise T3DError("Actor requires Class and Name", line)
            stack.append(_Builder(kind, attrs, line))
        elif end:
            if not stack or stack[-1].kind != end[1]:
                raise T3DError(f"unexpected {row}", line)
            item = stack.pop()
            block = Block(item.kind, item.attributes, tuple(item.entries), item.line, line)
            if stack:
                stack[-1].entries.append(block)
            else:
                root = block
        elif not stack:
            raise T3DError("content outside Map", line)
        elif stack[-1].kind == "Actor":
            # One property per line. Commas and whitespace inside values are retained.
            values = _assignments(row, None, line)
            stack[-1].entries.extend(values)
        elif stack[-1].kind == "Polygon":
            match = re.fullmatch(r"(\w+)\s+(.+)", row)
            if not match:
                raise T3DError("expected polygon record", line)
            stack[-1].entries.append(Record(match[1], match[2], line))
        else:
            raise T3DError(f"unsupported content in {stack[-1].kind}", line)
    if stack:
        raise T3DError(f"unclosed {stack[-1].kind} block", stack[-1].line)
    if root is None:
        raise T3DError("missing Map block", 1)
    return Document(root, text)


def read_polygon(block: Block) -> Polygon:
    """Decode polygon records strictly, leaving headers and source values intact."""
    if block.kind != "Polygon":
        raise T3DError("expected Polygon block", block.line)
    records: dict[str, list[Record]] = {}
    for entry in block.entries:
        if not isinstance(entry, Record) or entry.name not in {
            "Origin", "Normal", "TextureU", "TextureV", "Pan", "Vertex"
        }:
            raise T3DError("unsupported polygon record", entry.line)
        records.setdefault(entry.name, []).append(entry)
    for key in ("Origin", "Normal", "TextureU", "TextureV", "Pan"):
        if len(records.get(key, [])) != 1:
            raise T3DError(f"Polygon requires exactly one {key}", block.line)
    vertices = records.get("Vertex", [])
    if len(vertices) < 3:
        raise T3DError("Polygon requires at least three vertices", block.line)
    pan = records["Pan"][0]
    fields = _assignments(pan.value, "space", pan.line)
    if sorted(a.name for a in fields) != ["U", "V"]:
        raise T3DError("Pan requires U and V", pan.line)
    uv = {a.name: integer(a.value, a.line) for a in fields}
    vectors = [vector(records[k][0].value, records[k][0].line)
               for k in ("Origin", "Normal", "TextureU", "TextureV")]
    return Polygon(block, *vectors, (uv["U"], uv["V"]),
                   tuple(vector(v.value, v.line) for v in vertices))
