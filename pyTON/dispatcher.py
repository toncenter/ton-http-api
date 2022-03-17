import random

from datetime import datetime
from typing import Tuple


class Dispatcher:
    def __init__(self, n_liteservers):
        self.n_liteservers = n_liteservers

    def getLiteServerIndex(self, archival: bool=False) -> int:
        return random.randint(0, self.n_liteservers)

    def liteServerTaskFinished(self, ls_index: int):
        pass

    def getConsensusBlock(self) -> Tuple[int, "Timestamp"]:
        return 10, datetime.utcnowtimestamp()
