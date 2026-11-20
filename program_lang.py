# SPDX-License-Identifier: GPL-3.0-only
# Copyright (c) 2026 Michael Giuseppe Aglieri
"""Small, safe language of offline programs: expressions and block structure.

Expressions use Python syntax restricted to numbers, true/false, names (program
variables or sensors), + - * / % //, comparisons and and/or/not. They are parsed with
`ast` and evaluated by walking a whitelist of nodes: no calls, attributes, indexing
or imports. Structure: `loop`/`if` open a body closed by `end`, `if` may have one
`else`; nesting is bounded.
"""
import ast
import math
import re

NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,39}$')
RESERVED = {'and', 'or', 'not', 'true', 'false', 'True', 'False', 'vero', 'falso'}
MAX_DEPTH = 8
MAX_LENGTH = 200
CONSTANTS = {'true': True, 'false': False, 'vero': True, 'falso': False, 'True': True, 'False': False}
BINARY = {ast.Add: lambda a, b: a+b, ast.Sub: lambda a, b: a-b, ast.Mult: lambda a, b: a*b,
          ast.Div: lambda a, b: a/b, ast.Mod: lambda a, b: a % b, ast.FloorDiv: lambda a, b: a//b}
COMPARE = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
           ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}


def check_name(name, what='Nome'):
    if not isinstance(name, str) or not NAME.match(name) or name in RESERVED:
        raise ValueError('%s non valido: lettere, cifre e _, senza spazi, iniziando con una lettera.' % what)
    return name


def parse(text):
    """Parsed expression tree; raises ValueError with a readable message."""
    if type(text) in (int, float) and math.isfinite(text): text = repr(text)
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LENGTH:
        raise ValueError('Espressione vuota o troppo lunga.')
    try: tree = ast.parse(text.strip(), mode='eval')
    except SyntaxError: raise ValueError('Espressione non valida: %s' % text.strip()) from None
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd,
                                 ast.BinOp, ast.Compare, ast.Constant, ast.Name, ast.Load, *BINARY, *COMPARE)):
            raise ValueError('Espressione non ammessa (%s): usa numeri, nomi, + - * / %%, confronti e and/or/not.' % text.strip())
        if isinstance(node, ast.Constant) and (type(node.value) not in (int, float, bool) or not math.isfinite(node.value)):
            raise ValueError('Valore non ammesso in %s.' % text.strip())
    return tree


def names(tree):
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id not in CONSTANTS}


def evaluate(tree, env):
    """Value of a parsed expression; `env` maps every name used to a number or bool."""
    def walk(node):
        if isinstance(node, ast.Expression): return walk(node.body)
        if isinstance(node, ast.Constant): return node.value
        if isinstance(node, ast.Name):
            if node.id in CONSTANTS: return CONSTANTS[node.id]
            if node.id not in env: raise ValueError('nome sconosciuto: %s' % node.id)
            value = env[node.id]
            if value is None: raise ValueError('%s senza valore' % node.id)
            return value
        if isinstance(node, ast.BoolOp):
            values = [walk(v) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp):
            value = walk(node.operand)
            return (not value) if isinstance(node.op, ast.Not) else (-value if isinstance(node.op, ast.USub) else +value)
        if isinstance(node, ast.BinOp):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, (ast.Div, ast.Mod, ast.FloorDiv)) and right == 0: raise ValueError('divisione per zero')
            value = BINARY[type(node.op)](left, right)
            if abs(value) > 1e9: raise ValueError('valore oltre 1e9')
            return value
        if isinstance(node, ast.Compare):
            left = walk(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right = walk(comparator)
                if not COMPARE[type(op)](left, right): return False
                left = right
            return True
        raise ValueError('espressione non ammessa')
    return walk(tree)


def structure(blocks):
    """Matching map of loop/if/else/end; raises on unbalanced or too deep structure."""
    stack = []; match = {}
    for i, block in enumerate(blocks):
        kind = block['kind']
        if kind in ('loop', 'if', 'function'):
            if kind == 'function' and stack: raise ValueError('Blocco %d: definisci le funzioni soltanto al livello principale.' % (i+1))
            stack.append(i)
            if len(stack) > MAX_DEPTH: raise ValueError('Strutture annidate oltre %d livelli.' % MAX_DEPTH)
        elif kind == 'return':
            if not any(blocks[k]['kind'] == 'function' for k in stack): raise ValueError('Blocco %d: «Restituisci» fuori da una funzione.' % (i+1))
        elif kind == 'else':
            if not stack or blocks[stack[-1]]['kind'] != 'if' or 'else' in match.get(stack[-1], {}):
                raise ValueError('Blocco %d: «Altrimenti» senza un «Se» aperto.' % (i+1))
            match.setdefault(stack[-1], {})['else'] = i; match[i] = dict(owner=stack[-1])
        elif kind == 'end':
            if not stack: raise ValueError('Blocco %d: «Fine» senza «Ripeti», «Se» o «Funzione» aperto.' % (i+1))
            owner = stack.pop(); match.setdefault(owner, {})['end'] = i; match[i] = dict(owner=owner)
            if 'else' in match[owner]: match[match[owner]['else']]['end'] = i
    if stack: raise ValueError('Blocco %d: «%s» senza «Fine».' % (stack[-1]+1, {'loop':'Ripeti', 'if':'Se', 'function':'Funzione'}[blocks[stack[-1]]['kind']]))
    return match


def depths(blocks):
    """Indentation level of every block, for display."""
    level = 0; result = []
    for block in blocks:
        if block['kind'] in ('end', 'else'): level = max(0, level-1)
        result.append(level)
        if block['kind'] in ('loop', 'if', 'else', 'function'): level += 1
    return result
