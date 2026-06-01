"""
syntax_tree.py  —  FrançaisScript AST Node Definitions
========================================================
Stage 2 of the compilation pipeline.

Defines all Abstract Syntax Tree (AST) node classes produced by the Parser
and consumed by the Code Generator.

Tree hierarchy:
  ProgramNode
  └── SubroutineNode (fonction / methode / constructeur)
       ├── params:     [(type_str, name_str), ...]
       ├── local_vars: [('var', type_str, name_str), ...]
       └── body:       [Statement, ...]

Statements:
  LetNode, IfNode, WhileNode, DoNode, ReturnNode

Expressions:
  IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
  VarNode, ArrayAccessNode, CallNode,
  BinaryOpNode, UnaryOpNode
"""


# ──────────────────────────────────────────────────────────────────────────────
#  Base
# ──────────────────────────────────────────────────────────────────────────────

class Node:
    """Base AST node."""
    def __repr__(self):
        attrs = ', '.join(f'{k}={v!r}' for k, v in self.__dict__.items())
        return f'{self.__class__.__name__}({attrs})'


# ──────────────────────────────────────────────────────────────────────────────
#  Top-level
# ──────────────────────────────────────────────────────────────────────────────

class ProgramNode(Node):
    """
    Represents a full FrançaisScript programme (class).

    Attributes:
        name        (str)               Programme name
        static_vars (list of tuples)    ('statique', type, name)
        subroutines (list of SubroutineNode)
    """
    def __init__(self, name: str, static_vars: list, subroutines: list):
        self.name        = name
        self.static_vars = static_vars   # [('statique', type, name), ...]
        self.subroutines = subroutines   # [SubroutineNode, ...]


class SubroutineNode(Node):
    """
    Represents a fonction / methode / constructeur.

    Attributes:
        kind        (str)   'fonction' | 'methode' | 'constructeur'
        return_type (str)   Return type ('entier', 'vide', class name, …)
        name        (str)   Subroutine name
        params      (list)  [(type, name), …]
        local_vars  (list)  [('var', type, name), …]
        body        (list)  [Statement, …]
    """
    def __init__(self, kind: str, return_type: str, name: str,
                 params: list, local_vars: list, body: list):
        self.kind        = kind
        self.return_type = return_type
        self.name        = name
        self.params      = params
        self.local_vars  = local_vars
        self.body        = body


# ──────────────────────────────────────────────────────────────────────────────
#  Statements
# ──────────────────────────────────────────────────────────────────────────────

class LetNode(Node):
    """
    laisser <name>[<index>] = <expr>;

    Attributes:
        name  (str)          Variable name
        index (Node|None)    Array index expression, or None
        expr  (Node)         Right-hand side expression
    """
    def __init__(self, name: str, index, expr):
        self.name  = name
        self.index = index
        self.expr  = expr


class IfNode(Node):
    """
    si (<condition>) { <then_stmts> } [sinon { <else_stmts> }]

    Attributes:
        condition  (Node)       Boolean expression
        then_stmts (list)       Statements in the 'si' branch
        else_stmts (list|None)  Statements in the 'sinon' branch
    """
    def __init__(self, condition, then_stmts: list, else_stmts):
        self.condition  = condition
        self.then_stmts = then_stmts
        self.else_stmts = else_stmts


class WhileNode(Node):
    """
    tantque (<condition>) { <body> }

    Attributes:
        condition (Node)  Boolean expression
        body      (list)  Statements in loop body
    """
    def __init__(self, condition, body: list):
        self.condition = condition
        self.body      = body


class DoNode(Node):
    """
    faire <call>;

    Attributes:
        call (CallNode)  Subroutine call (return value discarded)
    """
    def __init__(self, call):
        self.call = call


class ReturnNode(Node):
    """
    retourner [<expr>];

    Attributes:
        expr (Node|None)  Value to return; None for void functions
    """
    def __init__(self, expr):
        self.expr = expr


# ──────────────────────────────────────────────────────────────────────────────
#  Expressions
# ──────────────────────────────────────────────────────────────────────────────

class BinaryOpNode(Node):
    """
    <left> <op> <right>

    op ∈ { '+', '-', '*', '/', '&', '|', '<', '>', '=' }
    """
    def __init__(self, op: str, left, right):
        self.op    = op
        self.left  = left
        self.right = right


class UnaryOpNode(Node):
    """
    <op><operand>

    op ∈ { '-'  (negate), '~' (bitwise NOT) }
    """
    def __init__(self, op: str, operand):
        self.op      = op
        self.operand = operand


class IntegerNode(Node):
    """Integer constant (0–32767)."""
    def __init__(self, value: int):
        self.value = value


class StringNode(Node):
    """String literal (without surrounding quotes)."""
    def __init__(self, value: str):
        self.value = value


class BoolNode(Node):
    """Boolean literal: vrai (True) or faux (False)."""
    def __init__(self, value: bool):
        self.value = value


class NullNode(Node):
    """The null pointer constant."""
    pass


class ThisNode(Node):
    """Reference to the current object (ceci)."""
    pass


class VarNode(Node):
    """Reference to a variable by name."""
    def __init__(self, name: str):
        self.name = name


class ArrayAccessNode(Node):
    """
    <name>[<index>]  — reads one element of an array.
    """
    def __init__(self, name: str, index):
        self.name  = name
        self.index = index


class CallNode(Node):
    """
    Subroutine / method call.

    Attributes:
        obj    (str|None)  Object or class name before the dot; None for same-class calls
        method (str)       Subroutine name
        args   (list)      Argument expressions
    """
    def __init__(self, obj, method: str, args: list):
        self.obj    = obj
        self.method = method
        self.args   = args