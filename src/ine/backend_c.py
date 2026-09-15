"""Target: native machine code via emitted C.

The smallest slice: `say` statements are lowered into a small C program
that prints the same values to stdout. The C is compiled by an external
C compiler (zig cc, clang, or gcc) into a native executable the CPU runs
directly.

Emission is pure (strings in, strings out) so it stays testable. Finding
the compiler, writing files, and invoking it belong to the build step.
"""

from .parser import SayStatement


def _c_escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _printf_line(statement):
    value = statement.value
    if isinstance(value, bool):
        return f'    printf("%s\\n", "true" if {int(value)} else "false");'
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return f'    printf("%.17g\\n", {value!r});'
        return f'    printf("%d\\n", {value});'
    return f'    printf("%s\\n", "{_c_escape(value)}");'


def emit(statements):
    """Lower statements into C source text. Only `say` is lowered today."""
    lines = ["#include <stdio.h>", "", "int main(void) {"]
    for statement in statements:
        if isinstance(statement, SayStatement):
            lines.append(_printf_line(statement))
    lines.append("    return 0;")
    lines.append("}")
    return "\n".join(lines) + "\n"