"""Turns syntax statements into the semantic model."""

from dataclasses import dataclass, field

from .parser import InsideStatement, MakeStatement, PropertyRef, PropertyStatement, SayStatement


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
    relationships: dict = field(default_factory=dict)


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
        elif isinstance(statement, InsideStatement):
            _add_relationship(model, statement)
    return model


def _add_relationship(model, statement):
    child, parent = statement.child, statement.parent
    if child not in model.entities:
        raise SemanticError(
            f"'{child} inside {parent}' references '{child}' which was not declared with 'make'",
            statement.line,
        )
    if parent not in model.entities:
        raise SemanticError(
            f"'{child} inside {parent}' references '{parent}' which was not declared with 'make'",
            statement.line,
        )
    if child == parent:
        raise SemanticError(
            f"'{child}' cannot be inside itself", statement.line
        )
    if child in model.relationships:
        raise SemanticError(
            f"'{child}' is already inside "
            f"'{model.relationships[child]}'; it cannot also be inside '{parent}'",
            statement.line,
        )
    model.relationships[child] = parent
    _check_cycle(model, child, statement.line)


def _check_cycle(model, child, line):
    seen = set()
    current = child
    while current in model.relationships:
        if current in seen:
            raise SemanticError(
                f"'{current}' is part of a containment cycle", line
            )
        seen.add(current)
        current = model.relationships[current]


def resolve(statements, model):
    """Resolve property references in `say` to the model's stored values.

    A reference must point to a declared entity and a property that
    exists; otherwise it is a compile-time error.
    """
    resolved = []
    for statement in statements:
        if isinstance(statement, SayStatement) and isinstance(statement.value, PropertyRef):
            ref = statement.value
            if ref.target not in model.entities:
                raise SemanticError(
                    f"'say {ref.target} {ref.name}' references '{ref.target}' "
                    "which was not declared with 'make'",
                    statement.line,
                )
            key = (ref.target, ref.name)
            if key not in model.properties:
                raise SemanticError(
                    f"'say {ref.target} {ref.name}' references '{ref.target}' "
                    f"which has no property '{ref.name}'",
                    statement.line,
                )
            resolved.append(SayStatement(model.properties[key], statement.line))
        else:
            resolved.append(statement)
    return resolved