"""
tokenizer.py  —  FrançaisScript Lexer
======================================
Stage 1 of the compilation pipeline.

Converts raw FrançaisScript source text into a flat list of Tokens.

French keyword mapping:
  programme   → class
  fonction    → function
  methode     → method
  constructeur→ constructor
  si          → if
  sinon       → else
  tantque     → while
  retourner   → return
  entier      → int
  booleen     → boolean
  caractere   → char
  vide        → void
  laisser     → let
  faire       → do
  vrai        → true
  faux        → false
  nul         → null
  ceci        → this
  statique    → static
"""

from enum import Enum, auto


class TokenType(Enum):
    KEYWORD    = auto()
    SYMBOL     = auto()
    INTEGER    = auto()
    STRING     = auto()
    IDENTIFIER = auto()
    EOF        = auto()


# All reserved French keywords
KEYWORDS = {
    'programme', 'fonction', 'methode', 'constructeur',
    'si', 'sinon', 'tantque', 'retourner',
    'entier', 'booleen', 'caractere', 'vide',
    'var', 'laisser', 'faire',
    'vrai', 'faux', 'nul', 'ceci', 'statique',
}

# Single-character symbols
SYMBOLS = set('{}()[].,;+-*/&|<>=~')


class Token:
    """A single lexical unit."""
    def __init__(self, type_: TokenType, value, line: int = 0):
        self.type  = type_
        self.value = value
        self.line  = line

    def __repr__(self):
        return f'Token({self.type.name}, {self.value!r}, line={self.line})'


class TokenizerError(Exception):
    pass


class Tokenizer:
    """
    Converts FrançaisScript source into a stream of Token objects.

    Usage:
        t = Tokenizer(source_code)
        while not t.is_eof():
            print(t.advance())
    """

    def __init__(self, source: str):
        self._tokens: list[Token] = []
        self._pos = 0
        self._scan(source)

    # ------------------------------------------------------------------ #
    #  Private scanning
    # ------------------------------------------------------------------ #

    def _scan(self, src: str):
        i, line = 0, 1
        n = len(src)

        while i < n:
            c = src[i]

            # Whitespace
            if c in ' \t\r':
                i += 1
                continue
            if c == '\n':
                line += 1
                i += 1
                continue

            # Single-line comment  //
            if src[i:i+2] == '//':
                while i < n and src[i] != '\n':
                    i += 1
                continue

            # Multi-line comment  /* ... */
            if src[i:i+2] == '/*':
                i += 2
                while i < n - 1 and src[i:i+2] != '*/':
                    if src[i] == '\n':
                        line += 1
                    i += 1
                i += 2
                continue

            # String literal  "..."
            if c == '"':
                j = i + 1
                while j < n and src[j] != '"':
                    if src[j] == '\n':
                        raise TokenizerError(f"Unterminated string at line {line}")
                    j += 1
                self._tokens.append(Token(TokenType.STRING, src[i+1:j], line))
                i = j + 1
                continue

            # Symbol
            if c in SYMBOLS:
                self._tokens.append(Token(TokenType.SYMBOL, c, line))
                i += 1
                continue

            # Integer literal
            if c.isdigit():
                j = i
                while j < n and src[j].isdigit():
                    j += 1
                val = int(src[i:j])
                if val > 32767:
                    raise TokenizerError(f"Integer {val} too large (max 32767) at line {line}")
                self._tokens.append(Token(TokenType.INTEGER, val, line))
                i = j
                continue

            # Keyword or identifier
            if c.isalpha() or c == '_':
                j = i
                while j < n and (src[j].isalnum() or src[j] == '_'):
                    j += 1
                word = src[i:j]
                tok_type = TokenType.KEYWORD if word in KEYWORDS else TokenType.IDENTIFIER
                self._tokens.append(Token(tok_type, word, line))
                i = j
                continue

            raise TokenizerError(f"Unexpected character {c!r} at line {line}")

        self._tokens.append(Token(TokenType.EOF, None, line))

    # ------------------------------------------------------------------ #
    #  Public stream interface
    # ------------------------------------------------------------------ #

    def peek(self) -> Token:
        """Return current token without consuming it."""
        return self._tokens[self._pos]

    def advance(self) -> Token:
        """Consume and return current token."""
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def expect(self, type_: TokenType = None, value=None) -> Token:
        """Consume token, raising if it doesn't match expected type/value."""
        tok = self.advance()
        if type_ is not None and tok.type != type_:
            raise SyntaxError(
                f"Expected token type {type_.name} but got {tok.type.name} "
                f"({tok.value!r}) at line {tok.line}"
            )
        if value is not None and tok.value != value:
            raise SyntaxError(
                f"Expected {value!r} but got {tok.value!r} at line {tok.line}"
            )
        return tok

    def match(self, type_: TokenType = None, value=None) -> bool:
        """Return True if current token matches (without consuming)."""
        tok = self.peek()
        if type_ is not None and tok.type != type_:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def is_eof(self) -> bool:
        return self.peek().type == TokenType.EOF

    def all_tokens(self) -> list[Token]:
        """Return all tokens (for debugging)."""
        return list(self._tokens)