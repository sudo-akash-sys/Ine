"""Turns tokens into syntax statements."""

from dataclasses import dataclass

from .lexer import TokenKind


class SyntaxError(Exception):
    def __init__(self, message, token):
        super().__init__(message)
        self.message = message
        self.line = token.line


@dataclass(frozen=True)
class MakeStatement:
    target: str
    kind: str
    line: int


@dataclass(frozen=True)
class PropertyStatement:
    target: str
    name: str
    value: object
    line: int


@dataclass(frozen=True)
class SayStatement:
    value: object
    line: int


@dataclass(frozen=True)
class PropertyRef:
    target: str
    name: str
    line: int


def parse(tokens):
    statements = []
    pos = 0
    while tokens[pos].kind == TokenKind.NEWLINE:
        pos += 1
    while tokens[pos].kind != TokenKind.EOF:
        pos, statement = _parse_statement(tokens, pos)
        statements.append(statement)
        while tokens[pos].kind == TokenKind.NEWLINE:
            pos += 1
    return statements


def _parse_statement(tokens, pos):
    token = tokens[pos]
    if token.kind == TokenKind.KEYWORD and token.value == "make":
        return _parse_make(tokens, pos)
    if token.kind == TokenKind.KEYWORD and token.value == "say":
        return _parse_say(tokens, pos)
    if token.kind == TokenKind.IDENT:
        return _parse_property(tokens, pos)
    if token.kind == TokenKind.NEWLINE or token.kind == TokenKind.EOF:
        raise SyntaxError("expected a statement, found an empty line", token)
    raise SyntaxError("cannot understand this line", token)


def _parse_make(tokens, pos):
    make = tokens[pos]
    target = tokens[pos + 1]
    if target.kind != TokenKind.IDENT:
        raise SyntaxError("expected a name after 'make'", target)
    after = tokens[pos + 2]
    if after.kind == TokenKind.IDENT:
        kind = after.value
        end = pos + 3
    else:
        kind = target.value
        end = pos + 2
    if tokens[end].kind not in (TokenKind.NEWLINE, TokenKind.EOF):
        raise SyntaxError("unexpected extra text", tokens[end])
    return end, MakeStatement(target.value, kind, make.line)


def _parse_property(tokens, pos):
    target = tokens[pos]
    name = tokens[pos + 1]
    value = tokens[pos + 2]
    if name.kind != TokenKind.IDENT:
        raise SyntaxError("expected a property name", name)
    if value.kind not in (TokenKind.STRING, TokenKind.NUMBER):
        raise SyntaxError("property value must be a string in quotes or a number", value)
    after = tokens[pos + 3]
    if after.kind not in (TokenKind.NEWLINE, TokenKind.EOF):
        raise SyntaxError("unexpected extra text", after)
    return pos + 3, PropertyStatement(target.value, name.value, _literal(value), target.line)


def _parse_say(tokens, pos):
    say = tokens[pos]
    first = tokens[pos + 1]
    if first.kind in (TokenKind.STRING, TokenKind.NUMBER):
        value = _literal(first)
        end = pos + 2
    elif first.kind == TokenKind.IDENT:
        first_value, first_kind = first.value, first.kind
        prop = tokens[pos + 2]
        if prop.kind != TokenKind.IDENT:
            raise SyntaxError("expected a property name after the name in 'say'", prop)
        value = PropertyRef(first.value, prop.value, first.line)
        end = pos + 3
    else:
        raise SyntaxError("expected a string, a number, or a name property after 'say'", first)
    after = tokens[end]
    if after.kind not in (TokenKind.NEWLINE, TokenKind.EOF):
        raise SyntaxError("unexpected extra text", after)
    return end, SayStatement(value, say.line)


def _literal(token):
    if token.kind == TokenKind.NUMBER:
        text = token.value
        if any(marker in text for marker in (".", "e", "E")):
            return float(text)
        return int(text)
    return token.value