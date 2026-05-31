from typing import Literal
from preparedness_turn_completer.turn_completer import TurnCompleter
from nanoeval.solvers.computer_tasks.code_execution_interface import ComputerInterface

from .base import *
from .detect import DetectGrader
from .patch import PatchGrader
from .exploit import ExploitGrader

def build_grader(
    mode: Literal["detect", "patch", "exploit"],
    computer: ComputerInterface,
    turn_completer: TurnCompleter,
) -> EVMbenchGrader:
    if mode == "detect":
        return DetectGrader(computer, turn_completer)
    elif mode == "patch":
        return PatchGrader(computer)
    else:
        return ExploitGrader(computer)
