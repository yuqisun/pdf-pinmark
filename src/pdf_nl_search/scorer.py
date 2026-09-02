import math
from dataclasses import dataclass, field

MULTI_TERM_BONUS = 2.0
PROXIMITY_BONUS = 1.0
PROXIMITY_WINDOW = 50


@dataclass
class ScoreArgs:
    weights: dict[str, float] = field(default_factory=dict)
    idf: dict[str, float] = field(default_factory=dict)


def compute_idf(df: dict[str, int], N: int) -> dict[str, float]:
    """df: term→出现该词的段落数；N: 总段落数。返回 term→idf。"""
    return {t: math.log(1.0 + N / (1.0 + c)) for t, c in df.items()}


def score_paragraph(args: ScoreArgs, hits: dict[str, list]) -> float:
    """hits: {term: [(norm_start, norm_end), ...]}（位置单调即可）。"""
    score = 0.0
    for term, spans in hits.items():
        w = args.weights.get(term, 1.0)
        idf = args.idf.get(term, 1.0)
        score += w * idf * math.log1p(len(spans))
    if len(hits) >= 2:
        score += MULTI_TERM_BONUS
    firsts = [spans[0][0] for spans in hits.values() if spans]
    if len(firsts) >= 2:
        d = min(abs(a - b) for i, a in enumerate(firsts) for b in firsts[i + 1 :])
        if d <= PROXIMITY_WINDOW:
            score += PROXIMITY_BONUS
    return score
