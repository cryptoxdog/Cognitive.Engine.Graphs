"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [traversal]
tags: [hoprag, pseudo-query, indexing, enrichment]
owner: engine-team
status: active
--- /L9_META ---

Pseudo-query generation for HopRAG edge enrichment.

Implements Query Simulation from HopRAG (ACL 2025, §3.1):
For each passage, generate in-coming and out-coming pseudo-queries
that serve as edge metadata for graph traversal.

- In-coming questions (Q-): questions whose answers are within the passage.
- Out-coming questions (Q+): questions arising from the passage that
  cannot be answered by it alone.

Prompt templates follow HopRAG paper Fig 4 (in-coming) and Fig 5 (out-coming).

Consumes:
- Passage text from graph vertices
- LLM API for question generation

Produces:
- Question triplets: (question_text, NER_keywords, embedding_vector)
- Consumed by EdgeMerger for edge creation

Integrates with:
- engine.hoprag.indexer.GraphIndexBuilder (called during indexing phase)
- engine.traversal.edge_merger.EdgeMerger (consumes generated triplets)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ── Prompt Templates (per HopRAG Fig 4, Fig 5) ──────────────────────


INCOMING_PROMPT_TEMPLATE = """\
You are a question generation assistant. Given the following passage, \
generate exactly {n} questions whose answers can be found WITHIN the passage.

These questions should represent what a user might ask that this passage \
can satisfy. The questions should be diverse and cover different aspects \
of the passage content.

Passage:
{passage}

Generate exactly {n} questions, one per line. Output ONLY the questions, \
nothing else.
"""

OUTGOING_PROMPT_TEMPLATE = """\
You are a question generation assistant. Given the following passage, \
generate exactly {m} follow-up questions that ARISE from reading this \
passage but CANNOT be answered by it alone.

These questions represent logical next steps in understanding — things \
a reader would want to know after reading this passage, which require \
information from other sources.

Passage:
{passage}

Generate exactly {m} questions, one per line. Output ONLY the questions, \
nothing else.
"""


# ── Data Structures ──────────────────────────────────────────────────


@dataclass(frozen=True)
class QuestionTriplet:
    """A pseudo-query triplet with sparse and dense representations.

    Attributes:
        question: The generated question text.
        keywords: NER-extracted keyword set for sparse matching.
        embedding: Dense embedding vector for similarity matching.
    """

    question: str
    keywords: frozenset[str] = frozenset()
    embedding: tuple[float, ...] = ()


@dataclass
class PassageQueries:
    """All generated pseudo-queries for a single passage.

    Attributes:
        passage_id: Identifier for the source passage/vertex.
        incoming: In-coming question triplets (answerable by this passage).
        outgoing: Out-coming question triplets (not answerable by this passage).
    """

    passage_id: str
    incoming: list[QuestionTriplet] = field(default_factory=list)
    outgoing: list[QuestionTriplet] = field(default_factory=list)


# ── Protocols ────────────────────────────────────────────────────────


class LLMGenerator(Protocol):
    """Protocol for LLM text generation."""

    def generate(self, prompt: str) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The input prompt.

        Returns:
            Generated text response.
        """
        ...


class KeywordExtractor(Protocol):
    """Protocol for NER keyword extraction."""

    def extract(self, text: str) -> frozenset[str]:
        """Extract keywords from text.

        Args:
            text: Input text.

        Returns:
            Set of extracted keyword strings.
        """
        ...


class EmbeddingEncoder(Protocol):
    """Protocol for text embedding."""

    def encode(self, text: str) -> tuple[float, ...]:
        """Encode text into a dense embedding vector.

        Args:
            text: Input text.

        Returns:
            Embedding vector as tuple of floats.
        """
        ...


# ── Main Generator ───────────────────────────────────────────────────


class PseudoQueryGenerator:
    """Generates pseudo-queries for passage vertices.

    For each passage, produces in-coming questions (answerable by the passage)
    and out-coming questions (arising from the passage but not answerable by it).
    Each question is enriched with NER keywords and embedding vectors.

    Usage::

        generator = PseudoQueryGenerator(
            llm=my_llm_client,
            keyword_extractor=my_ner,
            embedding_encoder=my_encoder,
        )
        result = generator.generate(
            passage_id="p_001",
            passage_text="The mitochondria is the powerhouse of the cell...",
            n_incoming=2,
            m_outgoing=4,
        )
        print(len(result.incoming))   # 2
        print(len(result.outgoing))   # 4
    """

    def __init__(
        self,
        llm: LLMGenerator,
        keyword_extractor: KeywordExtractor | None = None,
        embedding_encoder: EmbeddingEncoder | None = None,
        incoming_template: str = INCOMING_PROMPT_TEMPLATE,
        outgoing_template: str = OUTGOING_PROMPT_TEMPLATE,
    ) -> None:
        """Initialize PseudoQueryGenerator.

        Args:
            llm: LLM client for question generation.
            keyword_extractor: Optional NER keyword extractor.
            embedding_encoder: Optional text embedding encoder.
            incoming_template: Prompt template for in-coming questions.
            outgoing_template: Prompt template for out-coming questions.
        """
        self._llm = llm
        self._keyword_extractor = keyword_extractor
        self._embedding_encoder = embedding_encoder
        self._incoming_template = incoming_template
        self._outgoing_template = outgoing_template

    def generate_incoming_questions(
        self,
        passage: str,
        n: int = 2,
    ) -> list[str]:
        """Generate in-coming questions for a passage.

        In-coming questions are those whose answers can be found within
        the given passage. They represent what the passage can satisfy.

        Args:
            passage: The passage text.
            n: Number of questions to generate. Default 2.

        Returns:
            List of question strings.

        Raises:
            ValueError: If passage is empty or n < 1.
        """
        if not passage or not passage.strip():
            msg = "passage must be non-empty"
            raise ValueError(msg)
        if n < 1:
            msg = f"n must be >= 1, got {n}"
            raise ValueError(msg)

        prompt = self._incoming_template.format(n=n, passage=passage)
        response = self._llm.generate(prompt)
        questions = self._parse_questions(response, n)

        logger.debug("Generated %d incoming questions for passage", len(questions))
        return questions

    def generate_outgoing_questions(
        self,
        passage: str,
        m: int = 4,
    ) -> list[str]:
        """Generate out-coming questions for a passage.

        Out-coming questions arise from reading the passage but cannot
        be answered by it alone. They represent logical next-hops.

        Args:
            passage: The passage text.
            m: Number of questions to generate. Default 4.

        Returns:
            List of question strings.

        Raises:
            ValueError: If passage is empty or m < 1.
        """
        if not passage or not passage.strip():
            msg = "passage must be non-empty"
            raise ValueError(msg)
        if m < 1:
            msg = f"m must be >= 1, got {m}"
            raise ValueError(msg)

        prompt = self._outgoing_template.format(m=m, passage=passage)
        response = self._llm.generate(prompt)
        questions = self._parse_questions(response, m)

        logger.debug("Generated %d outgoing questions for passage", len(questions))
        return questions

    def generate(
        self,
        passage_id: str,
        passage_text: str,
        n_incoming: int = 2,
        m_outgoing: int = 4,
    ) -> PassageQueries:
        """Generate all pseudo-queries for a passage with full enrichment.

        Generates both in-coming and out-coming questions, then enriches
        each with NER keywords and embedding vectors (if extractors provided).

        Args:
            passage_id: Identifier for the passage/vertex.
            passage_text: The passage text content.
            n_incoming: Number of in-coming questions.
            m_outgoing: Number of out-coming questions.

        Returns:
            PassageQueries with enriched question triplets.
        """
        incoming_qs = self.generate_incoming_questions(passage_text, n_incoming)
        outgoing_qs = self.generate_outgoing_questions(passage_text, m_outgoing)

        incoming_triplets = [self._enrich_question(q) for q in incoming_qs]
        outgoing_triplets = [self._enrich_question(q) for q in outgoing_qs]

        return PassageQueries(
            passage_id=passage_id,
            incoming=incoming_triplets,
            outgoing=outgoing_triplets,
        )

    def generate_batch(
        self,
        passages: list[dict[str, str]],
        n_incoming: int = 2,
        m_outgoing: int = 4,
    ) -> list[PassageQueries]:
        """Generate pseudo-queries for a batch of passages.

        Args:
            passages: List of dicts with 'id' and 'text' keys.
            n_incoming: Number of in-coming questions per passage.
            m_outgoing: Number of out-coming questions per passage.

        Returns:
            List of PassageQueries, one per passage.
        """
        results: list[PassageQueries] = []
        for i, passage in enumerate(passages):
            pid = passage.get("id", f"p_{i:04d}")
            text = passage.get("text", "")
            if not text.strip():
                logger.warning("Skipping empty passage %s", pid)
                continue

            try:
                pq = self.generate(
                    passage_id=pid,
                    passage_text=text,
                    n_incoming=n_incoming,
                    m_outgoing=m_outgoing,
                )
                results.append(pq)
            except Exception:
                logger.exception("Failed to generate queries for passage %s", pid)

        logger.info(
            "Generated pseudo-queries for %d/%d passages",
            len(results),
            len(passages),
        )
        return results

    def _enrich_question(self, question: str) -> QuestionTriplet:
        """Enrich a question with keywords and embedding.

        Args:
            question: The question text.

        Returns:
            QuestionTriplet with optional keywords and embedding.
        """
        keywords: frozenset[str] = frozenset()
        embedding: tuple[float, ...] = ()

        if self._keyword_extractor is not None:
            try:
                keywords = self._keyword_extractor.extract(question)
            except Exception:
                logger.warning("Keyword extraction failed for question", exc_info=True)

        if self._embedding_encoder is not None:
            try:
                embedding = self._embedding_encoder.encode(question)
            except Exception:
                logger.warning("Embedding encoding failed for question", exc_info=True)

        return QuestionTriplet(
            question=question,
            keywords=keywords,
            embedding=embedding,
        )

    @staticmethod
    def _parse_questions(response: str, expected_count: int) -> list[str]:
        """Parse LLM response into individual question strings.

        Args:
            response: Raw LLM response text.
            expected_count: Expected number of questions.

        Returns:
            List of cleaned question strings.
        """
        lines = response.strip().split("\n")
        questions: list[str] = []

        for line in lines:
            cleaned = line.strip()
            # Remove numbering prefixes like "1.", "1)", "- "
            if cleaned and cleaned[0].isdigit():
                # Remove "1. " or "1) " prefix
                for sep in [". ", ") ", ": "]:
                    idx = cleaned.find(sep)
                    if idx != -1 and idx < 5:
                        cleaned = cleaned[idx + len(sep) :]
                        break
            elif cleaned.startswith("- "):
                cleaned = cleaned[2:]

            cleaned = cleaned.strip()
            if cleaned and len(cleaned) > 5:  # Filter out tiny fragments
                questions.append(cleaned)

        if len(questions) > expected_count:
            questions = questions[:expected_count]

        return questions
