"""Check AMD64 memory CMPXCHG accumulator semantics in the shared Angr runtime."""

import unittest

import angr


class MemoryCmpxchgTest(unittest.TestCase):
    def test_dword_accumulator(self):
        initial_rax = 0x1234567811223344
        replacement = 0x76543210
        address = 0x1000
        for prefix in (b"", b"\xf0"):
            # [lock] cmpxchg dword ptr [rdi], ecx
            project = angr.load_shellcode(prefix + b"\x0f\xb1\x0f", arch="amd64")
            for old, expected_rax, expected_memory, expected_zf in (
                (0x11223344, initial_rax, replacement, 1),
                (0xFEDCBA98, 0x00000000FEDCBA98, 0xFEDCBA98, 0),
            ):
                with self.subTest(locked=bool(prefix), old=hex(old)):
                    state = project.factory.blank_state(addr=0)
                    state.options.discard(angr.options.UNICORN)
                    state.regs.rax = initial_rax
                    state.regs.rcx = replacement
                    state.regs.rdi = address
                    state.memory.store(address, old, size=4, endness="Iend_LE")
                    (after,) = project.factory.successors(state, num_inst=1).flat_successors
                    memory = after.memory.load(address, 4, endness="Iend_LE")
                    self.assertEqual(after.solver.eval_one(after.regs.rax), expected_rax)
                    self.assertEqual(after.solver.eval_one(memory), expected_memory)
                    self.assertEqual(after.solver.eval_one(after.regs.eflags[6]), expected_zf)


if __name__ == "__main__":
    unittest.main()
