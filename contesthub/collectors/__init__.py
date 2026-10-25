from .contestkorea import ContestKoreaCollector
from .itchio import ItchioCollector
from .wevity import WevityCollector

COLLECTORS = {c.site: c for c in (WevityCollector, ContestKoreaCollector, ItchioCollector)}
