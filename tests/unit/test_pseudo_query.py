"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, pseudo-query, unit-test]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine.traversal.pseudo_query module.
"""

from __future__ import annotations

import pytest

from engine.traversal.pseudo_query import (
    PassageQueries,
    PseudoQueryGenerator,
    QuestionTriplet,
)


class MockLLM:
    """Mock LLM that returns numbered questions."""

    def __init__(self, response_template: str = "1. Question {i}?") -> None:
        self._template = response_template
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        # Detect how many questions are requested from prompt
        if "exactly 2" in prompt:
            n = 2
        elif "exactly 4" in prompt:
            n = 4
        else:
            n = 3  # default fallback

        lines = [f"{i + 1}. What is question {i + 1} about this topic?" for i in range(n)]
        return "\n".join(lines)


class MockKeywordExtractor:
    """Mock keyword extractor."""

    def extract(self, text: str) -> frozenset[str]:
        # Simple: return words longer than 3 chars
        words = text.lower().split()
        return frozenset(w for w in words if len(w) > 3)


class MockEmbeddingEncoder:
    """Mock embedding encoder."""

    def encode(self, text: str) -> tuple[float, ...]:
        # Hash-based fake embedding
        val = float(hash(text) % 1000) / 1000.0  # nosemgrep: float-requires-try-except
        return (val, 1.0 - val, 0.5)


class TestPseudoQueryGenerator:
    """Tests for PseudoQueryGenerator class."""

    def test_generate_incoming(self) -> None:
        """Should generate n incoming questions."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        questions = gen.generate_incoming_questions("Some passage text.", n=2)
        assert len(questions) == 2
        assert all(isinstance(q, str) for q in questions)
        assert llm.call_count == 1

    def test_generate_outgoing(self) -> None:
        """Should generate m outgoing questions."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        questions = gen.generate_outgoing_questions("Some passage text.", m=4)
        assert len(questions) == 4
        assert llm.call_count == 1

    def test_empty_passage_raises(self) -> None:
        """Empty passage should raise ValueError."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        with pytest.raises(ValueError, match="passage must be non-empty"):
            gen.generate_incoming_questions("", n=2)

    def test_whitespace_passage_raises(self) -> None:
        """Whitespace-only passage should raise ValueError."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        with pytest.raises(ValueError, match="passage must be non-empty"):
            gen.generate_outgoing_questions("   ", m=4)

    def test_n_less_than_one_raises(self) -> None:
        """n < 1 should raise ValueError."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        with pytest.raises(ValueError, match="n must be >= 1"):
            gen.generate_incoming_questions("passage", n=0)

    def test_m_less_than_one_raises(self) -> None:
        """m < 1 should raise ValueError."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)
        with pytest.raises(ValueError, match="m must be >= 1"):
            gen.generate_outgoing_questions("passage", m=0)

    def test_generate_full_with_enrichment(self) -> None:
        """Full generation with keyword extraction and embedding."""
        llm = MockLLM()
        kw = MockKeywordExtractor()
        emb = MockEmbeddingEncoder()
        gen = PseudoQueryGenerator(
            llm=llm,
            keyword_extractor=kw,
            embedding_encoder=emb,
        )

        result = gen.generate(
            passage_id="p_001",
            passage_text="The mitochondria is the powerhouse of the cell.",
            n_incoming=2,
            m_outgoing=4,
        )

        assert isinstance(result, PassageQueries)
        assert result.passage_id == "p_001"
        assert len(result.incoming) == 2
        assert len(result.outgoing) == 4

        # Check triplets have enrichment
        for triplet in result.incoming + result.outgoing:
            assert isinstance(triplet, QuestionTriplet)
            assert len(triplet.question) > 0
            assert isinstance(triplet.keywords, frozenset)
            assert len(triplet.embedding) == 3  # Mock encoder returns 3-dim

    def test_generate_without_enrichment(self) -> None:
        """Generation without extractors should have empty keywords/embeddings."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)

        result = gen.generate(
            passage_id="p_002",
            passage_text="Some text here.",
            n_incoming=2,
            m_outgoing=4,
        )

        for triplet in result.incoming + result.outgoing:
            assert triplet.keywords == frozenset()
            assert triplet.embedding == ()

    def test_generate_batch(self) -> None:
        """Batch generation should process multiple passages."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)

        passages = [
            {"id": "p1", "text": "First passage about science."},
            {"id": "p2", "text": "Second passage about history."},
            {"id": "p3", "text": "Third passage about math."},
        ]

        results = gen.generate_batch(passages, n_incoming=2, m_outgoing=4)
        assert len(results) == 3
        assert results[0].passage_id == "p1"
        assert results[2].passage_id == "p3"
        # Each passage needs 2 LLM calls (incoming + outgoing)
        assert llm.call_count == 6

    def test_generate_batch_skips_empty(self) -> None:
        """Batch should skip empty passages."""
        llm = MockLLM()
        gen = PseudoQueryGenerator(llm=llm)

        passages = [
            {"id": "p1", "text": "Valid passage."},
            {"id": "p2", "text": ""},
            {"id": "p3", "text": "Another valid passage."},
        ]

        results = gen.generate_batch(passages)
        assert len(results) == 2


class TestParseQuestions:
    """Tests for question parsing logic."""

    def test_numbered_lines(self) -> None:
        """Should parse numbered lines correctly."""
        response = "1. First question?\n2. Second question?\n3. Third question?"
        questions = PseudoQueryGenerator._parse_questions(response, 3)
        assert len(questions) == 3
        assert questions[0] == "First question?"

    def test_dash_prefixed_lines(self) -> None:
        """Should parse dash-prefixed lines."""
        response = "- First question?\n- Second question?"
        questions = PseudoQueryGenerator._parse_questions(response, 2)
        assert len(questions) == 2

    def test_truncates_excess(self) -> None:
        """Should truncate to expected count."""
        response = "1. Q1?\n2. Q2?\n3. Q3?\n4. Q4?\n5. Q5?"
        questions = PseudoQueryGenerator._parse_questions(response, 3)
        assert len(questions) == 3

    def test_filters_short_fragments(self) -> None:
        """Should filter fragments shorter than 5 chars."""
        response = "1. What is the meaning of life?\n2. Hi\n3. Where is the library?"
        questions = PseudoQueryGenerator._parse_questions(response, 3)
        # "Hi" (2 chars) should be filtered
        assert all(len(q) > 5 for q in questions)

    def test_empty_response(self) -> None:
        """Empty response should return empty list."""
        questions = PseudoQueryGenerator._parse_questions("", 3)
        assert questions == []
