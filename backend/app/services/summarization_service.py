import json
import os
import re
from typing import Any, Dict, List

import requests
from ..services.document_processor import chunk_text


class SummarizationService:
    """Enterprise AI document summarization service powered by Google Gemini.

    Implements a full AI summarization pipeline with length-controlled compression and
    hierarchical chunk aggregation for long business documents.
    """

    def __init__(self, api_key: str | None = None, model_name: str = "gemini-flash-latest"):
        if not api_key or not os.getenv("GEMINI_API_KEY"):
            from dotenv import load_dotenv
            from pathlib import Path
            service_file = Path(__file__).resolve()
            candidate_envs = [
                service_file.parents[3] / ".env",
                service_file.parents[2] / ".env",
                Path.cwd() / ".env"
            ]
            for env_path in candidate_envs:
                if env_path.exists():
                    load_dotenv(env_path, override=True)
                    if os.getenv("GEMINI_API_KEY"):
                        break

        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("AI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if self.api_key:
            self.api_key = self.api_key.strip()
        self.model_name = model_name

    def is_configured(self) -> bool:
        if not self.api_key:
            return False
        key = self.api_key
        if key.startswith("your_") or "replace_" in key or key.lower() == "none":
            return False
        return True

    def _get_length_guideline(self, text: str) -> str:
        word_count = len(text.split())
        if word_count < 500:
            return "Target summary length: 80 to 150 words."
        elif word_count <= 2000:
            return "Target summary length: 150 to 300 words."
        else:
            return "Target summary length: 200 to 500 words."

    def _build_single_summary_prompt(self, text: str, filename: str) -> str:
        length_guideline = self._get_length_guideline(text)
        return (
            "You are an expert business document analyst, 'IntelliBusiness'.\n\n"
            "Your task is to create a genuine, concise summary of the document.\n\n"
            "IMPORTANT RULES:\n"
            "1. Do NOT copy the document text verbatim.\n"
            "2. Do NOT return the original paragraphs.\n"
            "3. Do NOT repeat large sections of the source.\n"
            "4. Analyze the entire document before answering.\n"
            "5. Combine related information into concise explanations.\n"
            "6. Remove repetition and unnecessary details.\n"
            "7. Rewrite the information in your own words while preserving the original meaning.\n"
            "8. Keep important numbers, dates, requirements, decisions, policies, and responsibilities.\n"
            "9. Do not invent any information.\n"
            "10. The final executive summary must be substantially shorter than the original document.\n"
            f"11. {length_guideline}\n\n"
            "Return ONLY valid JSON in this exact structure:\n"
            "{\n"
            '  "executive_summary": "A concise rewritten summary of the overall document.",\n'
            '  "key_points": [\n'
            '    "Important point 1",\n'
            '    "Important point 2",\n'
            '    "Important point 3"\n'
            "  ],\n"
            '  "important_information": [\n'
            '    "Important dates, numbers, rules, requirements, or decisions"\n'
            "  ],\n"
            '  "action_items": [\n'
            '    "Actions explicitly required in the document"\n'
            "  ],\n"
            '  "keywords": [\n'
            '    "keyword1",\n'
            '    "keyword2"\n'
            "  ]\n"
            "}\n\n"
            "If a list section (such as action_items) has no relevant items in the document, return an empty JSON array [].\n\n"
            f"Document Name: {filename}\n\n"
            f"Document Text:\n{text[:25000]}"
        )

    def _build_chunk_prompt(self, chunk_text: str, chunk_idx: int, total_chunks: int) -> str:
        return (
            f"Summarize section {chunk_idx}/{total_chunks} of a larger business document in a concise way.\n\n"
            "Do not copy the original text.\n"
            "Identify the main information, important facts, decisions, rules, dates, numbers, and responsibilities.\n"
            "This is only an intermediate summary and will later be combined with other section summaries.\n\n"
            "Return a concise rewritten summary.\n\n"
            f"Section Content:\n{chunk_text}"
        )

    def _build_final_summary_prompt(self, section_summaries: List[str], filename: str, full_word_count: int) -> str:
        length_guideline = (
            "Target summary length: 150 to 300 words."
            if full_word_count <= 2000
            else "Target summary length: 200 to 500 words."
        )
        combined_sections = "\n\n".join(
            f"--- Section {idx + 1} Summary ---\n{summary}"
            for idx, summary in enumerate(section_summaries)
        )
        return (
            "You are given summaries of multiple sections of the same business document.\n\n"
            "Create one coherent final document summary.\n\n"
            "Do NOT simply list or concatenate the section summaries.\n\n"
            "Instead:\n"
            "- Understand the document as a whole\n"
            "- Merge related ideas\n"
            "- Remove repetition\n"
            "- Prioritize the most important information\n"
            "- Create a concise executive-level explanation\n"
            f"- {length_guideline}\n\n"
            "Do not copy the input text verbatim.\n\n"
            "Return ONLY valid JSON in this exact structure:\n"
            "{\n"
            '  "executive_summary": "A concise rewritten summary of the overall document.",\n'
            '  "key_points": [\n'
            '    "Important point 1",\n'
            '    "Important point 2"\n'
            "  ],\n"
            '  "important_information": [\n'
            '    "Important dates, numbers, rules, requirements, or decisions"\n'
            "  ],\n"
            '  "action_items": [\n'
            '    "Actions explicitly required in the document"\n'
            "  ],\n"
            '  "keywords": [\n'
            '    "keyword1",\n'
            '    "keyword2"\n'
            "  ]\n"
            "}\n\n"
            f"Document Name: {filename}\n\n"
            f"Section Summaries:\n{combined_sections}"
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
        elif start != -1:
            text = text[start:]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            fixed_text = text
            if not fixed_text.endswith("}"):
                if fixed_text.count('"') % 2 != 0:
                    fixed_text += '"'
                if fixed_text.count('[') > fixed_text.count(']'):
                    fixed_text += ']'
                fixed_text += '}'
            try:
                parsed = json.loads(fixed_text)
            except json.JSONDecodeError as err:
                raise ValueError(f"Failed to parse AI JSON response: {err}")

        if not isinstance(parsed, dict):
            raise ValueError("AI returned an invalid JSON object.")
        if not parsed.get("executive_summary"):
            raise ValueError("AI response missing executive_summary field.")

        return parsed

    def _call_gemini_api(self, prompt: str) -> str:
        if not self.is_configured():
            raise ValueError("AI summarization is not configured. Please set a valid GEMINI_API_KEY in your .env file.")

        models_to_try = [
            "gemini-flash-lite-latest",
            "gemma-4-26b-a4b-it",
            "gemini-flash-latest",
            "gemini-3.5-flash",
            "gemini-1.5-flash",
        ]
        seen = set()
        models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        last_error = None
        for model in models:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.8,
                    "maxOutputTokens": 4096,
                },
            }

            try:
                response = requests.post(api_url, headers=headers, json=payload, timeout=45)
                if response.status_code == 200:
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and parts[0].get("text"):
                            return parts[0]["text"]
                else:
                    last_error = f"Model {model} returned status {response.status_code}: {response.text[:200]}"
            except Exception as e:
                last_error = str(e)

        raise ValueError(f"Unable to communicate with Gemini API ({last_error}).")




    def summarize_document_text(self, text: str, filename: str) -> Dict[str, Any]:
        if not text or not text.strip():
            raise ValueError("The document does not contain extractable text.")

        if not self.is_configured():
            raise ValueError("AI summarization is not configured. Please set a valid GEMINI_API_KEY in your .env file.")

        if len(text) <= 6000:
            prompt = self._build_single_summary_prompt(text, filename)
            raw_response = self._call_gemini_api(prompt)
            response = self._extract_json_from_response(raw_response)
        else:
            chunks = chunk_text(text, chunk_size=3500, overlap=300)
            chunk_summaries: List[str] = []

            for idx, chunk in enumerate(chunks, start=1):
                chunk_prompt = self._build_chunk_prompt(chunk, idx, len(chunks))
                try:
                    chunk_summary_text = self._call_gemini_api(chunk_prompt)
                    if chunk_summary_text:
                        chunk_summaries.append(chunk_summary_text.strip())
                except Exception:
                    continue

            if not chunk_summaries:
                prompt = self._build_single_summary_prompt(text[:10000], filename)
                raw_response = self._call_gemini_api(prompt)
                response = self._extract_json_from_response(raw_response)
            else:
                final_prompt = self._build_final_summary_prompt(chunk_summaries, filename, len(text.split()))
                raw_response = self._call_gemini_api(final_prompt)
                response = self._extract_json_from_response(raw_response)

        cleaned = {
            "executive_summary": (response.get("executive_summary") or "").strip(),
            "key_points": response.get("key_points") if isinstance(response.get("key_points"), list) else [],
            "important_information": response.get("important_information") if isinstance(response.get("important_information"), list) else [],
            "action_items": response.get("action_items") if isinstance(response.get("action_items"), list) else [],
            "keywords": response.get("keywords") if isinstance(response.get("keywords"), list) else [],
        }

        cleaned["key_points"] = [str(kp).strip() for kp in cleaned["key_points"] if str(kp).strip()][:15]
        cleaned["important_information"] = [str(info).strip() for info in cleaned["important_information"] if str(info).strip()][:15]
        cleaned["action_items"] = [str(act).strip() for act in cleaned["action_items"] if str(act).strip()][:15]
        cleaned["keywords"] = [str(kw).strip() for kw in cleaned["keywords"] if str(kw).strip()][:10]

        return cleaned

