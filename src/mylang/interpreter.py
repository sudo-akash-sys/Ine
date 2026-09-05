"""Executes the program's runtime statements (currently `say`)."""

from .parser import SayStatement


def execute(statements):
    outputs = []
    for statement in statements:
        if isinstance(statement, SayStatement):
            outputs.append(statement.value)
    return outputs