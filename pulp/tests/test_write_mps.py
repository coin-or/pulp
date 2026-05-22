import tempfile
import unittest
from pathlib import Path

from pulp import LpProblem, const

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mps"


class WriteMpsGoldenSmokeTest(unittest.TestCase):
    def test_write_mps_continuous_matches_golden(self) -> None:
        prob = LpProblem("continuous", const.LpMinimize)
        x = prob.add_variable("x", 0, 4)
        y = prob.add_variable("y", -1, 1)
        z = prob.add_variable("z", 0)
        prob += x + 4 * y + 9 * z, "obj"
        prob += x + y <= 5, "c1"
        prob += x + z >= 10, "c2"
        prob += -y + z == 7, "c3"

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.mps"
            prob.writeMPS(str(out), mip=False)
            got = out.read_bytes()
        want = (FIXTURE_DIR / "continuous.mps").read_bytes()
        self.assertEqual(got, want, "MPS output drifted from golden")
