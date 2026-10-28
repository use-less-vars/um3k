#!/usr/bin/env python3
"""Validate an ``emfit.job.v1`` document against its JSON Schema, stdlib only.

The schema is ``schemas/emfit.job.v1.schema.json``; the instance defaults to the shipped
example ``schemas/examples/microstrip_stub.job.json``. This tool exists because the job
contract at ``decisions.md:7012-7093`` (section 101.19) needs a conformance test a stranger
can run without installing anything: ``jsonschema`` is *used if it is importable*, as a
reported cross-check, and never as the mechanism that decides a verdict.

Exit codes
    0   the instance is valid against the schema
    1   the instance is invalid, or the cross-check disagrees with this validator
    2   usage, I/O or parse error, **or a schema keyword this validator does not implement**
        (fail closed: silently ignoring a keyword would accept instances the schema rejects)

The two positional arguments are both optional and default relative to the repository root,
which is found by walking up from this file until a directory containing ``schemas/``.

``--list-keywords`` prints every keyword the schema uses, with how many times it occurs and
whether this validator implements it, annotation-only (ignored by design) or does not
support it. It exits 0 either way: the inventory is a report, not a verdict.
"""

import argparse
import json
import os
import re
import sys

EXIT_VALID = 0
EXIT_INVALID = 1
EXIT_USAGE = 2

SCHEMA_RELPATH = os.path.join("schemas", "emfit.job.v1.schema.json")
INSTANCE_RELPATH = os.path.join("schemas", "examples", "microstrip_stub.job.json")

#: Keywords that carry no assertion; a validator may ignore them without changing meaning.
ANNOTATION_KEYWORDS = (
    "$schema", "$id", "title", "description", "default", "examples", "deprecated",
    "$comment",
)

#: Keywords this validator actually asserts.
IMPLEMENTED_KEYWORDS = (
    "$defs", "$ref", "type", "const", "enum", "properties", "required",
    "additionalProperties", "items", "minItems", "maxItems", "uniqueItems", "minimum",
    "maximum", "exclusiveMinimum", "exclusiveMaximum", "pattern", "minLength", "maxLength",
    "oneOf", "anyOf", "allOf", "not",
)

#: Keywords whose value is a single subschema.
_SUBSCHEMA_KEYWORDS = ("additionalProperties", "items", "not")
#: Keywords whose value is a list of subschemas.
_SUBSCHEMA_LIST_KEYWORDS = ("allOf", "anyOf", "oneOf")
#: Keywords whose value is a mapping of name -> subschema.
_SUBSCHEMA_MAP_KEYWORDS = ("properties", "$defs")


class SchemaError(Exception):
    """The schema itself is malformed, or uses something this validator cannot assert."""


# --------------------------------------------------------------------------- pointers


def escape_token(token):
    """Escape one JSON-pointer reference token (RFC 6901)."""
    return str(token).replace("~", "~0").replace("/", "~1")


def child(pointer, token):
    """The pointer of a child of the node at ``pointer``."""
    return pointer + "/" + escape_token(token)


def display(pointer):
    """How a pointer is printed. The root instance is ``/``."""
    return pointer if pointer else "/"


# --------------------------------------------------------------------------- schema walk


def iter_schema_nodes(root):
    """Yield ``(node, pointer)`` for every schema node in the document.

    Non-schema values (consts, enum members, descriptions) are not descended into, so
    walking the document here never mistakes instance data for schema.
    """
    stack = [(root, "")]
    while stack:
        node, pointer = stack.pop()
        if not isinstance(node, dict):
            continue
        yield node, pointer
        for key in _SUBSCHEMA_KEYWORDS:
            value = node.get(key)
            if isinstance(value, dict):
                stack.append((value, child(pointer, key)))
        for key in _SUBSCHEMA_LIST_KEYWORDS:
            value = node.get(key)
            if isinstance(value, list):
                for index, sub in enumerate(value):
                    if isinstance(sub, dict):
                        stack.append((sub, child(child(pointer, key), index)))
        for key in _SUBSCHEMA_MAP_KEYWORDS:
            value = node.get(key)
            if isinstance(value, dict):
                for name, sub in value.items():
                    if isinstance(sub, dict):
                        stack.append((sub, child(child(pointer, key), name)))


def keyword_status(keyword):
    """Classify one keyword: implemented, annotation-only, or UNSUPPORTED."""
    if keyword in IMPLEMENTED_KEYWORDS:
        return "implemented"
    if keyword in ANNOTATION_KEYWORDS:
        return "annotation-only"
    return "UNSUPPORTED"


def keyword_inventory(schema):
    """``[(keyword, count, status)]`` sorted by keyword, for the schema's own nodes."""
    counts = {}
    for node, _pointer in iter_schema_nodes(schema):
        for keyword in node:
            counts[keyword] = counts.get(keyword, 0) + 1
    return [(key, counts[key], keyword_status(key)) for key in sorted(counts)]


def unsupported_keywords(schema):
    """``[(keyword, pointer)]`` for every keyword this validator would silently ignore."""
    found = []
    for node, pointer in iter_schema_nodes(schema):
        for keyword in node:
            if keyword_status(keyword) == "UNSUPPORTED":
                found.append((keyword, child(pointer, keyword)))
    return sorted(found)


# --------------------------------------------------------------------------- helpers


def resolve_ref(root, ref):
    """Resolve a local ``#/$defs/NAME`` reference. Remote references are refused."""
    if not isinstance(ref, str) or not ref.startswith("#"):
        raise SchemaError("only local references are supported, got %r" % (ref,))
    fragment = ref[1:]
    if fragment == "":
        return root
    if not fragment.startswith("/"):
        raise SchemaError("unsupported reference %r: expected '#/$defs/NAME'" % (ref,))
    node = root
    for raw in fragment[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or token not in node:
            raise SchemaError("reference %r does not resolve: %r is absent" % (ref, token))
        node = node[token]
    return node


def json_type(value):
    """The JSON type name of a Python value, with ``bool`` kept out of the numbers."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def is_number(value):
    """A JSON number. ``True`` and ``False`` are not numbers, whatever Python thinks."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def type_matches(value, name):
    """Whether ``value`` is of JSON type ``name``. ``integer`` accepts an integral float."""
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "number":
        return is_number(value)
    if name == "integer":
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        return isinstance(value, float) and float(value).is_integer()
    raise SchemaError("unknown type keyword value %r" % (name,))


def same_value(left, right):
    """Equality that does not confuse ``True`` with ``1`` (as ``==`` does in Python)."""
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


def canonical(value):
    """A canonical rendering of a JSON value, for ``uniqueItems``."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def first_error(errors):
    """``(pointer, message)`` of the first error in a list, or ``None``."""
    return errors[0] if errors else None


# --------------------------------------------------------------------------- validation


def validate(instance, schema, root, pointer="", errors=None):
    """Validate ``instance`` against ``schema``, appending ``(pointer, message)`` errors."""
    if errors is None:
        errors = []
    if schema is True:
        return errors
    if schema is False:
        errors.append((pointer, "no value is allowed here: the schema is false"))
        return errors
    if not isinstance(schema, dict):
        raise SchemaError("a schema node must be an object or a boolean, got %r at %s"
                          % (json_type(schema), display(pointer)))

    if "$ref" in schema:
        target = resolve_ref(root, schema["$ref"])
        validate(instance, target, root, pointer, errors)

    if "type" in schema:
        declared = schema["type"]
        names = declared if isinstance(declared, list) else [declared]
        if not any(type_matches(instance, name) for name in names):
            errors.append((pointer, "expected type %s, got %s"
                           % ("/".join(repr(n) for n in names), json_type(instance))))

    if "const" in schema and not same_value(instance, schema["const"]):
        errors.append((pointer, "must be the constant %s, got %s"
                       % (json.dumps(schema["const"]), json.dumps(instance, default=repr))))

    if "enum" in schema:
        allowed = schema["enum"]
        if not any(same_value(instance, member) for member in allowed):
            errors.append((pointer, "must be one of %s, got %s"
                           % (json.dumps(allowed), json.dumps(instance, default=repr))))

    if is_number(instance):
        _validate_number(instance, schema, pointer, errors)

    if isinstance(instance, str):
        _validate_string(instance, schema, pointer, errors)

    if isinstance(instance, list):
        _validate_array(instance, schema, root, pointer, errors)

    if isinstance(instance, dict):
        _validate_object(instance, schema, root, pointer, errors)

    _validate_combinators(instance, schema, root, pointer, errors)
    return errors


def _validate_number(instance, schema, pointer, errors):
    if "minimum" in schema and instance < schema["minimum"]:
        errors.append((pointer, "%r is less than the minimum %r"
                       % (instance, schema["minimum"])))
    if "maximum" in schema and instance > schema["maximum"]:
        errors.append((pointer, "%r is greater than the maximum %r"
                       % (instance, schema["maximum"])))
    if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
        errors.append((pointer, "%r is not greater than the exclusive minimum %r"
                       % (instance, schema["exclusiveMinimum"])))
    if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
        errors.append((pointer, "%r is not less than the exclusive maximum %r"
                       % (instance, schema["exclusiveMaximum"])))


def _validate_string(instance, schema, pointer, errors):
    if "minLength" in schema and len(instance) < schema["minLength"]:
        errors.append((pointer, "must be at least %d characters long, got %d"
                       % (schema["minLength"], len(instance))))
    if "maxLength" in schema and len(instance) > schema["maxLength"]:
        errors.append((pointer, "must be at most %d characters long, got %d"
                       % (schema["maxLength"], len(instance))))
    if "pattern" in schema:
        try:
            matches = re.search(schema["pattern"], instance)
        except re.error as exc:
            raise SchemaError("pattern %r does not compile: %s" % (schema["pattern"], exc))
        if matches is None:
            errors.append((pointer, "%s does not match the pattern %s"
                           % (json.dumps(instance), json.dumps(schema["pattern"]))))


def _validate_array(instance, schema, root, pointer, errors):
    if "minItems" in schema and len(instance) < schema["minItems"]:
        errors.append((pointer, "must have at least %d item(s), got %d"
                       % (schema["minItems"], len(instance))))
    if "maxItems" in schema and len(instance) > schema["maxItems"]:
        errors.append((pointer, "must have at most %d item(s), got %d"
                       % (schema["maxItems"], len(instance))))
    if schema.get("uniqueItems") is True:
        seen = {}
        for index, item in enumerate(instance):
            key = canonical(item)
            if key in seen:
                errors.append((pointer, "items are not unique: index %d repeats index %d (%s)"
                               % (index, seen[key], key)))
            else:
                seen[key] = index
    if "items" in schema:
        item_schema = schema["items"]
        if isinstance(item_schema, list):
            raise SchemaError("tuple-form 'items' is not JSON Schema 2020-12; "
                              "use 'prefixItems' (unsupported here)")
        for index, item in enumerate(instance):
            validate(item, item_schema, root, child(pointer, index), errors)


def _validate_object(instance, schema, root, pointer, errors):
    for name in schema.get("required", []):
        if name not in instance:
            errors.append((pointer, "required property %r is missing" % (name,)))

    properties = schema.get("properties") or {}
    for name, subschema in properties.items():
        if name in instance:
            validate(instance[name], subschema, root, child(pointer, name), errors)

    additional = schema.get("additionalProperties", True)
    if additional is False:
        for name in instance:
            if name not in properties:
                errors.append((child(pointer, name),
                               "unexpected property %r: the object is closed "
                               "(additionalProperties is false)" % (name,)))
    elif isinstance(additional, dict):
        for name in instance:
            if name not in properties:
                validate(instance[name], additional, root, child(pointer, name), errors)


def _validate_combinators(instance, schema, root, pointer, errors):
    if "allOf" in schema:
        for branch in schema["allOf"]:
            validate(instance, branch, root, pointer, errors)

    if "anyOf" in schema:
        branches = schema["anyOf"]
        results = [validate(instance, b, root, pointer, []) for b in branches]
        if all(results):
            detail = "; ".join("branch %d: %s %s" % (i, display(first_error(r)[0]),
                                                     first_error(r)[1])
                               for i, r in enumerate(results))
            errors.append((pointer, "anyOf: none of %d branches matched; %s"
                           % (len(branches), detail)))

    if "oneOf" in schema:
        branches = schema["oneOf"]
        results = [validate(instance, b, root, pointer, []) for b in branches]
        matched = [i for i, r in enumerate(results) if not r]
        if not matched:
            detail = "; ".join("branch %d: %s %s" % (i, display(first_error(r)[0]),
                                                     first_error(r)[1])
                               for i, r in enumerate(results))
            errors.append((pointer, "oneOf: no branch matched (0 of %d); %s"
                           % (len(branches), detail)))
        elif len(matched) > 1:
            errors.append((pointer, "oneOf: %d branches matched (indices %s), expected "
                                    "exactly 1"
                           % (len(matched), ", ".join(str(i) for i in matched))))

    if "not" in schema:
        branch = schema["not"]
        if not validate(instance, branch, root, pointer, []):
            errors.append((pointer, "must not match the schema under 'not'"))


# --------------------------------------------------------------------------- cross-check


def cross_check(instance, schema):
    """Run ``jsonschema`` if it is importable. Reported, never decisive."""
    try:
        import jsonschema
    except Exception as exc:                      # ImportError under ``python3 -S``
        return {"available": False, "reason": "%s: %s" % (type(exc).__name__, exc)}
    try:
        validator = jsonschema.Draft202012Validator(schema)
        found = list(validator.iter_errors(instance))
    except Exception as exc:
        return {"available": True, "failed": "%s: %s" % (type(exc).__name__, exc)}
    return {"available": True, "failed": None, "count": len(found),
            "errors": found}


def report_cross_check(result, our_valid, stream):
    """Write one line (or a short block) describing the cross-check outcome."""
    if not result["available"]:
        stream.write("cross-check: NOT PERFORMED — jsonschema is not importable (%s)\n"
                     % result["reason"])
        return None
    if result.get("failed"):
        stream.write("cross-check: NOT PERFORMED — jsonschema failed: %s\n"
                     % result["failed"])
        return None
    their_valid = result["count"] == 0
    agreement = "agrees" if their_valid == our_valid else "DISAGREES"
    stream.write("cross-check: jsonschema %s — this validator says %s, jsonschema says %s "
                 "(%d error(s))\n"
                 % (agreement, "valid" if our_valid else "invalid",
                    "valid" if their_valid else "invalid", result["count"]))
    if their_valid == our_valid:
        return True
    for error in result["errors"][:10]:
        stream.write("  jsonschema %s: %s\n"
                     % (display("".join("/" + escape_token(t) for t in error.absolute_path)),
                        error.message))
    return False


# --------------------------------------------------------------------------- defaults


def repo_root(start):
    """Walk up from ``start`` until a directory containing ``schemas/`` is found."""
    here = os.path.dirname(os.path.abspath(start))
    current = here
    while True:
        if os.path.isdir(os.path.join(current, "schemas")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return here
        current = parent


# --------------------------------------------------------------------------- cli


def build_parser():
    """The argument parser, with defaults resolved against the repository root."""
    root = repo_root(__file__)
    parser = argparse.ArgumentParser(
        prog="validate-job-schema.py",
        description="Validate an emfit.job.v1 document against its JSON Schema "
                    "(standard library only).",
        epilog="Exit codes: 0 valid, 1 invalid or cross-check disagreement, "
               "2 usage/IO/parse error or unsupported schema keyword.")
    parser.add_argument("schema", nargs="?", default=os.path.join(root, SCHEMA_RELPATH),
                        help="the JSON Schema to validate against "
                             "(default: %(default)s)")
    parser.add_argument("instance", nargs="?", default=os.path.join(root, INSTANCE_RELPATH),
                        help="the job document to validate (default: %(default)s)")
    parser.add_argument("--list-keywords", action="store_true",
                        help="print the schema's keyword inventory and exit 0")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--cross-check", dest="cross_check", action="store_true",
                       default=None,
                       help="run jsonschema as a cross-check (default: auto, if importable)")
    group.add_argument("--no-cross-check", dest="cross_check", action="store_false",
                       default=None,
                       help="skip the jsonschema cross-check even if it is importable")
    return parser


def load_json(path, what):
    """Read and parse a JSON file, raising ``SchemaError`` with a usable message."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise SchemaError("cannot read the %s at %s: %s" % (what, path, exc.strerror or exc))
    try:
        return json.loads(text)
    except ValueError as exc:
        raise SchemaError("the %s at %s is not valid JSON: %s" % (what, path, exc))


def print_inventory(schema):
    """Print the keyword inventory: keyword, count, status."""
    rows = keyword_inventory(schema)
    width = max([len("keyword")] + [len(key) for key, _c, _s in rows])
    sys.stdout.write("%-*s  %5s  %s\n" % (width, "keyword", "count", "status"))
    sys.stdout.write("%s  %5s  %s\n" % ("-" * width, "-----", "-" * 15))
    for keyword, count, status in rows:
        sys.stdout.write("%-*s  %5d  %s\n" % (width, keyword, count, status))
    unsupported = [key for key, _c, status in rows if status == "UNSUPPORTED"]
    sys.stdout.write("\n%d distinct keyword(s); %s\n"
                     % (len(rows),
                        "0 unsupported" if not unsupported
                        else "%d UNSUPPORTED: %s" % (len(unsupported),
                                                     ", ".join(unsupported))))


def main(argv=None):
    """Run the validator. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        schema = load_json(args.schema, "schema")
    except SchemaError as exc:
        sys.stderr.write("FAIL %s: %s\n" % (args.schema, exc))
        return EXIT_USAGE
    if not isinstance(schema, dict):
        sys.stderr.write("FAIL %s: the schema root must be an object, got %s\n"
                         % (args.schema, json_type(schema)))
        return EXIT_USAGE

    if args.list_keywords:
        print_inventory(schema)
        return EXIT_VALID

    unsupported = unsupported_keywords(schema)
    if unsupported:
        sys.stderr.write("FAIL %s: %d unsupported schema keyword(s); refusing to validate "
                         "(fail closed)\n" % (args.schema, len(unsupported)))
        for keyword, pointer in unsupported:
            sys.stderr.write("  %s: keyword %r is not implemented\n"
                             % (display(pointer), keyword))
        return EXIT_USAGE

    try:
        instance = load_json(args.instance, "instance")
    except SchemaError as exc:
        sys.stderr.write("FAIL %s: %s\n" % (args.instance, exc))
        return EXIT_USAGE

    try:
        errors = validate(instance, schema, schema, "", [])
    except SchemaError as exc:
        sys.stderr.write("FAIL %s: %s\n" % (args.schema, exc))
        return EXIT_USAGE

    our_valid = not errors
    if errors:
        sys.stderr.write("FAIL %s: %d error(s)\n" % (args.instance, len(errors)))
        for pointer, message in errors:
            sys.stderr.write("  %s: %s\n" % (display(pointer), message))
    else:
        sys.stdout.write("OK %s: valid against %s\n" % (args.instance, args.schema))

    wanted = True if args.cross_check is None else args.cross_check
    agreed = True
    if wanted:
        result = cross_check(instance, schema)
        agreed = report_cross_check(result, our_valid, sys.stdout)

    if not our_valid:
        return EXIT_INVALID
    if not wanted or agreed is None or agreed:
        return EXIT_VALID
    return EXIT_INVALID                          # the cross-check disagreed


if __name__ == "__main__":
    sys.exit(main())
