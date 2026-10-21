"""
RetrievalCheck — la réponse repose-t-elle sur un contexte pertinent ?

Les règles du prompt RAG autorisent le modèle à compléter avec ses connaissances
générales. Ce check rend visible le cas où il n'avait en réalité rien de pertinent
à se mettre sous la dent (aucun chunk, ou meilleur score sous le seuil).

Le score d'un chunk est `1 - distance` (cf. rag_chat.py). Le seuil par défaut est un
point de départ à calibrer sur vos propres logs (il dépend du modèle d'embedding).
"""
from __future__ import annotations

from typing import List, Sequence

from .base import CheckResult, Finding, Severity, VerificationContext


class RetrievalCheck:
    name = "retrieval"
    blocking = False

    def __init__(self, min_score: float = 0.25):
        self.min_score = min_score

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckResult:
        if not ctx.is_rag:
            return CheckResult.skipped(self.name, "not a RAG answer")

        chunks = ctx.retrieved_chunks or []
        if not chunks:
            return CheckResult.from_findings(self.name, [Finding(
                "retrieval.no_context",
                Severity.WARNING,
                "No document was retrieved: the answer relies only on the model's general knowledge.",
            )])

        scores: List[float] = []
        for chunk in chunks:
            score = chunk.get("score")
            if isinstance(score, (int, float)):
                scores.append(float(score))
        if not scores:
            return CheckResult.skipped(self.name, "retrieved chunks carry no score")

        best = max(scores)
        top3 = sorted(scores, reverse=True)[:3]
        mean_top3 = sum(top3) / len(top3)
        note = f"best={best:.2f} mean_top3={mean_top3:.2f} threshold={self.min_score:.2f}"

        if best < self.min_score:
            return CheckResult.from_findings(self.name, [Finding(
                "retrieval.low_relevance",
                Severity.WARNING,
                f"Best retrieval score {best:.2f} is below the threshold {self.min_score:.2f}: "
                "the retrieved context is probably off-topic, the answer may not be grounded in your documents.",
                {"best": round(best, 3), "mean_top3": round(mean_top3, 3), "threshold": self.min_score},
            )], note=note)

        return CheckResult.passed(self.name, note=note)
