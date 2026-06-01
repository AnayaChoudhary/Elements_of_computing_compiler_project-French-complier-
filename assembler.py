"""
assembler.py  —  Hack Assembly → Machine Code (Binary)
========================================================
Stage 6 of the compilation pipeline.

Translates Hack Assembly (.asm) into 16-bit binary machine code (.hack).

Two-pass algorithm:
  Pass 1 — scan for label declarations (xxx) and record ROM addresses.
  Pass 2 — translate each instruction into 16-bit binary.

Instruction formats:
  A-instruction:  @value  →  0vvvvvvvvvvvvvvv  (15-bit address/value)
  C-instruction:  dest=comp;jump  →  111accccccdddjjj

Predefined symbols:
  SP=0, LCL=1, ARG=2, THIS=3, THAT=4, R0-R15, SCREEN=16384, KBD=24576

Variables (unknown symbols in A-instructions) are allocated from RAM[16].
"""


class AssemblerError(Exception):
    pass


class Assembler:
    """
    Translates Hack Assembly source into 16-bit binary machine code.

    Usage:
        asm = Assembler()
        binary = asm.assemble(asm_source_string)
        # binary is a string of '0'/'1' lines, one per instruction
    """

    # Predefined symbols
    _PREDEFINED: dict = {
        'SP': 0, 'LCL': 1, 'ARG': 2, 'THIS': 3, 'THAT': 4,
        **{f'R{i}': i for i in range(16)},
        'SCREEN': 16384, 'KBD': 24576,
    }

    # dest bits  (key → 3-bit string)
    _DEST: dict = {
        '':    '000', 'M':   '001', 'D':   '010', 'MD':  '011',
        'A':   '100', 'AM':  '101', 'AD':  '110', 'AMD': '111',
    }

    # jump bits  (key → 3-bit string)
    _JUMP: dict = {
        '':    '000', 'JGT': '001', 'JEQ': '010', 'JGE': '011',
        'JLT': '100', 'JNE': '101', 'JLE': '110', 'JMP': '111',
    }

    # comp bits  (key → 7-bit string: a + c1-c6)
    _COMP: dict = {
        '0':   '0101010', '1':   '0111111', '-1':  '0111010',
        'D':   '0001100', 'A':   '0110000', '!D':  '0001101',
        '!A':  '0110001', '-D':  '0001111', '-A':  '0110011',
        'D+1': '0011111', 'A+1': '0110111', 'D-1': '0001110',
        'A-1': '0110010', 'D+A': '0000010', 'D-A': '0010011',
        'A-D': '0000111', 'D&A': '0000000', 'D|A': '0010101',
        'M':   '1110000', '!M':  '1110001', '-M':  '1110011',
        'M+1': '1110111', 'M-1': '1110010', 'D+M': '1000010',
        'D-M': '1010011', 'M-D': '1000111', 'D&M': '1000000',
        'D|M': '1010101',
    }

    # ------------------------------------------------------------------ #
    #  Public interface
    # ------------------------------------------------------------------ #

    def assemble(self, asm_source: str) -> str:
        """
        Assemble Hack Assembly source into binary.

        Returns a newline-separated string of 16-character binary lines.
        """
        clean_lines = self._clean(asm_source)
        symbols     = self._first_pass(clean_lines)
        binary      = self._second_pass(clean_lines, symbols)
        return '\n'.join(binary)

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _clean(self, source: str) -> list[str]:
        """Strip comments and blank lines."""
        result = []
        for line in source.splitlines():
            line = line.split('//')[0].strip()
            if line:
                result.append(line)
        return result

    def _first_pass(self, lines: list[str]) -> dict:
        """
        Scan for label declarations  (LABEL)  and record their ROM address.
        Returns the full symbol table (predefined + labels).
        """
        symbols  = dict(self._PREDEFINED)
        rom_addr = 0

        for line in lines:
            if line.startswith('(') and line.endswith(')'):
                label = line[1:-1]
                if label in symbols:
                    raise AssemblerError(f"Duplicate label: {label}")
                symbols[label] = rom_addr
            else:
                rom_addr += 1

        return symbols

    def _second_pass(self, lines: list[str], symbols: dict) -> list[str]:
        """
        Translate each instruction to 16-bit binary.
        Allocates new variable symbols starting at RAM[16].
        """
        binary   = []
        var_addr = 16

        for line in lines:
            # Skip label declarations — they don't produce instructions
            if line.startswith('('):
                continue

            if line.startswith('@'):
                # A-instruction
                sym = line[1:]
                if sym.isdigit():
                    addr = int(sym)
                elif sym in symbols:
                    addr = symbols[sym]
                else:
                    # New variable — allocate next RAM slot
                    symbols[sym] = var_addr
                    addr = var_addr
                    var_addr += 1

                if addr > 32767:
                    raise AssemblerError(f"Address {addr} exceeds 15-bit limit")
                binary.append(f'{addr:016b}')

            else:
                # C-instruction: [dest=]comp[;jump]
                dest, comp, jump = '', line, ''

                if '=' in line:
                    dest, comp = line.split('=', 1)
                if ';' in comp:
                    comp, jump = comp.split(';', 1)

                comp = comp.strip()
                dest = dest.strip()
                jump = jump.strip()

                if comp not in self._COMP:
                    raise AssemblerError(f"Unknown comp mnemonic: {comp!r}")
                if dest not in self._DEST:
                    raise AssemblerError(f"Unknown dest mnemonic: {dest!r}")
                if jump not in self._JUMP:
                    raise AssemblerError(f"Unknown jump mnemonic: {jump!r}")

                comp_bits = self._COMP[comp]
                dest_bits = self._DEST[dest]
                jump_bits = self._JUMP[jump]
                binary.append(f'111{comp_bits}{dest_bits}{jump_bits}')

        return binary

    # ------------------------------------------------------------------ #
    #  Utility: decode a single 16-bit word (for debugging)
    # ------------------------------------------------------------------ #

    @staticmethod
    def decode(word: str) -> str:
        """
        Human-readable decoding of a 16-bit binary instruction string.
        Useful for debugging the assembler output.
        """
        if len(word) != 16 or not all(c in '01' for c in word):
            return f'INVALID: {word!r}'
        val = int(word, 2)
        if word[0] == '0':
            return f'A-instruction: @{val}'
        # C-instruction: 111 a cccccc ddd jjj
        _DEST_REV = {v: k for k, v in Assembler._DEST.items()}
        _JUMP_REV = {v: k for k, v in Assembler._JUMP.items()}
        _COMP_REV = {v: k for k, v in Assembler._COMP.items()}
        comp_key  = word[3:10]
        dest_key  = word[10:13]
        jump_key  = word[13:16]
        comp = _COMP_REV.get(comp_key, '???')
        dest = _DEST_REV.get(dest_key, '???')
        jump = _JUMP_REV.get(jump_key, '???')
        expr = f'{dest}={comp}' if dest else comp
        if jump:
            expr += f';{jump}'
        return f'C-instruction: {expr}'