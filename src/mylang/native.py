"""Build step: statements -> native executable, using the project .tmp dir.

Everything generated here (the .c source, the .obj/.exe) is an
intermediate artifact and lives under <project>/.tmp/native/. Nothing
generated here is committed.
"""

import os
import shutil
import subprocess

from .backend_c import emit

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
NATIVE_TMP = os.path.join(PROJECT_ROOT, ".tmp", "native")


class NativeError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def find_c_compiler():
    """Return (kind, command) for an available C compiler."""
    env_cc = os.environ.get("MYLANG_CC")
    if env_cc:
        return ("env", env_cc)
    for name in ("zig", "clang", "gcc", "cc"):
        path = shutil.which(name)
        if path:
            return (name, path)
    return None


def compile_c(statements, name, work_dir=None):
    """Emit C, compile it to a native executable. Returns (c_path, exe_path)."""
    if work_dir is None:
        work_dir = NATIVE_TMP
    os.makedirs(work_dir, exist_ok=True)

    c_path = os.path.join(work_dir, name + ".c")
    with open(c_path, "w", encoding="utf-8") as handle:
        handle.write(emit(statements))

    exe_path = os.path.join(work_dir, name + ".exe")
    toolchain = find_c_compiler()
    if toolchain is None:
        raise NativeError(
            "no C compiler found. Install Zig (zig cc), LLVM clang, or gcc, "
            "or set MYLANG_CC to your compiler command."
        )

    kind, compiler = toolchain
    if kind == "zig":
        args = [compiler, "cc", c_path, "-o", exe_path]
    else:
        args = [compiler, c_path, "-o", exe_path]

    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        raise NativeError(
            f"{kind} failed to compile ({result.returncode}): {result.stderr}"
        )
    return c_path, exe_path


def run_native(exe_path):
    """Execute the compiled native program and return its stdout."""
    result = subprocess.run([exe_path], capture_output=True, text=True)
    if result.returncode != 0:
        raise NativeError(f"native program exited {result.returncode}: {result.stderr}")
    return result.stdout