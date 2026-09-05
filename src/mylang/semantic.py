"""Turns syntax statements into the semantic model."""

from dataclasses import dataclass, field

from .parser import MakeStatement, PropertyStatement


class SemanticError(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line


@dataclass
class Entity:
    id: str
    kind: str


@dataclass
class Model:
    entities: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)


def analyze(statements):
    model = Model()
    for statement in statements:
        if isinstance(statement, MakeStatement):
            if statement.target in model.entities:
                raise SemanticError(
                    f"entity '{statement.target}' was defined twice", statement.line
                )
            model.entities[statement.target] = Entity(statement.target, statement.kind)
        elif isinstance(statement, PropertyStatement):
            if statement.target not in model.entities:
                raise SemanticError(
                    f"'{statement.target}' has a property but was not declared with 'make'",
                    statement.line,
                )
            model.properties[(statement.target, statement.name)] = statement.value
    return model