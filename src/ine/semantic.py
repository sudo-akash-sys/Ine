"""Turns syntax statements into the semantic model."""

from dataclasses import dataclass, field

from . import dictionary
from .parser import GroupStatement, InsideStatement, MakeStatement, PropertyRef, PropertyStatement, SayStatement


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
    groups: dict = field(default_factory=dict)


def analyze(statements):
    model = Model()
    statements = _expand_groups(statements, model)
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


def _expand_groups(statements, model):
    """Turn groups into ordinary per-entity statements.

    `group cards = card-1 card-2 card-3` names a collection. A statement
    that targets the group expands to one statement per member:
    `cards inside card-group` becomes one `inside` per member, and a
    property on the group becomes a property on each member. Groups are
    recorded in the model but are otherwise transparent to the backends.
    """
    declared = {
        s.target for s in statements if isinstance(s, MakeStatement)
    }
    groups = {}

    for statement in statements:
        if not isinstance(statement, GroupStatement):
            continue
        if statement.name in declared:
            raise SemanticError(
                f"'{statement.name}' is an entity and cannot also be a group name",
                statement.line,
            )
        if statement.name in groups:
            raise SemanticError(
                f"group '{statement.name}' was defined twice", statement.line
            )
        for member in statement.members:
            if member not in declared:
                raise SemanticError(
                    f"group '{statement.name}' references '{member}' "
                    "which was not declared with 'make'",
                    statement.line,
                )
        groups[statement.name] = statement.members
    model.groups = groups

    expanded = []
    for statement in statements:
        if isinstance(statement, GroupStatement):
            continue
        if isinstance(statement, InsideStatement) and statement.child in groups:
            for member in groups[statement.child]:
                expanded.append(
                    InsideStatement(member, statement.parent, statement.line)
                )
        elif isinstance(statement, PropertyStatement) and statement.target in groups:
            for member in groups[statement.target]:
                expanded.append(
                    PropertyStatement(
                        member, statement.name, statement.value, statement.line
                    )
                )
        else:
            expanded.append(statement)
    return expanded


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


def advisory_warnings(model) -> list[str]:
    """Dictionary-backed, advisory-only warnings about a built model.

    The dictionary is the semantics authority (DECISIONS 49), but these
    checks never raise and never stop the build — each finding is a string
    the CLI prints to stderr, and the model still renders as-is. Checks:

    - a property whose name the kind does not declare (`properties_for`),
      with `title`/`text` covered by the universal entry;
    - a property value outside the kind's declared vocabulary, i.e. not a
      key in the property's `style` values map (e.g. `padding "banana"`),
      skipping free-form strings on undeclared or unvocabularized kinds;
    - containment where the child's kind is not in the parent kind's
      `members`, using the dictionary's `parents`/`contains` data.

    Kinds the dictionary does not declare (custom domains such as Alice's
    `person`) are skipped entirely: the dictionary has nothing to say.
    """

    found = []
    for (entity_id, name), value in model.properties.items():
        kind = model.entities[entity_id].kind
        declared = dictionary.properties_for(kind)
        if not declared:
            continue
        if name not in declared:
            found.append(
                f"'{entity_id}' has property '{name}', which kind '{kind}' does not declare"
            )
            continue
        words = _value_words(kind, name)
        if words and isinstance(value, str) and value not in words:
            found.append(
                f"'{entity_id}' property '{name}' value '{value}' is not a declared "
                f"{name} for kind '{kind}'"
            )
    for child, parent in model.relationships.items():
        child_kind = model.entities[child].kind
        parent_kind = model.entities[parent].kind
        members = dictionary.members(parent_kind)
        if members and child_kind not in members:
            found.append(
                f"'{child}' ({child_kind}) inside '{parent}' ({parent_kind}) "
                f"is not declared containment for kind '{parent_kind}'"
            )
    return found


def _value_words(kind, name) -> set[str]:
    """The words a kind's property accepts.

    The union of two declared vocabularies: the exact CSS-value words of the
    property's `style.values` map, and the `properties`-block `"choice"`
    options (e.g. card-group `layout` row/column). A property with neither
    (including the universal `title`/`text`, which map to no style) returns
    an empty set, so free text is never flagged.
    """
    words: set[str] = set()
    shape = dictionary.value_shape(kind, name)
    if shape.type == "choice":
        words.update(shape.choices)
    entry = dictionary.find(kind)
    if entry is None:
        return words
    style = entry.get("style")
    if not isinstance(style, dict):
        return words
    properties = style.get("properties")
    if not isinstance(properties, dict):
        return words
    spec = properties.get(name)
    if not isinstance(spec, dict):
        return words
    values = spec.get("values")
    if not isinstance(values, dict):
        return words
    words.update(values)
    return words