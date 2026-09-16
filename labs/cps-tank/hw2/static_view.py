#!/usr/bin/env python3
"""Derive a source-based CFG for the teaching controller's supported C subset.

The analyzer handles blocks, if/else, simple statements, and returns. It
rejects unsupported control constructs rather than emitting a misleading
diagram. It does not preprocess macros or analyze arbitrary C programs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Optional

HERE = pathlib.Path(__file__).resolve().parent
FUNCTION = re.compile(r"\b(?:bool|_Bool)\s+controller_step\s*\((.*?)\)\s*\{", re.S)
BRACES = re.compile(
    r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]',
    re.S,
)
LEXEME = re.compile(
    r'\s+|/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    r'|->|==|!=|<=|>=|&&|\|\||\+\+|--|[A-Za-z_]\w*'
    r'|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[fFlLuU]*'
    r'|[{}();=<>+\-*/!,.\[\]&|?]',
    re.S,
)
UNSUPPORTED = {"for", "while", "do", "switch", "goto", "break", "continue"}


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Statement:
    kind: str
    text: str
    yes: tuple["Statement", ...] = ()
    no: tuple["Statement", ...] = ()


def function_parts(source: str) -> tuple[str, str]:
    match = FUNCTION.search(source)
    if match is None:
        raise ValueError("expected a bool controller_step(...) definition")
    opening = match.end() - 1
    depth = 0
    for item in BRACES.finditer(source, opening):
        if item.group() == "{":
            depth += 1
        elif item.group() == "}":
            depth -= 1
            if depth == 0:
                return match.group(1), source[opening + 1:item.start()]
    raise ValueError("controller_step has an unclosed body")


def tokenize(body: str) -> list[Token]:
    tokens = []
    position = 0
    while position < len(body):
        match = LEXEME.match(body, position)
        if match is None:
            raise ValueError("unsupported C token near " + repr(body[position:position + 24]))
        word = match.group()
        if not word.isspace() and not word.startswith(("/*", "//")):
            tokens.append(Token(word, position, match.end()))
        position = match.end()
    return tokens


class Parser:
    def __init__(self, body: str):
        self.body = body
        self.tokens = tokenize(body)
        self.index = 0

    def peek(self) -> str:
        return self.tokens[self.index].text if self.index < len(self.tokens) else ""

    def take(self, expected: Optional[str] = None) -> Token:
        if self.index >= len(self.tokens):
            raise ValueError("unexpected end of controller_step")
        token = self.tokens[self.index]
        if expected is not None and token.text != expected:
            raise ValueError("expected " + repr(expected) + ", found " + repr(token.text))
        self.index += 1
        return token

    def enclosed_condition(self) -> str:
        self.take("(")
        start = self.index
        depth = 1
        while depth:
            word = self.take().text
            depth += (word == "(") - (word == ")")
        end = self.index - 1
        if start == end:
            raise ValueError("empty branch condition")
        if any(token.text in {"&&", "||", "?"} for token in self.tokens[start:end]):
            raise ValueError("compound conditions are outside the supported CFG subset")
        return self.body[self.tokens[start].start:self.tokens[end - 1].end].strip()

    def simple_expression(self) -> str:
        start = self.index
        depth = 0
        while True:
            word = self.take().text
            if word in {"(", "["}:
                depth += 1
            elif word in {")", "]"}:
                depth -= 1
            elif word == ";" and depth == 0:
                break
            elif word in {"{", "}"}:
                raise ValueError("unsupported compound statement")
        end = self.index - 1
        if start == end:
            raise ValueError("empty C statement")
        if any(token.text in {"&&", "||", "?"} for token in self.tokens[start:end]):
            raise ValueError("compound expressions are outside the supported CFG subset")
        return self.body[self.tokens[start].start:self.tokens[end - 1].end].strip()

    def branch(self) -> tuple[Statement, ...]:
        if self.peek() == "{":
            self.take("{")
            result = self.sequence("}")
            self.take("}")
            return result
        return (self.statement(),)

    def statement(self) -> Statement:
        word = self.peek()
        if word in UNSUPPORTED:
            raise ValueError(word + " is outside the supported CFG subset")
        if word == "if":
            self.take("if")
            condition = self.enclosed_condition()
            yes = self.branch()
            no = ()
            if self.peek() == "else":
                self.take("else")
                no = self.branch()
            return Statement("if", condition, yes, no)
        if word == "else":
            raise ValueError("else without if")
        if word == "return":
            self.take("return")
            return Statement("return", self.simple_expression())
        return Statement("expression", self.simple_expression())

    def sequence(self, until: str = "") -> tuple[Statement, ...]:
        result = []
        while self.peek() != until:
            if not self.peek():
                if until:
                    raise ValueError("unclosed C block")
                break
            if self.peek() == "{":
                self.take("{")
                result.extend(self.sequence("}"))
                self.take("}")
            else:
                result.append(self.statement())
        return tuple(result)


def walk(statements: tuple[Statement, ...]):
    for statement in statements:
        yield statement
        if statement.kind == "if":
            yield from walk(statement.yes)
            yield from walk(statement.no)


def return_write_states(
    statements: tuple[Statement, ...], field: str, states: set[bool], found: set[bool]
) -> set[bool]:
    for statement in statements:
        if statement.kind == "if":
            yes = return_write_states(statement.yes, field, set(states), found)
            no = return_write_states(statement.no, field, set(states), found) if statement.no else set(states)
            states = yes | no
        elif statement.kind == "return":
            found.update(states)
            states = set()
        elif re.search(r"\bstate\s*->\s*" + re.escape(field) + r"\s*=(?!=)", statement.text):
            states = {True for _ in states}
    return states


def analyze_source(source: str) -> tuple[str, dict]:
    parameters, body = function_parts(source)
    statements = Parser(body).sequence()
    flat = list(walk(statements))
    conditions = [item.text for item in flat if item.kind == "if"]
    returns = [item.text for item in flat if item.kind == "return"]
    if not conditions or not returns:
        raise ValueError("controller_step needs a branch and a return")
    fields = {
        field for expression in returns
        for field in re.findall(r"\bstate\s*->\s*([A-Za-z_]\w*)", expression)
    }
    if len(fields) != 1:
        raise ValueError("expected one state field in controller return")
    field = fields.pop()
    parameter_names = [
        re.findall(r"[A-Za-z_]\w*", item)[-1]
        for item in parameters.split(",") if re.findall(r"[A-Za-z_]\w*", item)
    ]
    observation = next(
        (name for name in parameter_names if name != "state"
         and any(re.search(r"\b" + re.escape(name) + r"\b", condition) for condition in conditions)),
        None,
    )
    if observation is None:
        raise ValueError("no function parameter controls a branch")

    nodes: list[tuple[str, str, str]] = []
    edges: list[tuple[str, str, str]] = []

    def node(label: str, shape: str = "box") -> str:
        identifier = "n" + str(len(nodes))
        nodes.append((identifier, label, shape))
        return identifier

    def build(sequence: tuple[Statement, ...], successor: str) -> str:
        current = successor
        for item in reversed(sequence):
            if item.kind == "if":
                decision = node(item.text + "?", "diamond")
                yes = build(item.yes, current) if item.yes else current
                no = build(item.no, current) if item.no else current
                edges.extend([(decision, yes, "true"), (decision, no, "false")])
                current = decision
            else:
                label = ("return " if item.kind == "return" else "") + item.text + ";"
                step = node(label)
                edges.append((step, exit_node if item.kind == "return" else current, ""))
                current = step
        return current

    exit_node = node("exit", "oval")
    first = build(statements, exit_node)
    entry = node("entry", "oval")
    edges.append((entry, first, ""))
    lines = ["digraph controller_step {", "  rankdir=TB;", "  node [shape=box];"]
    for identifier, label, shape in nodes:
        lines.append("  " + identifier + " [label=" + json.dumps(label) + ", shape=" + shape + "];")
    for source_id, target_id, label in edges:
        suffix = " [label=" + json.dumps(label) + "]" if label else ""
        lines.append("  " + source_id + " -> " + target_id + suffix + ";")
    lines.append("}")

    return_states: set[bool] = set()
    return_write_states(statements, field, {False}, return_states)
    dependency = {
        "analysis_method": "source-derived structured CFG for controller_step",
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "external_observation": observation,
        "control_dependencies": conditions,
        "retained_state": field if False in return_states else None,
        "actuator_decision": field,
        "assumption_to_question": "the reported observation faithfully represents the process state",
        "student_prompt": "Explain a path that can keep the inlet open even while true tank level rises.",
    }
    return "\n".join(lines) + "\n", dependency


def generate(output: pathlib.Path, source_path: Optional[pathlib.Path] = None) -> pathlib.Path:
    source_file = source_path or HERE / "representations" / "controller.c"
    dot, dependency = analyze_source(source_file.read_text(encoding="utf-8"))
    output.mkdir(parents=True, exist_ok=True)
    (output / "controller_cfg.dot").write_text(dot, encoding="utf-8")
    (output / "dependency_map.json").write_text(
        json.dumps(dependency, indent=2) + "\n", encoding="utf-8"
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path, default=HERE / "runs" / "analysis")
    parser.add_argument(
        "--source", type=pathlib.Path,
        default=HERE / "representations" / "controller.c",
        help="C file to analyze (use a copy; this never changes the live PLC)",
    )
    args = parser.parse_args()
    print(generate(args.out, args.source))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
