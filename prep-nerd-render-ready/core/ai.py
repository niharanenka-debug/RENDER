import json
import math

from .config import EMBEDDING_MODEL, MODEL, api_key
from .logic import chunk_text, rank_chunks


class AIError(RuntimeError):
    pass


class GeminiService:
    def __init__(self, model=MODEL):
        self.model = model
        self.client = None
        key = api_key()
        if key:
            try:
                from google import genai
                self.client = genai.Client(api_key=key)
            except Exception as exc:
                raise AIError("Gemini SDK initialization failed.") from exc

    def generate(self, prompt):
        if not self.client:
            raise AIError("Set GEMINI_API_KEY in the service environment to use AI features.")
        try:
            response = self.client.models.generate_content(model=self.model, contents=prompt)
            text = getattr(response, "text", None)
            if not text:
                raise AIError("Gemini returned an empty response")
            return text
        except AIError:
            raise
        except Exception as exc:
            raise AIError("Gemini request failed.") from exc

    @staticmethod
    def _interaction_text(response):
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        text = getattr(response, "output_text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        fragments = []
        for item in getattr(response, "output", []) or []:
            for part in getattr(item, "content", []) or []:
                value = getattr(part, "text", None)
                if value:
                    fragments.append(value)
        return "\n".join(fragments).strip()

    def generate_url_context(self, url, prompt):
        """Use Gemini's URL Context tool to create study notes for a public page."""
        if not self.client:
            raise AIError("Add GEMINI_API_KEY to use Gemini URL Context.")
        try:
            response = self.client.interactions.create(
                model=self.model,
                input=f"{prompt}\n\nURL: {url}",
                tools=[{"type": "url_context"}],
            )
            text = self._interaction_text(response)
            if not text:
                raise AIError("Gemini returned an empty response.")
            return text
        except AIError:
            raise
        except Exception as exc:
            raise AIError("Gemini URL Context request failed.") from exc

    def generate_youtube_notes(self, url, prompt):
        """Use a public YouTube video input to create study notes, not a transcript."""
        if not self.client:
            raise AIError("A Gemini API key is required to process public YouTube videos.")
        try:
            response = self.client.interactions.create(
                model=self.model,
                input=[{"type": "text", "text": prompt}, {"type": "video", "uri": url}],
            )
            text = self._interaction_text(response)
            if not text:
                raise AIError("Gemini returned an empty response.")
            return text
        except AIError:
            raise
        except Exception as exc:
            raise AIError("Gemini video processing request failed.") from exc

    def json(self, prompt):
        text = self.generate(prompt).strip()
        if text.startswith("```json"):
            text = text[len("```json"):]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except Exception as exc:
            raise AIError(f"Gemini returned invalid JSON: {exc}")

    @staticmethod
    def _cosine(left, right):
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def retrieve(self, question, content, limit=4, history=()):
        # Expand short follow-ups with the prior user question for retrieval only.
        recent_user = next((message for role, message in reversed(history) if role == "user"), "")
        query = question
        if recent_user and len(question.split()) <= 8 and any(
            token in question.lower().split() for token in ("it", "that", "this", "they", "those", "them", "why", "how")
        ):
            query = f"{recent_user} {question}"

        chunks = chunk_text(content, size=2400, overlap=240)
        if not chunks:
            return []

        # Prefer Gemini embeddings when the configured model/API supports them.
        # The lexical ranker remains a deterministic, dependency-free fallback.
        if self.client:
            try:
                passages = chunks[:80]
                response = self.client.models.embed_content(
                    model=EMBEDDING_MODEL,
                    contents=[*passages, query],
                )
                vectors = [getattr(item, "values", None) for item in getattr(response, "embeddings", [])]
                if len(vectors) == len(passages) + 1 and all(vector for vector in vectors):
                    query_vector = vectors[-1]
                    ranked = sorted(
                        ((self._cosine(vector, query_vector), index, text) for index, (vector, text) in enumerate(zip(vectors[:-1], passages))),
                        reverse=True,
                    )
                    best = max((score for score, _, _ in ranked), default=0.0)
                    if best >= 0.20:
                        return [
                            {"index": index, "text": text, "score": score}
                            for score, index, text in ranked[:limit]
                            if score >= max(0.20, best * 0.78)
                        ]
            except Exception:
                # Some Gemini SDK/model versions do not support batched embeddings;
                # fall back to local ranking instead of failing the chat interaction.
                pass
        return rank_chunks(query, chunks, limit=limit)

    def answer_question(self, question, content, history=()):
        passages = self.retrieve(question, content, history=history)
        context = "\n\n".join(
            f"[Retrieved passage {index + 1}]\n{passage['text']}"
            for index, passage in enumerate(passages)
        ) or "No passages were confidently matched from the supplied notes."
        recent_history = "\n".join(
            f"{role.title()}: {message}" for role, message in list(history)[-8:]
        ) or "No earlier turns."
        prompt = (
            "You are prep-Nerd.ai, a precise, friendly study tutor. Understand the student's intent, synonyms, "
            "natural phrasing, and follow-up questions. Use the supplied notes as the primary source. First answer "
            "what the notes support and cite only the retrieved passage labels shown below (for example, [Retrieved passage 1]). "
            "If the notes do not contain a fact, say briefly that it is not explicit in the notes; when a useful explanation "
            "is possible, add a clearly labeled 'Additional context' section and distinguish it from note-based facts. "
            "Do not invent quotations, page numbers, or source facts. Explain concepts with a concise example when helpful. "
            "Resolve pronouns and follow-ups using conversation history. If the question is ambiguous, answer the likely intent "
            "and ask one focused follow-up rather than refusing.\n\n"
            f"RECENT CONVERSATION:\n{recent_history}\n\n"
            f"RELEVANT SOURCE PASSAGES:\n{context}\n\n"
            f"STUDENT QUESTION:\n{question}"
        )
        return self.generate(prompt)

    def analyze(self, task, content, depth="Standard"):
        chunks = chunk_text(content)
        if not chunks:
            raise AIError("Add some study material first.")
        cap = {"Quick": 1, "Standard": 3, "Deep": 6,
               "Exhaustive": len(chunks), "Automatic": min(3, len(chunks))}.get(depth, 3)
        count = min(max(1, cap), len(chunks))
        if count >= len(chunks):
            selected = chunks
        elif count == 1:
            selected = [chunks[0]]
        else:
            # Sample across the full source instead of silently ignoring later sections.
            positions = [round(i * (len(chunks) - 1) / (count - 1)) for i in range(count)]
            selected = [chunks[index] for index in positions]
        partial = len(selected) < len(chunks)
        prompt = (
            f"You are prep-Nerd.ai, a careful study assistant. Analysis depth: {depth}. "
            f"Return accurate, useful output for this task: {task}.\n"
            f"Coverage note: {'partial sample across the source; mention the limit where material is omitted' if partial else 'complete source'}\n"
            "Treat the provided source as primary and do not invent unsupported details.\nSOURCE:\n"
            + "\n---\n".join(selected)
        )
        return self.generate(prompt)
