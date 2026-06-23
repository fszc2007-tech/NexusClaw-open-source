from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.core.config import settings
from app.core.text_locale import format_reply_text


class DeepSeekService:
    def is_enabled(self) -> bool:
        return bool(settings.DEEPSEEK_API_KEY)

    def rewrite_query(self, query: str, history: list[dict[str, str]]) -> str:
        cleaned = " ".join(query.strip().split())
        if not cleaned:
            return ""
        if not self.is_enabled() or not settings.DEEPSEEK_ENABLE_QUERY_REWRITE or not history:
            return cleaned

        prompt = (
            "请将用户最后一个问题改写成适合检索的完整问题。"
            "如果原问题已经完整，就直接返回原问题。"
            "只输出改写后的问题，不要输出解释。\n\n"
            f"历史对话：\n{self._history_text(history)}\n\n"
            f"最后问题：{cleaned}"
        )
        try:
            content = self._chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个面向知识检索的 query rewrite 助手。"},
                    {"role": "user", "content": prompt},
                ]
            )
            return content.strip() or cleaned
        except Exception:  # noqa: BLE001
            return cleaned

    def check_retrieval(self, query: str, hits: list[dict[str, Any]]) -> bool:
        if not hits:
            return False
        top_score = float(hits[0].get("score") or 0.0)
        if top_score >= max(settings.RETRIEVAL_MIN_SCORE, 0.35):
            return True
        if not self.is_enabled() or not settings.DEEPSEEK_ENABLE_RETRIEVAL_GUARD:
            return False

        prompt = (
            "判断下面检索结果是否足以回答用户问题。"
            "如果可以回答，输出 YES；如果明显不足，输出 NO。"
            "只输出 YES 或 NO。\n\n"
            f"问题：{query}\n\n"
            f"检索结果：\n{self._references_text(hits[:3])}"
        )
        try:
            content = self._chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个严格的检索结果可用性审查器。"},
                    {"role": "user", "content": prompt},
                ]
            )
            return content.strip().upper().startswith("YES")
        except Exception:  # noqa: BLE001
            return False

    def answer(
        self,
        system_prompt: str,
        runtime_prompt: str,
        reply_locale: str = "zh-Hant",
    ) -> tuple[str, str]:
        if not self.is_enabled():
            raise RuntimeError("deepseek_not_configured")
        answer = self._chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": runtime_prompt},
            ]
        )
        return format_reply_text(answer, reply_locale), settings.DEEPSEEK_CHAT_MODEL

    def extract_structured_json(
        self,
        system_prompt: str,
        runtime_prompt: str,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        if not self.is_enabled():
            return None
        try:
            content = self._chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": runtime_prompt},
                ],
                timeout_seconds=timeout_seconds,
            )
            payload = self._parse_json_block(content)
            if isinstance(payload, (dict, list)):
                return payload
        except Exception:  # noqa: BLE001
            return None
        return None

    def generate_document_qa_pairs(
        self,
        file_name: str,
        chunks: list[dict[str, Any]],
        max_pairs: int = 12,
    ) -> list[dict[str, Any]]:
        if not self.is_enabled() or not chunks:
            return []

        candidate_chunks = [
            {
                "chunk_index": int(((chunk.get("source_meta") or {}).get("chunk_index")) or index),
                "title": str(chunk.get("title") or ""),
                "content": str(chunk.get("content") or "").strip()[:1200],
            }
            for index, chunk in enumerate(chunks, start=1)
            if str(chunk.get("content") or "").strip()
        ][: max(max_pairs * 2, 8)]
        if not candidate_chunks:
            return []

        prompt = (
            "请根据给定文档片段，生成适合知识库入库的问答对。"
            "要求：\n"
            "1. 问题必须具体、自然，避免过于泛化。\n"
            "2. 答案必须严格依据文档片段，不要编造文档中没有的信息。\n"
            "3. 每条问答必须绑定一个最相关的 chunk_index。\n"
            "4. 关键词保留 1 到 5 个短词。\n"
            "5. 最多输出指定数量。\n"
            "6. 只输出 JSON，不要解释。\n\n"
            f"文档名：{file_name}\n"
            f"最多生成：{max_pairs} 条\n\n"
            f"文档片段：\n{json.dumps(candidate_chunks, ensure_ascii=False, indent=2)}\n\n"
            '输出格式：{"pairs":[{"question":"...","answer":"...","keywords":["..."],"chunk_index":1}]}'
        )

        try:
            content = self._chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个严谨的文档问答抽取助手，只能输出合法 JSON。"},
                    {"role": "user", "content": prompt},
                ]
            )
            payload = self._parse_json_block(content)
            pairs = payload.get("pairs") if isinstance(payload, dict) else None
            if not isinstance(pairs, list):
                return []

            normalized: list[dict[str, Any]] = []
            seen_questions: set[str] = set()
            for item in pairs:
                if not isinstance(item, dict):
                    continue
                question = " ".join(str(item.get("question") or "").split()).strip()
                answer = str(item.get("answer") or "").strip()
                if not question or not answer or question in seen_questions:
                    continue
                chunk_index = int(item.get("chunk_index") or 0)
                keywords = [
                    str(keyword).strip()
                    for keyword in (item.get("keywords") or [])
                    if str(keyword).strip()
                ][:5]
                normalized.append(
                    {
                        "question": question,
                        "answer": answer,
                        "keywords": keywords,
                        "chunk_index": chunk_index,
                    }
                )
                seen_questions.add(question)
                if len(normalized) >= max_pairs:
                    break
            return normalized
        except Exception:  # noqa: BLE001
            return []

    async def stream_answer(
        self,
        system_prompt: str,
        runtime_prompt: str,
        reply_locale: str = "zh-Hant",
    ) -> AsyncIterator[str]:
        if not self.is_enabled():
            raise RuntimeError("deepseek_not_configured")

        payload = {
            "model": settings.DEEPSEEK_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": runtime_prompt},
            ],
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{settings.DEEPSEEK_API_BASE_URL.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient(timeout=settings.DEEPSEEK_TIMEOUT_SECONDS) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    delta = (((chunk.get("choices") or [{}])[0]).get("delta") or {}).get("content")
                    if delta:
                        yield format_reply_text(str(delta), reply_locale)

    def _chat_completion(self, messages: list[dict[str, str]], timeout_seconds: int | None = None) -> str:
        payload = {
            "model": settings.DEEPSEEK_CHAT_MODEL,
            "messages": messages,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }
        url = f"{settings.DEEPSEEK_API_BASE_URL.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=timeout_seconds or settings.DEEPSEEK_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        return str((((result.get("choices") or [{}])[0]).get("message") or {}).get("content") or "").strip()

    def _history_text(self, history: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for item in history:
            query = item.get("query") or ""
            answer = item.get("answer") or ""
            if query:
                lines.append(f"用户：{query}")
            if answer:
                lines.append(f"助手：{answer}")
        return "\n".join(lines)

    def _references_text(self, hits: list[dict[str, Any]]) -> str:
        return "\n\n".join(
            f"[{index}] 标题：{item.get('title')}\n摘要：{item.get('snippet')}"
            for index, item in enumerate(hits, start=1)
        )

    def _parse_json_block(self, content: str) -> Any:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        start_positions = [position for position in [cleaned.find("{"), cleaned.find("[")] if position >= 0]
        if not start_positions:
            raise ValueError("json_not_found")
        start = min(start_positions)
        end_object = cleaned.rfind("}")
        end_array = cleaned.rfind("]")
        end = max(end_object, end_array)
        if end < start:
            raise ValueError("json_not_found")
        return json.loads(cleaned[start : end + 1])
