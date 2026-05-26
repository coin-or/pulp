"""Unit tests for cplex_cmd solver."""

from typing import ClassVar

import pulp.apis as solvers
from pulp.tests.solver_common import (
    BaseSolverTest,
    PulpTestConfig,
    _status,
)


class CPLEX_CMDTest(BaseSolverTest.PuLPTest):
    solveInst = solvers.CPLEX_CMD
    pulp_test_overrides: ClassVar[dict[str, PulpTestConfig]] = {
        "test_dual_variables_reduced_costs": PulpTestConfig(skip=False),
        "test_initial_value": PulpTestConfig(warm_start=True),
        "test_logPath": PulpTestConfig(skip=False, check_log_path=True),
        "test_long_var_name": PulpTestConfig(allow_pulp_error=True),
        "test_repeated_name": PulpTestConfig(expect_pulp_error=True),
        "test_unbounded": PulpTestConfig(
            okstatus=_status(
                "LpStatusInfeasible", "LpStatusUnbounded", "LpStatusUndefined"
            )
        ),
    }

    def test_parse_cplex_mipopt_solution(self):
        from io import StringIO

        file_content = """<?xml version = "1.0" encoding="UTF-8" standalone="yes"?>
                <CPLEXSolution version="1.2">
                <header
                    problemName="mipopt_solution_example.lp"
                    solutionName="incumbent"
                    solutionIndex="-1"
                    objectiveValue="442"
                    solutionTypeValue="3"
                    solutionTypeString="primal"
                    solutionStatusValue="101"
                    solutionStatusString="integer optimal solution"
                    solutionMethodString="mip"
                    primalFeasible="1"
                    dualFeasible="1"
                    MIPNodes="25471"
                    MIPIterations="282516"
                    writeLevel="1"/>
                <quality
                    epInt="1.0000000000000001e-05"
                    epRHS="9.9999999999999995e-07"
                    maxIntInfeas="8.8817841970012523e-16"
                    maxPrimalInfeas="0"
                    maxX="48"
                maxSlack="141"/>
                <linearConstraints>
                    <constraint name="C1" index="0" slack="0"/>
                    <constraint name="C2" index="1" slack="0"/>
                </linearConstraints>
                <variables>
                    <variable name="x" index="0" value="42"/>
                    <variable name="y" index="1" value="0"/>
                </variables>
                <objectiveValues>
                    <objective index="0" name="x" value="42"/>
                </objectiveValues>
                </CPLEXSolution>
            """
        solution_file = StringIO(file_content)
        _, _, reducedCosts, shadowPrices, _, _ = solvers.CPLEX_CMD.readsol(
            solution_file
        )
        self.assertTrue(all(c is None for c in reducedCosts.values()))
        self.assertTrue(all(c is None for c in shadowPrices.values()))
