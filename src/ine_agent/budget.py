"""Token and context budgets, configurable in `.agent/workers.json`.

Safeguards, not instructions, and never a reason to fail legitimate work.
The defaults are the conservative numbers the loop already used, expressed
once:

    {
      "policy": {
        "max_prompt_chars": 12000,
        "max_previous_receipts": 3,
        "max_previous_receipt_chars": 2000,
        "max_attempts": 1
      }
    }

Three rules shape what this module is allowed to do:

- **A budget never truncates source.** The previous-receipt caps bound
  material this module generated; the prompt cap is a *report*. A mission
  that exceeds `max_prompt_chars` is announced, with the overage, and sent —
  because the context in it was asked for by the mission author, and silently
  dropping a declared file is worse than a large prompt.
- **Nothing here costs a request.** Every check is arithmetic over a string
  this process already holds. The whole point of the budget is to make the
  handoff cheap, so measuring it must not cost what it is measuring.
- **A bad config is an error, not a fallback.** A key spelled `max_promt_chars`
  fails loudly with the name, the same contract `profiles` uses, so a policy
  that was meant to apply and did not is visible immediately.
"""

import json
import os

DEFAULTS = {
    "max_prompt_chars": 12000,
    "max_previous_receipts": 3,
    "max_previous_receipt_chars": 2000,
    "max_attempts": 1,
}

KEYS = tuple(sorted(DEFAULTS))


class PolicyError(ValueError):
    """A policy in `.agent/workers.json` cannot be used.

    A ValueError so the existing "bad configuration is reported, not
    silently ignored" contract holds, and always naming the offending key.
    """


class Policy(dict):
    """The resolved budget, with the overrides recorded for the report.

    A dict rather than a class with attributes so it can be printed, compared
    and passed as a plain mapping by callers that want one field.
    """

    @property
    def configured(self):
        """The keys the config actually set, for `- policy` in the report."""
        return getattr(self, "_configured", {})


def _positive_int(key, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PolicyError(
            "policy.{} must be a whole number of 0 or more, not {!r}".format(
                key, value))
    return value


def load_policy(root, config_path=None):
    """The effective budget for `root`, defaults merged with any override.

    Returns a `Policy`. A missing file is the defaults and not an error; a
    file that exists and cannot be understood is an error, because a policy
    the commander wrote and the loop ignored is exactly the silent failure
    this module exists to prevent.
    """
    path = config_path or os.path.join(
        os.path.abspath(root), ".agent", "workers.json")
    values = dict(DEFAULTS)
    configured = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, ValueError) as exc:
            raise PolicyError("cannot read {}: {}".format(path, exc))
        if not isinstance(document, dict):
            raise PolicyError("{} must hold an object, not {}".format(
                path, type(document).__name__))
        policy = document.get("policy", {})
        if not isinstance(policy, dict):
            raise PolicyError("{}: 'policy' must be an object, not {}".format(
                path, type(policy).__name__))
        unknown = sorted(set(policy) - set(KEYS))
        if unknown:
            raise PolicyError(
                "{}: policy has unknown key(s): {}. Known keys are: "
                "{}".format(path, ", ".join(unknown), ", ".join(KEYS)))
        for key, value in policy.items():
            values[key] = _positive_int(key, value)
            configured[key] = value
    resolved = Policy(values)
    resolved._configured = configured
    return resolved
