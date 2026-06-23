from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.deepseek_service import DeepSeekService
from app.services.document_parser import ParsedDocument


@dataclass
class TableColumnDef:
    key: str
    label: str
    label_en: str | None = None
    unit: str | None = None
    definition: str | None = None


@dataclass
class TableFootnote:
    marker: str
    meaning: str


@dataclass
class TableRow:
    row_label: str
    group_path: list[str]
    aliases: list[str]
    cells: dict[str, Any]
    source_quote: str | None = None


@dataclass
class ExtractedTable:
    table_title: str
    page_start: int
    page_end: int
    column_defs: list[TableColumnDef]
    footnotes: list[TableFootnote]
    rows: list[TableRow]


@dataclass
class TableKnowledgeDraft:
    title: str
    content: str
    keywords: list[str]
    source_meta: dict[str, Any]


@dataclass
class TableAwareIngestionResult:
    tables: list[ExtractedTable]
    row_drafts: list[TableKnowledgeDraft]
    meta_drafts: list[TableKnowledgeDraft]
    validation_queries: list[str]
    skipped_pages: list[int]

    def summary(self) -> dict[str, Any]:
        return {
            "table_count": len(self.tables),
            "row_item_count": len(self.row_drafts),
            "meta_item_count": len(self.meta_drafts),
            "validation_query_count": len(self.validation_queries),
            "skipped_pages": self.skipped_pages,
        }


class TableAwareIngestionService:
    TABLE_SCORE_PATTERNS = (
        r"\btable\b",
        r"^表\s*\d+",
        r"candidate",
        r"category",
        r"subject",
        r"statistics",
        r"百分率",
        r"百分比",
        r"考生類別",
        r"人數",
        r"科目",
        r"達標",
        r"總數",
    )
    PERCENT_LIKE_PATTERN = re.compile(r"\d+(?:\.\d+)?%")
    NUMBER_LIKE_PATTERN = re.compile(r"\d[\d,\s]*(?:\.\d+)?")

    def __init__(self) -> None:
        self.deepseek_service = DeepSeekService()

    def supports(self, document: ParsedDocument, file_name: str, file_ext: str | None) -> bool:
        if not settings.FILE_TABLE_EXTRACTION_ENABLED:
            return False
        normalized_ext = (file_ext or Path(file_name).suffix.lstrip(".")).lower()
        if normalized_ext != "pdf":
            return False
        if not document.blocks:
            return False
        return any(self._score_page_text(text) >= settings.FILE_TABLE_EXTRACTION_MIN_PAGE_SCORE for _, text in self._iter_page_texts(document))

    def extract(
        self,
        document: ParsedDocument,
        file_name: str,
        schema_hint: str | None = None,
    ) -> TableAwareIngestionResult:
        if not self.deepseek_service.is_enabled():
            return TableAwareIngestionResult([], [], [], [], [])

        extracted_tables: list[ExtractedTable] = []
        skipped_pages: list[int] = []
        max_pages = max(int(settings.FILE_TABLE_EXTRACTION_MAX_PAGES or 1), 1)

        for page_index, (page_no, page_text) in enumerate(self._iter_page_texts(document), start=1):
            if page_index > max_pages:
                skipped_pages.append(page_no)
                continue
            if self._score_page_text(page_text) < settings.FILE_TABLE_EXTRACTION_MIN_PAGE_SCORE:
                skipped_pages.append(page_no)
                continue
            tables = self._extract_page_tables(file_name=file_name, page_no=page_no, page_text=page_text, schema_hint=schema_hint)
            extracted_tables.extend(tables)

        row_drafts, meta_drafts = self._build_knowledge_drafts(file_name=file_name, tables=extracted_tables)
        validation_queries = self._build_validation_queries(row_drafts=row_drafts, meta_drafts=meta_drafts)
        return TableAwareIngestionResult(
            tables=extracted_tables,
            row_drafts=row_drafts,
            meta_drafts=meta_drafts,
            validation_queries=validation_queries,
            skipped_pages=sorted(set(skipped_pages)),
        )

    def _iter_page_texts(self, document: ParsedDocument) -> list[tuple[int, str]]:
        page_map: dict[int, list[str]] = {}
        for block in document.blocks:
            page_no = int(block.page_no or 1)
            text = str(block.text or "").strip()
            if not text:
                continue
            page_map.setdefault(page_no, []).append(text)
        if not page_map and document.text.strip():
            return [(1, document.text.strip())]
        return [(page_no, "\n".join(parts).strip()) for page_no, parts in sorted(page_map.items())]

    def _score_page_text(self, page_text: str) -> int:
        lines = [line.strip() for line in page_text.splitlines() if line.strip()]
        if not lines:
            return 0
        digit_lines = sum(1 for line in lines if self.NUMBER_LIKE_PATTERN.search(line))
        score = 0
        if digit_lines >= 8:
            score += 2
        if digit_lines >= 14:
            score += 1
        if self.PERCENT_LIKE_PATTERN.search(page_text):
            score += 2
        for pattern in self.TABLE_SCORE_PATTERNS:
            if re.search(pattern, page_text, re.IGNORECASE | re.MULTILINE):
                score += 1
        if any(len(re.findall(r"\s{2,}", line)) >= 1 for line in lines):
            score += 1
        return score

    def _extract_page_tables(
        self,
        file_name: str,
        page_no: int,
        page_text: str,
        schema_hint: str | None,
    ) -> list[ExtractedTable]:
        runtime_prompt = self._build_extraction_prompt(file_name=file_name, page_no=page_no, page_text=page_text, schema_hint=schema_hint)
        payload = self.deepseek_service.extract_structured_json(
            system_prompt="你是一个严谨的 PDF 表格结构化抽取助手，只能输出合法 JSON。",
            runtime_prompt=runtime_prompt,
            timeout_seconds=settings.FILE_TABLE_EXTRACTION_TIMEOUT_SECONDS,
        )
        if not isinstance(payload, dict):
            return []
        tables = payload.get("tables")
        if not isinstance(tables, list):
            return []
        return self._normalize_tables(tables=tables, page_no=page_no)

    def _build_extraction_prompt(
        self,
        file_name: str,
        page_no: int,
        page_text: str,
        schema_hint: str | None,
    ) -> str:
        schema_section = (
            f"补充 schema 提示：{schema_hint}\n\n"
            if schema_hint and schema_hint.strip()
            else ""
        )
        return (
            "请从下面这一个 PDF 页面文本中识别表格并输出结构化 JSON。\n"
            "要求：\n"
            "1. 只提取表格，不要把普通说明段落误当成表格行。\n"
            "2. 如果页面上有多张表，请输出多张表。\n"
            "3. 如果表格是中英双语并列，优先保留繁体中文为主标签，英文可放进 label_en 或 aliases。\n"
            "4. 对跨行分类、分组标题、合并单元格要展开到具体数据行。\n"
            "5. row_label 必须是具体行名，不要只写“日校考生”“全體考生”这种过于抽象的值；若需要，请通过 group_path 保留上层分类。\n"
            "6. cells 的 key 必须对应 column_defs 中的 key。\n"
            "7. 数字尽量输出数字；百分比去掉 % 后输出数字。\n"
            "8. footnotes 只保留真正的脚注或统计口径说明。\n"
            "9. 如果这一页没有可用表格，输出 {\"tables\":[]}。\n"
            "10. 只输出 JSON，不要解释。\n\n"
            f"{schema_section}"
            f"文件名：{Path(file_name).name}\n"
            f"页码：{page_no}\n\n"
            "输出格式：\n"
            "{\n"
            '  "tables": [\n'
            "    {\n"
            '      "table_title": "...",\n'
            '      "page_start": 1,\n'
            '      "page_end": 1,\n'
            '      "column_defs": [\n'
            '        {"key":"...", "label":"...", "label_en":"...", "unit":"...", "definition":"..."}\n'
            "      ],\n"
            '      "footnotes": [{"marker":"*", "meaning":"..."}],\n'
            '      "rows": [\n'
            '        {"group_path":["..."], "row_label":"...", "aliases":["..."], "cells":{"...":123}, "source_quote":"..."}\n'
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"页面文本：\n{page_text}"
        )

    def _normalize_tables(self, tables: list[Any], page_no: int) -> list[ExtractedTable]:
        normalized_tables: list[ExtractedTable] = []
        for index, raw_table in enumerate(tables, start=1):
            if not isinstance(raw_table, dict):
                continue
            table_title = (
                " ".join(str(raw_table.get("table_title") or raw_table.get("title") or "").split()).strip()
                or f"第{page_no}頁表格 {index}"
            )
            raw_rows = raw_table.get("rows")
            if not isinstance(raw_rows, list):
                raw_rows = raw_table.get("data")
            column_defs = self._normalize_column_defs(raw_table.get("column_defs"))
            if not column_defs:
                column_defs = self._infer_column_defs(raw_rows)
            rows = self._normalize_rows(raw_rows, column_defs)
            if not rows:
                continue
            footnotes = self._normalize_footnotes(raw_table.get("footnotes"))
            page_start = self._normalize_int(raw_table.get("page_start"), default=page_no)
            page_end = self._normalize_int(raw_table.get("page_end"), default=page_no)
            normalized_tables.append(
                ExtractedTable(
                    table_title=table_title,
                    page_start=page_start,
                    page_end=max(page_end, page_start),
                    column_defs=column_defs,
                    footnotes=footnotes,
                    rows=rows,
                )
            )
        return normalized_tables

    def _normalize_column_defs(self, column_defs: Any) -> list[TableColumnDef]:
        normalized: list[TableColumnDef] = []
        seen_keys: set[str] = set()
        if not isinstance(column_defs, list):
            return normalized
        for index, raw in enumerate(column_defs, start=1):
            if not isinstance(raw, dict):
                continue
            label = " ".join(str(raw.get("label") or raw.get("label_zh") or "").split()).strip()
            if not label:
                continue
            raw_key = " ".join(str(raw.get("key") or "").split()).strip().lower()
            key = self._slugify_key(raw_key or label)
            if not key or key in seen_keys:
                key = f"col_{index}"
            seen_keys.add(key)
            normalized.append(
                TableColumnDef(
                    key=key,
                    label=label,
                    label_en=" ".join(str(raw.get("label_en") or "").split()).strip() or None,
                    unit=" ".join(str(raw.get("unit") or "").split()).strip() or None,
                    definition=" ".join(str(raw.get("definition") or "").split()).strip() or None,
                )
            )
        return normalized

    def _normalize_rows(self, rows: Any, column_defs: list[TableColumnDef]) -> list[TableRow]:
        if not isinstance(rows, list):
            return []
        column_keys = {column.key for column in column_defs}
        column_label_map = {
            self._slugify_key(column.label): column.key
            for column in column_defs
        }
        normalized_rows: list[TableRow] = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            if "row_label" not in raw and "cells" not in raw:
                heuristic_row = self._normalize_heuristic_row(raw=raw, column_keys=column_keys, column_label_map=column_label_map)
                if heuristic_row is not None:
                    normalized_rows.append(heuristic_row)
                continue
            row_label = " ".join(str(raw.get("row_label") or "").split()).strip()
            if not row_label:
                continue
            group_path = [
                " ".join(str(value).split()).strip()
                for value in (raw.get("group_path") or [])
                if " ".join(str(value).split()).strip()
            ]
            aliases = [
                " ".join(str(value).split()).strip()
                for value in (raw.get("aliases") or [])
                if " ".join(str(value).split()).strip()
            ]
            raw_cells = raw.get("cells")
            if not isinstance(raw_cells, dict):
                continue
            normalized_cells: dict[str, Any] = {}
            for key, value in raw_cells.items():
                cell_key = self._slugify_key(str(key))
                if not cell_key:
                    continue
                if column_keys and cell_key not in column_keys:
                    continue
                normalized_value = self._normalize_cell_value(value)
                if normalized_value in ("", None, []):
                    continue
                normalized_cells[cell_key] = normalized_value
            if not normalized_cells:
                continue
            source_quote = " ".join(str(raw.get("source_quote") or "").split()).strip() or None
            normalized_rows.append(
                TableRow(
                    row_label=row_label,
                    group_path=group_path,
                    aliases=aliases,
                    cells=normalized_cells,
                    source_quote=source_quote,
                )
            )
        return normalized_rows

    def _infer_column_defs(self, rows: Any) -> list[TableColumnDef]:
        if not isinstance(rows, list):
            return []
        labels: list[str] = []
        seen: set[str] = set()
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            for key in raw.keys():
                label = " ".join(str(key or "").split()).strip()
                if not label or label in seen:
                    continue
                seen.add(label)
                labels.append(label)
        inferred: list[TableColumnDef] = []
        for index, label in enumerate(labels, start=1):
            key = self._slugify_key(label) or f"col_{index}"
            unit = "%" if "%" in label else None
            inferred.append(TableColumnDef(key=key, label=label, unit=unit))
        return inferred

    def _normalize_footnotes(self, footnotes: Any) -> list[TableFootnote]:
        if not isinstance(footnotes, list):
            return []
        normalized: list[TableFootnote] = []
        for raw in footnotes:
            if not isinstance(raw, dict):
                continue
            marker = " ".join(str(raw.get("marker") or "").split()).strip()
            meaning = " ".join(str(raw.get("meaning") or "").split()).strip()
            if not marker or not meaning:
                continue
            normalized.append(TableFootnote(marker=marker, meaning=meaning))
        return normalized

    def _normalize_heuristic_row(
        self,
        raw: dict[str, Any],
        column_keys: set[str],
        column_label_map: dict[str, str],
    ) -> TableRow | None:
        text_fields: list[tuple[str, str]] = []
        normalized_cells: dict[str, Any] = {}
        for raw_key, raw_value in raw.items():
            label = " ".join(str(raw_key or "").split()).strip()
            if not label:
                continue
            key = column_label_map.get(self._slugify_key(label)) or self._slugify_key(label)
            if column_keys and key not in column_keys:
                continue
            normalized_value = self._normalize_cell_value(raw_value)
            if normalized_value in ("", None, []):
                continue
            normalized_cells[key] = normalized_value
            if isinstance(normalized_value, str):
                text_fields.append((label, normalized_value))

        if not normalized_cells:
            return None

        row_label = ""
        group_path: list[str] = []
        preferred_patterns = (
            "candidate category",
            "考生類別",
            "subject",
            "科目",
            "item",
            "項目",
        )
        for label, text in text_fields:
            lowered_label = label.lower()
            if any(pattern in lowered_label for pattern in preferred_patterns):
                row_label = text
                break
        if not row_label and text_fields:
            row_label = text_fields[-1][1]
        if not row_label:
            row_label = "資料列"
        for _, text in text_fields:
            if text == row_label:
                continue
            group_path.append(text)
        return TableRow(
            row_label=row_label,
            group_path=group_path[:3],
            aliases=[],
            cells=normalized_cells,
            source_quote=None,
        )

    def _build_knowledge_drafts(
        self,
        file_name: str,
        tables: list[ExtractedTable],
    ) -> tuple[list[TableKnowledgeDraft], list[TableKnowledgeDraft]]:
        row_drafts: list[TableKnowledgeDraft] = []
        meta_drafts: list[TableKnowledgeDraft] = []
        document_label = Path(file_name).stem

        for table_index, table in enumerate(tables, start=1):
            column_map = {column.key: column for column in table.column_defs}
            for row_index, row in enumerate(table.rows, start=1):
                title = f"《{table.table_title}》中「{self._build_row_display_label(row)}」的表格數據是什麼？"
                content_lines = [f"此記錄來自表「{table.table_title}」。"]
                if row.group_path:
                    content_lines.append(f"分組路徑為「{' > '.join(row.group_path)}」。")
                content_lines.append(f"行項目為「{row.row_label}」。")
                for column in table.column_defs:
                    if column.key not in row.cells:
                        continue
                    content_lines.append(self._describe_cell(column, row.cells[column.key]))
                if row.aliases:
                    content_lines.append(f"可對應別名：{'、'.join(row.aliases[:4])}。")
                if row.source_quote:
                    content_lines.append(f"原文片段：{row.source_quote}")
                keywords = self._dedupe_keywords(
                    [
                        document_label,
                        table.table_title,
                        row.row_label,
                        *row.group_path,
                        *row.aliases,
                        *(column.label for column in table.column_defs),
                    ]
                )
                row_drafts.append(
                    TableKnowledgeDraft(
                        title=title,
                        content="".join(content_lines),
                        keywords=keywords[:12],
                        source_meta={
                            "ingest_kind": "structured_table_row",
                            "table_kind": self._slugify_key(table.table_title) or f"table_{table_index}",
                            "table_title": table.table_title,
                            "page_start": table.page_start,
                            "page_end": table.page_end,
                            "row_index": row_index,
                            "group_path": row.group_path,
                            "row_label": row.row_label,
                            "row_aliases": row.aliases,
                            "metric_map": row.cells,
                            "source_quote": row.source_quote,
                        },
                    )
                )

            for column in table.column_defs:
                label = column.label
                meta_title = f"「{label}」在這個表裏是什麼意思？"
                definition = column.definition or self._build_column_definition_fallback(column)
                meta_keywords = self._dedupe_keywords(
                    [document_label, table.table_title, label, column.label_en or "", "意思", "代表", "表頭", "欄位"]
                )
                meta_drafts.append(
                    TableKnowledgeDraft(
                        title=meta_title,
                        content=f"在表「{table.table_title}」中，「{label}」表示{definition}。",
                        keywords=meta_keywords[:10],
                        source_meta={
                            "ingest_kind": "structured_table_meta",
                            "meta_kind": "column_definition",
                            "table_kind": self._slugify_key(table.table_title) or f"table_{table_index}",
                            "table_title": table.table_title,
                            "page_start": table.page_start,
                            "page_end": table.page_end,
                            "column_key": column.key,
                            "column_label": column.label,
                            "column_label_en": column.label_en,
                            "definition": definition,
                        },
                    )
                )

            for footnote in table.footnotes:
                marker_title = f"這個表裏「{footnote.marker}」代表什麼？"
                footnote_keywords = self._dedupe_keywords(
                    [document_label, table.table_title, footnote.marker, "腳註", "註", "備註", "代表", "意思"]
                )
                meta_drafts.append(
                    TableKnowledgeDraft(
                        title=marker_title,
                        content=f"在表「{table.table_title}」中，標記「{footnote.marker}」表示：{footnote.meaning}",
                        keywords=footnote_keywords[:10],
                        source_meta={
                            "ingest_kind": "structured_table_meta",
                            "meta_kind": "footnote_definition",
                            "table_kind": self._slugify_key(table.table_title) or f"table_{table_index}",
                            "table_title": table.table_title,
                            "page_start": table.page_start,
                            "page_end": table.page_end,
                            "footnote_marker": footnote.marker,
                            "meaning": footnote.meaning,
                        },
                    )
                )

        return row_drafts, meta_drafts

    def _build_validation_queries(
        self,
        row_drafts: list[TableKnowledgeDraft],
        meta_drafts: list[TableKnowledgeDraft],
    ) -> list[str]:
        queries: list[str] = []
        sample_size = max(int(settings.FILE_TABLE_VALIDATION_SAMPLE_SIZE or 1), 1)
        for draft in row_drafts[:sample_size]:
            queries.append(draft.title)
        for draft in meta_drafts[: max(1, sample_size // 2)]:
            queries.append(draft.title)
        return queries[: sample_size + max(1, sample_size // 2)]

    def _build_row_display_label(self, row: TableRow) -> str:
        if not row.group_path:
            return row.row_label
        tail = row.group_path[-1]
        if row.row_label == tail:
            return row.row_label
        return f"{tail}－{row.row_label}"

    def _describe_cell(self, column: TableColumnDef, value: Any) -> str:
        label = column.label
        formatted = self._format_cell_value(value=value, unit=column.unit, label=label)
        return f"「{label}」為 {formatted}。"

    def _format_cell_value(self, value: Any, unit: str | None, label: str) -> str:
        if isinstance(value, bool):
            return "是" if value else "否"
        if isinstance(value, (int, float)):
            number_text = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
            normalized_unit = (unit or "").strip()
            if normalized_unit in {"%", "percent", "percentage"} or "%" in label:
                return f"{number_text}%"
            return number_text
        text = " ".join(str(value).split()).strip()
        return text

    def _build_column_definition_fallback(self, column: TableColumnDef) -> str:
        if column.unit and column.unit.strip() in {"%", "percent", "percentage"}:
            return f"该欄位的百分比數值"
        if column.label_en:
            return f"欄位「{column.label}」對應的統計值（英文對照：{column.label_en}）"
        return f"欄位「{column.label}」對應的統計值"

    def _normalize_cell_value(self, value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return ""
        number_like = text.replace(",", "")
        if re.fullmatch(r"-?\d+", number_like):
            return int(number_like)
        if re.fullmatch(r"-?\d+\.\d+", number_like):
            return float(number_like)
        return text

    def _normalize_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _slugify_key(self, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            return ""
        normalized = normalized.replace("／", "/").replace("（", "(").replace("）", ")")
        normalized = re.sub(r"[%]+", " pct ", normalized)
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        return normalized

    def _dedupe_keywords(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = " ".join(str(value or "").split()).strip()
            if not cleaned:
                continue
            lowered = cleaned.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            result.append(cleaned)
        return result
