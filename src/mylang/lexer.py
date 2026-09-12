"""Turns .ine source text into tokens."""

from dataclasses import dataclass
from enum import Enum


class TokenKind(Enum):
    KEYWORD = "keyword"
    IDENT = "ident"
    NUMBER = "number"
    STRING = "string"
    NEWLINE = "newline"
    EOF = "eof"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    line: int
    column: int


KEYWORDS = {"make", "say", "inside"}


class LexError(Exception):
    def __init__(self, message, line, column):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def lex(source):
    tokens = []
    i = 0
    line = 1
    column = 1
    length = len(source)

    while i < length:
        ch = source[i]
        if ch in " \t\r":
            i += 1
            column += 1
        elif ch == "\n":
            tokens.append(Token(TokenKind.NEWLINE, "\n", line, column))
            i += 1
            line += 1
            column = 1
        elif ch == "#":
            while i < length and source[i] != "\n":
                i += 1
                column += 1
        elif ch == '"':
            start_line = line
            start_column = column
            i += 1
            column += 1
            chars = []
            while i < length and source[i] != '"':
                if source[i] == "\n":
                    raise LexError("unterminated string", start_line, start_column)
                chars.append(source[i])
                i += 1
                column += 1
            if i >= length:
                raise LexError("unterminated string", start_line, start_column)
            i += 1
            column += 1
            tokens.append(Token(TokenKind.STRING, "".join(chars), start_line, start_column))
        elif ch.isalpha() or ch == "_":
            start_line = line
            start_column = column
            start = i
            while i < length and (source[i].isalnum() or source[i] in "_-"):
                i += 1
                column += 1
            word = source[start:i]
            kind = TokenKind.KEYWORD if word in KEYWORDS else TokenKind.IDENT
            tokens.append(Token(kind, word, start_line, start_column))
        elif ch.isdigit():
            start_line = line
            start_column = column
            start = i
            while i < length and (source[i].isalnum() or source[i] in "._"):
                i += 1
                column += 1
            tokens.append(Token(TokenKind.NUMBER, source[start:i], start_line, start_column))
        else:
            raise LexError(f"unexpected character {ch!r}", line, column)

    tokens.append(Token(TokenKind.EOF, "", line, column))
    return tokens