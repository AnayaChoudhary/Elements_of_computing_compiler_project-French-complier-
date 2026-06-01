"""
code_generator.py  —  FrançaisScript → VM Code
================================================
Stage 4 of the compilation pipeline.

Walks the AST (ProgramNode) produced by the Parser and emits
stack-based VM instructions (identical in format to the Nand2Tetris VM).

VM Instruction Reference:
  push <segment> <index>     — push value onto stack
  pop  <segment> <index>     — pop value from stack into segment
  add / sub / neg            — arithmetic
  and / or / not             — logical / bitwise
  lt / gt / eq               — comparison (result: -1=true, 0=false)
  label <lbl>                — jump target
  goto <lbl>                 — unconditional jump
  if-goto <lbl>              — conditional jump (pops top of stack)
  function <name> <nLocals>  — subroutine header
  call <name> <nArgs>        — subroutine call
  return                     — return from subroutine

Segments:
  constant, local, argument, this, that, static, temp, pointer
"""

from syntax_tree import (
    ProgramNode, SubroutineNode,
    LetNode, IfNode, WhileNode, DoNode, ReturnNode,
    BinaryOpNode, UnaryOpNode,
    IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
    VarNode, ArrayAccessNode, CallNode,
)

# Maps symbol-table 'kind' → VM segment name
_KIND_TO_SEG = {
    'statique': 'static',
    'field':    'this',
    'arg':      'argument',
    'var':      'local',
}

_BINARY_OP_VM = {
    '+': 'add',
    '-': 'sub',
    '&': 'and',
    '|': 'or',
    '<': 'lt',
    '>': 'gt',
    '=': 'eq',
    '*': 'call Math.multiply 2',
    '/': 'call Math.divide 2',
}


# ──────────────────────────────────────────────────────────────────────────────
#  Symbol Table
# ──────────────────────────────────────────────────────────────────────────────

class SymbolTable:
    """
    Two-scope symbol table:
      • class scope  → 'statique' and 'field' variables
      • subroutine scope → 'arg' and 'var' (local) variables

    Each entry: name → (type, kind, index)
    """

    def __init__(self):
        self._class_scope: dict = {}
        self._sub_scope:   dict = {}
        self._counts = {'statique': 0, 'field': 0, 'arg': 0, 'var': 0}

    def start_subroutine(self):
        """Reset subroutine-level scope (call at start of each subroutine)."""
        self._sub_scope = {}
        self._counts['arg'] = 0
        self._counts['var'] = 0

    def define(self, name: str, var_type: str, kind: str):
        """Register a new variable."""
        idx = self._counts[kind]
        self._counts[kind] += 1
        if kind in ('statique', 'field'):
            self._class_scope[name] = (var_type, kind, idx)
        else:
            self._sub_scope[name] = (var_type, kind, idx)

    def lookup(self, name: str):
        """Return (type, kind, index) or None if not found."""
        if name in self._sub_scope:
            return self._sub_scope[name]
        if name in self._class_scope:
            return self._class_scope[name]
        return None

    def count(self, kind: str) -> int:
        return self._counts[kind]


# ──────────────────────────────────────────────────────────────────────────────
#  Code Generator
# ──────────────────────────────────────────────────────────────────────────────

class CodeGenerator:
    """
    Generates VM code from a FrançaisScript AST.

    Usage:
        gen = CodeGenerator()
        vm_code = gen.generate(ast)   # ast is a ProgramNode
    """

    def __init__(self):
        self._out:        list  = []
        self._symbols:    SymbolTable = SymbolTable()
        self._label_cnt:  int   = 0
        self._class_name: str   = ''

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _emit(self, *lines: str):
        self._out.extend(lines)

    def _new_label(self) -> str:
        lbl = f'FS_L{self._label_cnt}'
        self._label_cnt += 1
        return lbl

    def _push_var(self, name: str):
        sym = self._symbols.lookup(name)
        if sym is None:
            raise NameError(f"Undefined variable: '{name}'")
        _, kind, idx = sym
        self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')

    def _pop_var(self, name: str):
        sym = self._symbols.lookup(name)
        if sym is None:
            raise NameError(f"Undefined variable: '{name}'")
        _, kind, idx = sym
        self._emit(f'pop {_KIND_TO_SEG[kind]} {idx}')

    # ------------------------------------------------------------------ #
    #  Public interface
    # ------------------------------------------------------------------ #

    def generate(self, program: ProgramNode) -> str:
        """Walk the AST and return VM source code as a string."""
        self._class_name = program.name

        # Register class-level static variables
        for (kind, vtype, vname) in program.static_vars:
            self._symbols.define(vname, vtype, kind)

        for sub in program.subroutines:
            self._gen_subroutine(sub)

        return '\n'.join(self._out)

    # ------------------------------------------------------------------ #
    #  Subroutine
    # ------------------------------------------------------------------ #

    def _gen_subroutine(self, sub: SubroutineNode):
        self._symbols.start_subroutine()

        # Methods receive 'ceci' (this) as implicit first argument
        if sub.kind == 'methode':
            self._symbols.define('ceci', self._class_name, 'arg')

        for (ptype, pname) in sub.params:
            self._symbols.define(pname, ptype, 'arg')

        for (_, vtype, vname) in sub.local_vars:
            self._symbols.define(vname, vtype, 'var')

        n_locals = self._symbols.count('var')
        self._emit(
            f'// ---- {sub.kind} {self._class_name}.{sub.name} ----',
            f'function {self._class_name}.{sub.name} {n_locals}',
        )

        if sub.kind == 'constructeur':
            # Allocate heap memory for the new object
            n_fields = self._symbols.count('field')
            self._emit(
                f'push constant {n_fields}',
                'call Memory.alloc 1',
                'pop pointer 0',        # anchor THIS to allocated block
            )
        elif sub.kind == 'methode':
            # Set THIS to the object passed as argument 0
            self._emit('push argument 0', 'pop pointer 0')

        for stmt in sub.body:
            self._gen_statement(stmt)

    # ------------------------------------------------------------------ #
    #  Statements
    # ------------------------------------------------------------------ #

    def _gen_statement(self, stmt):
        if   isinstance(stmt, LetNode):    self._gen_let(stmt)
        elif isinstance(stmt, IfNode):     self._gen_if(stmt)
        elif isinstance(stmt, WhileNode):  self._gen_while(stmt)
        elif isinstance(stmt, DoNode):     self._gen_do(stmt)
        elif isinstance(stmt, ReturnNode): self._gen_return(stmt)
        else:
            raise TypeError(f"Unknown statement node: {type(stmt)}")

    def _gen_let(self, stmt: LetNode):
        if stmt.index is not None:
            # Array write:  name[index] = expr
            sym = self._symbols.lookup(stmt.name)
            if sym is None:
                raise NameError(f"Undefined array: '{stmt.name}'")
            _, kind, idx = sym
            self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')  # base address
            self._gen_expr(stmt.index)
            self._emit('add')                                 # target address
            self._gen_expr(stmt.expr)
            self._emit(
                'pop temp 0',      # stash value
                'pop pointer 1',   # THAT = target address
                'push temp 0',
                'pop that 0',      # *THAT = value
            )
        else:
            self._gen_expr(stmt.expr)
            self._pop_var(stmt.name)

    def _gen_if(self, stmt: IfNode):
        else_lbl = self._new_label()
        end_lbl  = self._new_label()

        self._gen_expr(stmt.condition)
        self._emit('not', f'if-goto {else_lbl}')

        for s in stmt.then_stmts:
            self._gen_statement(s)
        self._emit(f'goto {end_lbl}', f'label {else_lbl}')

        if stmt.else_stmts:
            for s in stmt.else_stmts:
                self._gen_statement(s)
        self._emit(f'label {end_lbl}')

    def _gen_while(self, stmt: WhileNode):
        top_lbl = self._new_label()
        end_lbl = self._new_label()

        self._emit(f'label {top_lbl}')
        self._gen_expr(stmt.condition)
        self._emit('not', f'if-goto {end_lbl}')

        for s in stmt.body:
            self._gen_statement(s)
        self._emit(f'goto {top_lbl}', f'label {end_lbl}')

    def _gen_do(self, stmt: DoNode):
        self._gen_expr(stmt.call)
        self._emit('pop temp 0')   # discard return value

    def _gen_return(self, stmt: ReturnNode):
        if stmt.expr is not None:
            self._gen_expr(stmt.expr)
        else:
            self._emit('push constant 0')   # void functions must push a dummy
        self._emit('return')

    # ------------------------------------------------------------------ #
    #  Expressions
    # ------------------------------------------------------------------ #

    def _gen_expr(self, node):
        if isinstance(node, IntegerNode):
            self._emit(f'push constant {node.value}')

        elif isinstance(node, BoolNode):
            self._emit('push constant 0')
            if node.value:
                self._emit('not')   # -1 in 2's complement = true

        elif isinstance(node, NullNode):
            self._emit('push constant 0')

        elif isinstance(node, ThisNode):
            self._emit('push pointer 0')

        elif isinstance(node, StringNode):
            # Build string on the heap char-by-char
            self._emit(f'push constant {len(node.value)}', 'call String.new 1')
            for ch in node.value:
                self._emit(f'push constant {ord(ch)}', 'call String.appendChar 2')

        elif isinstance(node, VarNode):
            self._push_var(node.name)

        elif isinstance(node, ArrayAccessNode):
            sym = self._symbols.lookup(node.name)
            if sym is None:
                raise NameError(f"Undefined array: '{node.name}'")
            _, kind, idx = sym
            self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')
            self._gen_expr(node.index)
            self._emit('add', 'pop pointer 1', 'push that 0')

        elif isinstance(node, BinaryOpNode):
            self._gen_expr(node.left)
            self._gen_expr(node.right)
            self._emit(_BINARY_OP_VM[node.op])

        elif isinstance(node, UnaryOpNode):
            self._gen_expr(node.operand)
            self._emit('neg' if node.op == '-' else 'not')

        elif isinstance(node, CallNode):
            self._gen_call(node)

        else:
            raise TypeError(f"Unknown expression node: {type(node)}")

    def _gen_call(self, node: CallNode):
        n_args = len(node.args)

        if node.obj is None:
            # Same-class method call  →  push this first
            self._emit('push pointer 0')
            for arg in node.args:
                self._gen_expr(arg)
            self._emit(f'call {self._class_name}.{node.method} {n_args + 1}')

        else:
            sym = self._symbols.lookup(node.obj)
            if sym is not None:
                # node.obj is a variable → method call on an object
                var_type, kind, idx = sym
                self._emit(f'push {_KIND_TO_SEG[kind]} {idx}')
                for arg in node.args:
                    self._gen_expr(arg)
                self._emit(f'call {var_type}.{node.method} {n_args + 1}')
            else:
                # node.obj is a class name → static function call
                for arg in node.args:
                    self._gen_expr(arg)
                self._emit(f'call {node.obj}.{node.method} {n_args}')