"""Check the shared Angr version and the FP exporter patch consumers require."""

import importlib.metadata
import unittest

from angr import claripy
import z3


class SharedAngrTest(unittest.TestCase):
    def test_version(self):
        for package in ("angr", "archinfo", "cle", "pyvex"):
            with self.subTest(package=package):
                self.assertEqual(importlib.metadata.version(package), "10.0.4")

    def test_fp_conversion_export(self):
        for width, sort in ((32, claripy.FSORT_FLOAT), (64, claripy.FSORT_DOUBLE)):
            value = claripy.BVS(f"bits_{width}", width, explicit_name=True)
            converted = value.val_to_fp(sort, signed=False)
            solver = claripy.Solver()
            solver.add(converted == claripy.FPV(1.0, sort))
            # Parsing catches explicit-mantissa widths in place of SMT-LIB's
            # significand widths. Satisfiability checks the resulting formula.
            smt = solver.to_smt2()
            parsed = z3.Solver()
            parsed.from_string(smt)
            self.assertEqual(parsed.check(), z3.sat)


if __name__ == "__main__":
    unittest.main()
