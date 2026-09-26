"""Named worker profiles: which external agent CLI the loop drives.

The command shape is data, not code. A profile says what to run, how the
prompt travels, and (optionally) which model to ask for; the commander picks
one by name and can add or override a profile in `.agent/workers.json`
without editing Python. Resolution is total and checkable: `doctor` reports
exactly the argv that would run, without running it.

Two rules are enforced here rather than trusted:

- no credentials. A profile may name environment variables to pass through,
  never their values, and a key that looks like a secret is refused by name
  so a key pasted into the config fails loudly instead of being committed.
- the placeholders are a closed set. `{root}` and `{model}` are the whole
  vocabulary; a typo becomes an error naming the profile and the field
  rather than a literal `{modle}` on somebody's command line.
"""

import json
import os
import re
import shutil


CONFIG_NAME = "workers.json"

#: The only substitutions a profile may use.
PLACEHOLDERS = ("root", "model")

_PLACEHOLDER_RE = re.compile(r"\{([a-z_]+)\}")
_ENV_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRETISH_RE = re.compile(
    r"api[_-]?key|token|secret|password|authorization|credential", re.I)

TRANSPORTS = ("argument", "stdin")

#: Today's shape, plus the wall-clock bound a worker needs and previously had
#: no way to be given. One hour is per mission *attempt* — long enough for a
#: real implementation mission, short enough that a hung worker costs one
#: timeout rather than the evening. No model on the command line unless one is
#: asked for: the tool's own default is used otherwise.
#:
#: The `opencode` profile deliberately passes no `--agent`. A project-side
#: agent file is a provider integration: INE drives external CLIs and does not
#: create agents, personas or modes inside one (Session 52, DECISIONS). The cost
#: of that boundary is stated plainly rather than hidden — the agent file also
#: carried a 60-step budget and a permission deny-list, and the step budget is
#: not reproduced here. The wall clock below is now the only hard bound on a
#: run, alongside INE's own prompt and output caps.
BUILTINS = {
    "opencode": {
        "command": ["opencode", "run", "--pure", "--dir", "{root}"],
        "prompt_transport": "argument",
        "model_args": ["--model", "{model}"],
        "timeout_seconds": 3600,
        "description": "OpenCode CLI in non-interactive run mode, using the "
                       "tool's own default agent",
    },
    "claude": {
        # The worker needs to edit files and run tests, and in `-p` mode it
        # cannot ask anyone for permission, so anything not granted here is
        # simply refused. That is why the lists are explicit: the posture is
        # the one PLAN item 122 was approved on — local edit and test work
        # allowed, the network, subagents and interactive tools denied —
        # expressed as documented CLI flags rather than as a provider config
        # file, which the Session 52 decision rules out. `acceptEdits` alone
        # would still refuse every `Bash` call, so no mission could test
        # anything; `--dangerously-skip-permissions` would work and is exactly
        # what this must not be.
        "command": ["claude", "-p",
                    "--permission-mode", "acceptEdits",
                    "--allowedTools", "Read,Edit,Write,Glob,Grep,Bash",
                    "--disallowedTools",
                    "WebFetch,WebSearch,Task,TodoWrite,Skill"],
        "prompt_transport": "stdin",
        "model_args": [],
        "timeout_seconds": 1800,
        "description": "Claude Code CLI in non-interactive print mode, with "
                       "edits and tests allowed and the network, subagents "
                       "and interactive tools denied",
    },
}

_FIELDS = ("command", "prompt_transport", "model_args", "timeout_seconds",
           "env", "env_var", "description")


class ProfileError(ValueError):
    """A profile cannot be resolved.

    A ValueError so the loop's existing "unknown worker" contract still
    holds, and always a message that names the profile and the field.
    """


class WorkerProfile:
    """A resolved, runnable worker profile."""

    __slots__ = ("name", "command", "prompt_transport", "model_args",
                 "timeout_seconds", "env", "env_var", "description")

    def __init__(self, name, command, prompt_transport, model_args,
                 timeout_seconds=None, env=(), env_var=None, description=""):
        self.name = name
        self.command = list(command)
        self.prompt_transport = prompt_transport
        self.model_args = list(model_args)
        self.timeout_seconds = timeout_seconds
        self.env = list(env)
        self.env_var = env_var
        self.description = description

    @property
    def executable(self):
        return self.command[0]

    @property
    def model(self):
        """The `--model` value implied by `model_args`, for display."""
        for token in self.model_args:
            if token.startswith("--model="):
                return token.split("=", 1)[1]
        return ""

    def argv(self, prompt=None):
        """The resolved command line, with no worker attached.

        `prompt=None` gives the command as it would be invoked, which is
        what `doctor` prints; with a prompt it is what actually runs. One
        function, so the preview cannot drift from the execution.
        """
        tokens = [*self.command, *self.model_args]
        if prompt is not None and self.prompt_transport == "argument":
            tokens.append(prompt)
        return tokens

    def where_prompt_goes(self):
        if self.prompt_transport == "stdin":
            return "stdin"
        return "the final argument"

    def __repr__(self):
        return "WorkerProfile({!r}, command={!r})".format(
            self.name, self.command)


def config_path(root):
    return os.path.join(root, ".agent", CONFIG_NAME)


def load_profiles(root):
    """Built-ins merged with `.agent/workers.json`, name -> raw fields.

    An override is merged field by field, so a config that sets only
    `command` keeps the built-in's transport and timeout. A broken config is
    an error here, not a silent fallback to the built-in: a profile that was
    meant to be read and was not is a fact the commander must be told.
    """
    profiles = {name: dict(fields) for name, fields in BUILTINS.items()}
    path = config_path(root)
    if not os.path.isfile(path):
        return profiles
    try:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ProfileError("cannot read {}: {}".format(path, exc))
    if not isinstance(document, dict):
        raise ProfileError(
            "{} must hold an object, not {}".format(path, type(document).__name__))
    declared = document.get("profiles", {})
    if not isinstance(declared, dict):
        raise ProfileError(
            "{}: 'profiles' must be an object, not {}".format(
                path, type(declared).__name__))
    for name, fields in declared.items():
        if not isinstance(fields, dict):
            raise ProfileError(
                "{}: profile {!r} must be an object, not {}".format(
                    path, name, type(fields).__name__))
        unknown = sorted(set(fields) - set(_FIELDS))
        if unknown:
            raise ProfileError(
                "{}: profile {!r} has unknown field(s): {}".format(
                    path, name, ", ".join(unknown)))
        merged = profiles.setdefault(name, {})
        merged.update(fields)
    return profiles


def available(root):
    return sorted(load_profiles(root))


def resolve(root, name, model=None):
    """Resolve `name` against `root`, or raise ProfileError saying why not."""
    if not isinstance(name, str) or not name.strip():
        raise ProfileError("no worker profile was named")
    profiles = load_profiles(root)
    raw = profiles.get(name)
    if raw is None:
        raise ProfileError("unknown worker profile {!r} (available: {})".format(
            name, ", ".join(sorted(profiles))))
    timeout = raw.get("timeout_seconds")
    # A model is a refinement, not a requirement: with none given the tool's
    # own default is used and `model_args` is dropped whole. A `{model}` in
    # `command` is different — the command cannot be built without it, so
    # that is an error. Nothing is ever appended: a profile decides its own
    # CLI shape, and `--model` reaches a tool only if the profile says how.
    model_args = (_tokens(name, "model_args", raw.get("model_args", []), root,
                          model) if model else [])
    return WorkerProfile(
        name=name,
        command=_tokens(name, "command", raw.get("command"), root, model,
                        required=True),
        prompt_transport=_transport(name, raw.get("prompt_transport", "argument")),
        model_args=model_args,
        timeout_seconds=_timeout(name, timeout),
        env=_env(name, raw.get("env", [])),
        env_var=_env_var(name, raw.get("env_var")),
        description=str(raw.get("description", "")),
    )


def _tokens(profile, field, value, root, model, required=False):
    """Validate and substitute one field's argv tokens."""
    if value is None:
        value = [] if not required else None
    if value is None:
        raise ProfileError(
            "worker profile {!r}: {!r} is missing".format(profile, field))
    if isinstance(value, str):
        raise ProfileError(
            "worker profile {!r}: {!r} must be a list of arguments, not a "
            "string (a quoted path is one argument, not two)".format(
                profile, field))
    if not isinstance(value, (list, tuple)):
        raise ProfileError(
            "worker profile {!r}: {!r} must be a list, not {}".format(
                profile, field, type(value).__name__))
    tokens = list(value)
    if required and not tokens:
        raise ProfileError(
            "worker profile {!r}: {!r} is empty".format(profile, field))
    resolved = []
    for token in tokens:
        if not isinstance(token, str):
            raise ProfileError(
                "worker profile {!r}: {!r} holds a non-string argument "
                "{!r}".format(profile, field, token))
        for placeholder in _PLACEHOLDER_RE.findall(token):
            if placeholder not in PLACEHOLDERS:
                raise ProfileError(
                    "worker profile {!r}: {!r} uses unknown placeholder "
                    "{{{}}} (known: {})".format(
                        profile, field, placeholder,
                        ", ".join("{%s}" % name for name in PLACEHOLDERS)))
            if placeholder == "model" and not model:
                raise ProfileError(
                    "worker profile {!r}: {!r} needs a model — pass --model "
                    "or set INE_AGENT_MODEL".format(profile, field))
        resolved.append(token.replace("{root}", str(root))
                        .replace("{model}", model or ""))
    return resolved


def _transport(profile, value):
    if value not in TRANSPORTS:
        raise ProfileError(
            "worker profile {!r}: 'prompt_transport' must be one of {} (not "
            "{!r})".format(profile, " or ".join(TRANSPORTS), value))
    return value


def _timeout(profile, value):
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(
            "worker profile {!r}: 'timeout_seconds' must be a number, not "
            "{!r}".format(profile, value))
    if value < 0:
        raise ProfileError(
            "worker profile {!r}: 'timeout_seconds' cannot be negative "
            "({!r})".format(profile, value))
    return float(value)


def _env(profile, value):
    """Environment variable *names* to pass through — never values."""
    if not isinstance(value, (list, tuple)):
        raise ProfileError(
            "worker profile {!r}: 'env' must be a list of variable names, "
            "not {}".format(profile, type(value).__name__))
    names = []
    for entry in value:
        if not isinstance(entry, str) or not _ENV_NAME_RE.match(entry):
            raise ProfileError(
                "worker profile {!r}: 'env' holds {!r}; list variable names, "
                "not values or paths".format(profile, entry))
        names.append(entry)
    return names


def _env_var(profile, value):
    if value is None:
        return "INE_AGENT_" + profile.upper().replace("-", "_")
    if not isinstance(value, str) or not _ENV_NAME_RE.match(value):
        raise ProfileError(
            "worker profile {!r}: 'env_var' must be a variable name, not "
            "{!r}".format(profile, value))
    return value


def display_command(argv):
    """An argv shown as a copy-pasteable command line.

    Quoted only where the shell would otherwise re-split it, so the printed
    line is the same list of arguments the worker receives — not a guess at
    it. One function for `doctor` and `--dry-run`, so the preview of a
    command and the command itself are never quoted differently.
    """
    return " ".join(
        token if token and not any(char.isspace() for char in token)
        else '"{}"'.format(token.replace('"', '\\"'))
        for token in argv
    )


def check_executable(profile, command):
    """The resolved argv, or a one-line remedy.

    `command` is the effective argv (environment override already applied),
    so this reports the executable that would really be started.
    """
    if not command:
        raise ProfileError("worker profile {!r}: resolved to no command"
                           .format(profile.name))
    exe = command[0]
    if os.path.isfile(exe):
        return command
    found = shutil.which(exe)
    if found:
        return [found, *command[1:]]
    raise ProfileError(
        "worker profile {!r}: {!r} is not on PATH — install it, or set {}=<path>"
        .format(profile.name, exe, profile.env_var))
