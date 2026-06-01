"""
vm_translator.py  —  VM Code → Hack Assembly
=============================================
Stage 5 of the compilation pipeline.

Translates stack-based VM instructions into Hack Assembly language.

VM Command → Assembly mapping:
  push constant N  →  @N / D=A / @SP / A=M / M=D / @SP / M=M+1
  pop local N      →  compute address, store via R13
  add              →  pop two, push sum
  sub              →  pop two, push difference
  neg              →  negate top of stack
  eq / lt / gt     →  comparison with conditional jump
  label L          →  (function$L)
  goto L           →  @function$L / 0;JMP
  if-goto L        →  pop, conditional jump
  function f n     →  (f) / initialise n locals to 0
  call f n         →  save frame, jump to f
  return           →  restore frame, jump to caller

Register conventions (Hack):
  R13  — scratch (target address for pop)
  R14  — FRAME temp during return
  R15  — return address temp during return
"""


_SEG_BASE = {
    'local':    'LCL',
    'argument': 'ARG',
    'this':     'THIS',
    'that':     'THAT',
}


class VMTranslator:
    """
    Translates a string of VM instructions into Hack Assembly source.

    Usage:
        translator = VMTranslator()
        asm = translator.translate(vm_code_string)
    """

    def __init__(self):
        self._out:       list = []
        self._lbl_cnt:   int  = 0
        self._cur_func:  str  = 'GLOBAL'

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _emit(self, *lines: str):
        self._out.extend(lines)

    def _new_label(self) -> str:
        lbl = f'VM_L{self._lbl_cnt}'
        self._lbl_cnt += 1
        return lbl

    # ------------------------------------------------------------------ #
    #  Public interface
    # ------------------------------------------------------------------ #

    def translate(self, vm_code: str) -> str:
        """
        Accept multi-line VM code string, return Hack Assembly string.
        Bootstrap code (SP=256, call Sys.init) is prepended automatically.
        """
        self._emit_bootstrap()

        for raw_line in vm_code.splitlines():
            line = raw_line.split('//')[0].strip()
            if not line:
                continue
            self._emit(f'// {line}')
            self._translate_line(line)

        return '\n'.join(self._out)

    # ------------------------------------------------------------------ #
    #  Bootstrap
    # ------------------------------------------------------------------ #

    def _emit_bootstrap(self):
        self._emit(
            '// === Bootstrap ===',
            '@256', 'D=A', '@SP', 'M=D',
        )
        self._emit(*self._call_asm('Sys.init', 0, ret_label='BOOTSTRAP_RET'))

    # ------------------------------------------------------------------ #
    #  Dispatch
    # ------------------------------------------------------------------ #

    def _translate_line(self, line: str):
        parts = line.split()
        cmd   = parts[0]

        if cmd == 'push':
            self._gen_push(parts[1], int(parts[2]))
        elif cmd == 'pop':
            self._gen_pop(parts[1], int(parts[2]))
        elif cmd in ('add', 'sub', 'and', 'or'):
            self._gen_binary(cmd)
        elif cmd in ('neg', 'not'):
            self._gen_unary(cmd)
        elif cmd in ('lt', 'gt', 'eq'):
            self._gen_compare(cmd)
        elif cmd == 'label':
            self._emit(f'({self._cur_func}${parts[1]})')
        elif cmd == 'goto':
            self._emit(f'@{self._cur_func}${parts[1]}', '0;JMP')
        elif cmd == 'if-goto':
            self._emit(
                '@SP', 'AM=M-1', 'D=M',
                f'@{self._cur_func}${parts[1]}', 'D;JNE',
            )
        elif cmd == 'function':
            self._gen_function(parts[1], int(parts[2]))
        elif cmd == 'call':
            self._emit(*self._call_asm(parts[1], int(parts[2])))
        elif cmd == 'return':
            self._gen_return()
        else:
            raise ValueError(f"Unknown VM command: {line!r}")

    # ------------------------------------------------------------------ #
    #  Push / Pop
    # ------------------------------------------------------------------ #

    def _gen_push(self, segment: str, index: int):
        """Load value into D, then push D onto stack."""
        if segment == 'constant':
            self._emit(f'@{index}', 'D=A')

        elif segment in _SEG_BASE:
            base = _SEG_BASE[segment]
            self._emit(f'@{base}', 'D=M', f'@{index}', 'A=D+A', 'D=M')

        elif segment == 'temp':
            self._emit(f'@{5 + index}', 'D=M')

        elif segment == 'pointer':
            reg = 'THIS' if index == 0 else 'THAT'
            self._emit(f'@{reg}', 'D=M')

        elif segment == 'static':
            self._emit(f'@{self._cur_func}.{index}', 'D=M')

        else:
            raise ValueError(f"Unknown push segment: {segment}")

        # Push D → stack
        self._emit('@SP', 'A=M', 'M=D', '@SP', 'M=M+1')

    def _gen_pop(self, segment: str, index: int):
        """Pop from stack into segment[index]."""
        # Compute target address → R13
        if segment in _SEG_BASE:
            base = _SEG_BASE[segment]
            self._emit(f'@{base}', 'D=M', f'@{index}', 'D=D+A', '@R13', 'M=D')

        elif segment == 'temp':
            self._emit(f'@{5 + index}', 'D=A', '@R13', 'M=D')

        elif segment == 'pointer':
            reg = 'THIS' if index == 0 else 'THAT'
            self._emit(f'@{reg}', 'D=A', '@R13', 'M=D')

        elif segment == 'static':
            self._emit(f'@{self._cur_func}.{index}', 'D=A', '@R13', 'M=D')

        else:
            raise ValueError(f"Unknown pop segment: {segment}")

        # Pop stack → *R13
        self._emit('@SP', 'AM=M-1', 'D=M', '@R13', 'A=M', 'M=D')

    # ------------------------------------------------------------------ #
    #  Arithmetic / Logic
    # ------------------------------------------------------------------ #

    def _gen_binary(self, op: str):
        ops = {'add': 'D+M', 'sub': 'M-D', 'and': 'D&M', 'or': 'D|M'}
        self._emit(
            '@SP', 'AM=M-1', 'D=M',   # pop y into D
            'A=A-1',                   # point to x (top-1)
            f'M={ops[op]}',            # x = x op y
        )

    def _gen_unary(self, op: str):
        expr = '-M' if op == 'neg' else '!M'
        self._emit('@SP', 'A=M-1', f'M={expr}')

    def _gen_compare(self, op: str):
        true_lbl = self._new_label()
        end_lbl  = self._new_label()
        jump = {'lt': 'JLT', 'gt': 'JGT', 'eq': 'JEQ'}[op]
        self._emit(
            '@SP', 'AM=M-1', 'D=M',        # pop y
            'A=A-1', 'D=M-D',              # D = x - y
            f'@{true_lbl}', f'D;{jump}',   # if condition true, jump
            '@SP', 'A=M-1', 'M=0',         # false → 0
            f'@{end_lbl}', '0;JMP',
            f'({true_lbl})',
            '@SP', 'A=M-1', 'M=-1',        # true → -1
            f'({end_lbl})',
        )

    # ------------------------------------------------------------------ #
    #  Function / Call / Return
    # ------------------------------------------------------------------ #

    def _gen_function(self, name: str, n_locals: int):
        self._cur_func = name
        self._emit(f'// function {name} {n_locals}', f'({name})')
        # Initialise locals to 0
        for _ in range(n_locals):
            self._emit('@SP', 'A=M', 'M=0', '@SP', 'M=M+1')

    def _call_asm(self, func: str, n_args: int, ret_label: str = None) -> list:
        """Return assembly lines that perform a VM call instruction."""
        if ret_label is None:
            ret_label = f'{self._cur_func}$ret.{self._new_label()}'

        return [
            # Push return address
            f'@{ret_label}', 'D=A', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Push LCL
            '@LCL',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Push ARG
            '@ARG',  'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Push THIS
            '@THIS', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # Push THAT
            '@THAT', 'D=M', '@SP', 'A=M', 'M=D', '@SP', 'M=M+1',
            # ARG = SP - 5 - n_args
            f'@{n_args + 5}', 'D=A', '@SP', 'D=M-D', '@ARG', 'M=D',
            # LCL = SP
            '@SP', 'D=M', '@LCL', 'M=D',
            # goto function
            f'@{func}', '0;JMP',
            # return address label
            f'({ret_label})',
        ]

    def _gen_return(self):
        self._emit(
            # FRAME = LCL  →  R14
            '@LCL', 'D=M', '@R14', 'M=D',
            # RET = *(FRAME-5)  →  R15
            '@5', 'A=D-A', 'D=M', '@R15', 'M=D',
            # *ARG = pop() (return value for caller)
            '@SP', 'AM=M-1', 'D=M', '@ARG', 'A=M', 'M=D',
            # SP = ARG + 1
            '@ARG', 'D=M+1', '@SP', 'M=D',
            # THAT = *(FRAME-1)
            '@R14', 'AM=M-1', 'D=M', '@THAT', 'M=D',
            # THIS = *(FRAME-2)
            '@R14', 'AM=M-1', 'D=M', '@THIS', 'M=D',
            # ARG = *(FRAME-3)
            '@R14', 'AM=M-1', 'D=M', '@ARG',  'M=D',
            # LCL = *(FRAME-4)
            '@R14', 'AM=M-1', 'D=M', '@LCL',  'M=D',
            # goto RET
            '@R15', 'A=M', '0;JMP',
        )