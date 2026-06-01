"""
parser.py  —  FrançaisScript Recursive-Descent Parser
=======================================================
Stage 3 of the compilation pipeline.

Consumes a Tokenizer stream and produces a ProgramNode (AST).

Grammar (simplified):
  programme     := 'programme' ID '{' varDec* subroutine* '}'
  subroutine    := ('fonction'|'methode'|'constructeur') type ID '(' paramList ')' subroutineBody
  paramList     := ((type ID) (',' type ID)*)?
  subroutineBody:= '{' varDec* statement* '}'
  varDec        := 'var' type ID (',' ID)* ';'
  statement     := letStmt | ifStmt | whileStmt | doStmt | returnStmt
  letStmt       := 'laisser' ID ('[' expr ']')? '=' expr ';'
  ifStmt        := 'si' '(' expr ')' '{' statement* '}' ('sinon' '{' statement* '}')?
  whileStmt     := 'tantque' '(' expr ')' '{' statement* '}'
  doStmt        := 'faire' subroutineCall ';'
  returnStmt    := 'retourner' expr? ';'
  expr          := term (op term)*
  term          := INTEGER | STRING | 'vrai' | 'faux' | 'nul' | 'ceci'
                 | ID '[' expr ']' | subroutineCall | ID
                 | '(' expr ')' | unaryOp term
  op            := '+' | '-' | '*' | '/' | '&' | '|' | '<' | '>' | '='
  unaryOp       := '-' | '~'
"""

from tokenizer import Tokenizer, TokenType
from syntax_tree import (
    ProgramNode, SubroutineNode,
    LetNode, IfNode, WhileNode, DoNode, ReturnNode,
    BinaryOpNode, UnaryOpNode,
    IntegerNode, StringNode, BoolNode, NullNode, ThisNode,
    VarNode, ArrayAccessNode, CallNode,
)


class ParseError(Exception):
    pass


_BINARY_OPS  = set('+-*/&|<>=')
_UNARY_OPS   = {'-', '~'}
_SUB_KINDS   = {'fonction', 'methode', 'constructeur'}


class Parser:
    """
    Transforms a Tokenizer into a ProgramNode (full AST).

    Usage:
        tokenizer = Tokenizer(source)
        ast = Parser(tokenizer).parse()
    """

    def __init__(self, tokenizer: Tokenizer):
        self._t = tokenizer

    # ------------------------------------------------------------------ #
    #  Entry point
    # ------------------------------------------------------------------ #

    def parse(self) -> ProgramNode:
        node = self._parse_programme()
        self._t.expect(TokenType.EOF)
        return node

    # ------------------------------------------------------------------ #
    #  Programme (class)
    # ------------------------------------------------------------------ #

    def _parse_programme(self) -> ProgramNode:
        self._t.expect(TokenType.KEYWORD, 'programme')
        name = self._t.expect(TokenType.IDENTIFIER).value
        self._t.expect(TokenType.SYMBOL, '{')

        static_vars  = []
        subroutines  = []

        while not self._t.match(TokenType.SYMBOL, '}'):
            tok = self._t.peek()
            if tok.value == 'statique':
                static_vars.extend(self._parse_static_dec())
            elif tok.value in _SUB_KINDS:
                subroutines.append(self._parse_subroutine())
            else:
                raise ParseError(
                    f"Unexpected token '{tok.value}' inside programme at line {tok.line}. "
                    f"Expected 'statique', 'fonction', 'methode', or 'constructeur'."
                )

        self._t.expect(TokenType.SYMBOL, '}')
        return ProgramNode(name, static_vars, subroutines)

    # ------------------------------------------------------------------ #
    #  Variable declarations
    # ------------------------------------------------------------------ #

    def _parse_static_dec(self) -> list:
        """Parse  statique <type> <id>, <id>, ... ;"""
        self._t.expect(TokenType.KEYWORD, 'statique')
        var_type = self._t.advance().value          # type token
        names    = [self._t.expect(TokenType.IDENTIFIER).value]
        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            names.append(self._t.expect(TokenType.IDENTIFIER).value)
        self._t.expect(TokenType.SYMBOL, ';')
        return [('statique', var_type, n) for n in names]

    def _parse_local_dec(self) -> list:
        """Parse  var <type> <id>, <id>, ... ;"""
        self._t.expect(TokenType.KEYWORD, 'var')
        var_type = self._t.advance().value
        names    = [self._t.expect(TokenType.IDENTIFIER).value]
        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            names.append(self._t.expect(TokenType.IDENTIFIER).value)
        self._t.expect(TokenType.SYMBOL, ';')
        return [('var', var_type, n) for n in names]

    # ------------------------------------------------------------------ #
    #  Subroutine
    # ------------------------------------------------------------------ #

    def _parse_subroutine(self) -> SubroutineNode:
        kind        = self._t.advance().value           # fonction/methode/constructeur
        return_type = self._t.advance().value           # vide / entier / ClassName …
        name        = self._t.expect(TokenType.IDENTIFIER).value

        self._t.expect(TokenType.SYMBOL, '(')
        params = self._parse_param_list()
        self._t.expect(TokenType.SYMBOL, ')')

        self._t.expect(TokenType.SYMBOL, '{')
        local_vars = []
        while self._t.match(TokenType.KEYWORD, 'var'):
            local_vars.extend(self._parse_local_dec())

        body = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')

        return SubroutineNode(kind, return_type, name, params, local_vars, body)

    def _parse_param_list(self) -> list:
        """Parse zero or more  type ID  separated by commas."""
        params = []
        if self._t.match(TokenType.SYMBOL, ')'):
            return params
        ptype = self._t.advance().value
        pname = self._t.expect(TokenType.IDENTIFIER).value
        params.append((ptype, pname))
        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            ptype = self._t.advance().value
            pname = self._t.expect(TokenType.IDENTIFIER).value
            params.append((ptype, pname))
        return params

    # ------------------------------------------------------------------ #
    #  Statements
    # ------------------------------------------------------------------ #

    def _parse_statements(self) -> list:
        stmts = []
        stmt_starters = {'laisser', 'si', 'tantque', 'faire', 'retourner'}
        while self._t.peek().value in stmt_starters:
            stmts.append(self._parse_statement())
        return stmts

    def _parse_statement(self):
        kw = self._t.peek().value
        if kw == 'laisser':
            return self._parse_let()
        if kw == 'si':
            return self._parse_if()
        if kw == 'tantque':
            return self._parse_while()
        if kw == 'faire':
            return self._parse_do()
        if kw == 'retourner':
            return self._parse_return()
        tok = self._t.peek()
        raise ParseError(f"Unknown statement keyword '{kw}' at line {tok.line}")

    def _parse_let(self) -> LetNode:
        self._t.expect(TokenType.KEYWORD, 'laisser')
        name  = self._t.expect(TokenType.IDENTIFIER).value
        index = None
        if self._t.match(TokenType.SYMBOL, '['):
            self._t.advance()
            index = self._parse_expression()
            self._t.expect(TokenType.SYMBOL, ']')
        self._t.expect(TokenType.SYMBOL, '=')
        expr = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ';')
        return LetNode(name, index, expr)

    def _parse_if(self) -> IfNode:
        self._t.expect(TokenType.KEYWORD, 'si')
        self._t.expect(TokenType.SYMBOL, '(')
        cond = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ')')
        self._t.expect(TokenType.SYMBOL, '{')
        then_stmts = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')

        else_stmts = None
        if self._t.match(TokenType.KEYWORD, 'sinon'):
            self._t.advance()
            self._t.expect(TokenType.SYMBOL, '{')
            else_stmts = self._parse_statements()
            self._t.expect(TokenType.SYMBOL, '}')

        return IfNode(cond, then_stmts, else_stmts)

    def _parse_while(self) -> WhileNode:
        self._t.expect(TokenType.KEYWORD, 'tantque')
        self._t.expect(TokenType.SYMBOL, '(')
        cond = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ')')
        self._t.expect(TokenType.SYMBOL, '{')
        body = self._parse_statements()
        self._t.expect(TokenType.SYMBOL, '}')
        return WhileNode(cond, body)

    def _parse_do(self) -> DoNode:
        self._t.expect(TokenType.KEYWORD, 'faire')
        call = self._parse_call()
        self._t.expect(TokenType.SYMBOL, ';')
        return DoNode(call)

    def _parse_return(self) -> ReturnNode:
        self._t.expect(TokenType.KEYWORD, 'retourner')
        expr = None
        if not self._t.match(TokenType.SYMBOL, ';'):
            expr = self._parse_expression()
        self._t.expect(TokenType.SYMBOL, ';')
        return ReturnNode(expr)

    # ------------------------------------------------------------------ #
    #  Expressions
    # ------------------------------------------------------------------ #

    def _parse_expression(self):
        left = self._parse_term()
        while (self._t.match(TokenType.SYMBOL)
               and self._t.peek().value in _BINARY_OPS):
            op    = self._t.advance().value
            right = self._parse_term()
            left  = BinaryOpNode(op, left, right)
        return left

    def _parse_term(self):
        tok = self._t.peek()

        # Integer constant
        if tok.type == TokenType.INTEGER:
            self._t.advance()
            return IntegerNode(tok.value)

        # String constant
        if tok.type == TokenType.STRING:
            self._t.advance()
            return StringNode(tok.value)

        # Boolean / null / this
        if tok.value == 'vrai':
            self._t.advance(); return BoolNode(True)
        if tok.value == 'faux':
            self._t.advance(); return BoolNode(False)
        if tok.value == 'nul':
            self._t.advance(); return NullNode()
        if tok.value == 'ceci':
            self._t.advance(); return ThisNode()

        # Parenthesised sub-expression
        if tok.type == TokenType.SYMBOL and tok.value == '(':
            self._t.advance()
            expr = self._parse_expression()
            self._t.expect(TokenType.SYMBOL, ')')
            return expr

        # Unary operator
        if tok.type == TokenType.SYMBOL and tok.value in _UNARY_OPS:
            self._t.advance()
            operand = self._parse_term()
            return UnaryOpNode(tok.value, operand)

        # Identifier → variable | array access | call
        if tok.type == TokenType.IDENTIFIER:
            name = self._t.advance().value

            # Array access:   name[expr]
            if self._t.match(TokenType.SYMBOL, '['):
                self._t.advance()
                index = self._parse_expression()
                self._t.expect(TokenType.SYMBOL, ']')
                return ArrayAccessNode(name, index)

            # Call with dot:  name.method(args)
            if self._t.match(TokenType.SYMBOL, '.'):
                self._t.advance()
                method = self._t.expect(TokenType.IDENTIFIER).value
                self._t.expect(TokenType.SYMBOL, '(')
                args = self._parse_arg_list()
                self._t.expect(TokenType.SYMBOL, ')')
                return CallNode(name, method, args)

            # Call without dot:  name(args)
            if self._t.match(TokenType.SYMBOL, '('):
                self._t.advance()
                args = self._parse_arg_list()
                self._t.expect(TokenType.SYMBOL, ')')
                return CallNode(None, name, args)

            # Plain variable reference
            return VarNode(name)

        raise ParseError(
            f"Unexpected token in expression: {tok!r} at line {tok.line}"
        )

    def _parse_call(self) -> CallNode:
        """Parse a standalone subroutine call (used by DoNode)."""
        name = self._t.expect(TokenType.IDENTIFIER).value
        obj, method = None, name

        if self._t.match(TokenType.SYMBOL, '.'):
            self._t.advance()
            obj    = name
            method = self._t.expect(TokenType.IDENTIFIER).value

        self._t.expect(TokenType.SYMBOL, '(')
        args = self._parse_arg_list()
        self._t.expect(TokenType.SYMBOL, ')')
        return CallNode(obj, method, args)

    def _parse_arg_list(self) -> list:
        args = []
        if self._t.match(TokenType.SYMBOL, ')'):
            return args
        args.append(self._parse_expression())
        while self._t.match(TokenType.SYMBOL, ','):
            self._t.advance()
            args.append(self._parse_expression())
        return args