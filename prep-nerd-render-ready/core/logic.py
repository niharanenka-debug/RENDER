import math
import re
from collections import Counter
from datetime import datetime, timezone

from .config import MAX_QUESTIONS, QUESTION_COUNTS


STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from",
    "how", "i", "in", "is", "it", "of", "on", "or", "please", "the", "this", "to", "was", "what", "when", "where", "which", "who", "why", "with",
}
SYNONYM_GROUPS = (
    {"explain", "describe", "clarify", "meaning", "define", "elaborate"},
    {"cause", "reason", "factor", "because", "lead", "result", "effect"},
    {"compare", "contrast", "difference", "similarity", "versus", "vs"},
    {"example", "instance", "illustration", "sample", "case"},
    {"benefit", "advantage", "strength", "pro", "positive"},
    {"drawback", "disadvantage", "limitation", "weakness", "con"},
    {"process", "steps", "method", "procedure", "workflow", "sequence"},
    {"important", "key", "main", "major", "central", "significant"},
    {"make", "produce", "convert", "create", "form", "synthesize"},
    {"sugar", "glucose", "carbohydrate", "sucrose"},
    {"sunlight", "light", "solar", "sun"},
)
SYNONYM_MAP = {word: group for group in SYNONYM_GROUPS for word in group}


def normalize_count(n: int) -> int:
    n = int(n)
    if n not in QUESTION_COUNTS:
        raise ValueError("Question count must be 5, 10, 15, 20, or 25")
    return min(n, MAX_QUESTIONS)


def score_questions(questions, answers):
    correct = sum(1 for index, question in enumerate(questions) if answers.get(index) == question["correct_answer"])
    total = len(questions)
    return {
        "correct": correct,
        "total": total,
        "percentage": round(correct / total * 100, 1) if total else 0,
        "unanswered": total - len(answers),
    }


def mistake_from_question(question, selected=None):
    return {
        "question": question["question"],
        "options": question["options"],
        "selected_answer": selected or "",
        "correct_answer": question["correct_answer"],
        "explanation": question.get("explanation", ""),
        "topic": question.get("topic", "General"),
        "difficulty": question.get("difficulty", "Medium"),
        "source_ref": question.get("source_ref", ""),
        "status": "Needs More Practice",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def chunk_text(text, size=7000, overlap=500):
    text = text.strip()
    if not text:
        return []
    size = max(1, int(size))
    overlap = min(max(0, int(overlap)), size - 1)
    output = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        output.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return output


def _terms(text):
    terms = [term for term in re.findall(r"[a-z0-9]+", text.lower()) if term not in STOP_WORDS and len(term) > 1]
    expanded = list(terms)
    for term in terms:
        expanded.extend(SYNONYM_MAP.get(term, ()))
    return Counter(expanded)


def rank_chunks(question, chunks, limit=4, min_score=0.015, min_absolute_score=0.12):
    """Rank source passages using BM25-like relevance with lightweight synonym expansion."""
    if not chunks:
        return []
    query_terms = _terms(question)
    if not query_terms:
        return []
    documents = [_terms(chunk) for chunk in chunks]
    lengths = [max(1, sum(counts.values())) for counts in documents]
    average_length = sum(lengths) / len(lengths)
    document_frequency = {
        term: sum(1 for document in documents if term in document)
        for term in query_terms
    }
    scored = []
    k1, b = 1.5, 0.75
    for index, (chunk, terms, length) in enumerate(zip(chunks, documents, lengths)):
        score = 0.0
        for term, query_count in query_terms.items():
            frequency = terms.get(term, 0)
            if not frequency:
                continue
            df = document_frequency.get(term, 0)
            inverse = math.log(1 + (len(chunks) - df + 0.5) / (df + 0.5))
            norm = frequency + k1 * (1 - b + b * length / average_length)
            score += inverse * (frequency * (k1 + 1) / norm) * min(query_count, 2)
        scored.append((score, index, chunk))
    maximum = max((score for score, _, _ in scored), default=0.0)
    if maximum < min_absolute_score:
        return []
    scored = [(score, index, chunk) for score, index, chunk in scored if score / maximum >= min_score]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [{"index": index, "text": chunk, "score": score / maximum} for score, index, chunk in scored[:limit]]
