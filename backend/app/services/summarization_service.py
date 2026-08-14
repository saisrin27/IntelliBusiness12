import json
import os
from typing import Any, Dict, List

import requests
from ..services.document_processor import chunk_text


class SummarizationService:
    """Modular document summarization service with Gemini-ready API support.

    Implements hierarchical summarization for long documents: chunk -> summarize chunks -> aggregate -> final summary.
    """

    def __init__(self, api_key: str | None = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _build_prompt(self, text: str, filename: str) -> str:
        return (
            "You are IntelliBusiness, an enterprise document intelligence assistant.\n\n"
            "Analyze the provided business document and create an accurate, concise summary.\n"
            "Do not invent information. Only use information contained in the document.\n\n"
            "Return the result in the following JSON structure:\n"
            "{\n"
            "  \"executive_summary\": \"...\",\n"
            "  \"key_points\": [\"...\", \"...\"],\n"
            "  \"important_information\": [\"...\"],\n"
            "  \"action_items\": [\"...\"],\n"
            "  \"keywords\": [\"...\"]\n"
            "}\n\n"
            "If a section is not present in the document, use \"Not specified in the document.\" for summary or empty arrays for lists where appropriate.\n\n"
            f"Document name: {filename}\n\nDocument text:\n{text[:25000]}"
        )

    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("AI returned an invalid JSON object.")
        return parsed

    def _generate_from_gemini(self, text: str, filename: str) -> Dict[str, Any]:
        if not self.is_configured():
            raise ValueError("AI summarization is not configured.")

        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        payload = {
            "contents": [{"parts": [{"text": self._build_prompt(text, filename)}]}],
            "generationConfig": {
                "temperature": 0.3,
                "topP": 0.9,
                "maxOutputTokens": 1024,
            },
        }

        response = requests.post(api_url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise ValueError("Unable to generate the summary right now. Please try again.")

        data = response.json()
        result = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
        if not result:
            raise ValueError("AI returned an empty summary.")
        return self._extract_json_from_response(result)

    def summarize_document_text(self, text: str, filename: str) -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("The document does not contain extractable text.")

        if not self.is_configured():
            raise ValueError("AI summarization is not configured.")

        # If document is small enough, summarize in a single pass.
        if len(text) <= 6000:
            response = self._generate_from_gemini(text, filename)
        else:
            # Hierarchical summarization for long documents.
            chunks = chunk_text(text, chunk_size=3000, overlap=300)
            chunk_summaries: List[str] = []
            combined_key_points: List[str] = []
            combined_important: List[str] = []
            combined_actions: List[str] = []
            combined_keywords: List[str] = []

            for idx, chunk in enumerate(chunks, start=1):
                prompt_text = f"Chunk {idx}/{len(chunks)}:\n\n{chunk}"
                try:
                    partial = self._generate_from_gemini(prompt_text, f"{filename} (chunk {idx})")
                except Exception:
                    # If a chunk fails, skip but continue processing others.
                    continue

                chunk_summary = partial.get("executive_summary")
                if chunk_summary:
                    chunk_summaries.append(chunk_summary)

                if isinstance(partial.get("key_points"), list):
                    combined_key_points.extend(partial.get("key_points"))
                if isinstance(partial.get("important_information"), list):
                    combined_important.extend(partial.get("important_information"))
                if isinstance(partial.get("action_items"), list):
                    combined_actions.extend(partial.get("action_items"))
                if isinstance(partial.get("keywords"), list):
                    combined_keywords.extend(partial.get("keywords"))

            # Build an aggregation prompt from chunk summaries and lists
            aggregate_text_parts = []
            if chunk_summaries:
                aggregate_text_parts.append("\n\n".join(chunk_summaries))
            if combined_key_points:
                aggregate_text_parts.append("Key points:\n" + "\n".join(combined_key_points[:50]))
            if combined_important:
                aggregate_text_parts.append("Important info:\n" + "\n".join(combined_important[:50]))

            aggregate_text = "\n\n".join(aggregate_text_parts) or text[:20000]

            response = self._generate_from_gemini(aggregate_text, f"{filename} (aggregate)")

        cleaned = {
            "executive_summary": response.get("executive_summary") or "Not specified in the document.",
            "key_points": response.get("key_points") if isinstance(response.get("key_points"), list) else [],
            "important_information": response.get("important_information") if isinstance(response.get("important_information"), list) else [],
            "action_items": response.get("action_items") if isinstance(response.get("action_items"), list) else [],
            "keywords": response.get("keywords") if isinstance(response.get("keywords"), list) else [],
        }

        if not cleaned["keywords"]:
            cleaned["keywords"] = ["Document", "Business", "Summary", "Key", "Information"]

        # Normalize lists: trim whitespace and limit lengths
        cleaned["key_points"] = [kp.strip() for kp in cleaned["key_points"]][:20]
        cleaned["important_information"] = [info.strip() for info in cleaned["important_information"]][:20]
        cleaned["action_items"] = [act.strip() for act in cleaned["action_items"]][:20]
        cleaned["keywords"] = [kw.strip() for kw in cleaned["keywords"]][:10]

        return cleaned
