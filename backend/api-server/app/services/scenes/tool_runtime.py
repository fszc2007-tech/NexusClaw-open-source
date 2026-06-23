from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
import re
import shutil
import smtplib
from typing import Any

import httpx
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, BooleanObject, NameObject, TextStringObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont

from app.core.config import ensure_storage_root, settings
from app.models.scene import SceneCase, SceneEvent
from app.services.scenes.address_analysis_service import AddressAnalysisService
from app.services.scenes.rules_service import SceneRulesService


class SceneToolRuntime:
    OVERLAY_FONT_NAME = "GZT-CJK-Overlay"
    OVERLAY_FONT_CANDIDATES = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]

    def __init__(self, db: Session, rules_service: SceneRulesService | None = None) -> None:
        self.db = db
        self.rules_service = rules_service or SceneRulesService()
        self.address_analysis_service = AddressAnalysisService()

    def write_event(
        self,
        case: SceneCase,
        event_type: str,
        actor_type: str,
        request_json: dict[str, Any] | None = None,
        result_json: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> None:
        self.db.add(
            SceneEvent(
                case_id=case.id,
                event_type=event_type,
                actor_type=actor_type,
                request_json=request_json or {},
                result_json=result_json or {},
                trace_id=trace_id,
            )
        )

    def generate_pdf(self, case: SceneCase, form_no: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            case_root = ensure_storage_root() / "scene_cases" / case.case_code
            case_root.mkdir(parents=True, exist_ok=True)
            preview_path = case_root / f"{form_no.lower()}_preview.pdf"
            final_path = case_root / f"{form_no.lower()}_final.pdf"

            mapping = self.rules_service.get_mapping(form_no)
            template_path = self._resolve_template_path(form_no)
            kind = mapping.get("kind")

            if kind == "acroform":
                self._generate_ir1249_pdf(template_path, mapping, payload, preview_path, final_path)
            elif kind == "overlay":
                self._generate_overlay_pdf(template_path, mapping, payload, preview_path, final_path)
            else:
                raise ValueError("PDF_GENERATION_FAILED")

            return {
                "preview_path": str(preview_path),
                "final_path": str(final_path),
            }
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ValueError("PDF_GENERATION_FAILED") from exc

    def preview_mail(self, route_rules: dict[str, Any], payload: dict[str, Any], pdf_artifacts: dict[str, Any]) -> dict[str, Any]:
        reference = payload.get("reference_id") or payload.get("business_registration_no") or ""
        masked_reference = f"{reference[:4]}***" if reference else ""
        phone = payload.get("daytime_phone") or payload.get("telephone_no") or ""
        signer_name = payload.get("signer_name") or ""
        full_name = payload.get("full_name") or payload.get("business_name") or signer_name
        effective_date = payload.get("effective_date") or ""
        subject = f"{route_rules['form_no']} - Address Change - {full_name or 'Applicant'}"
        body = (
            "Dear Inland Revenue Department,\n\n"
            f"Please find attached the completed {route_rules['form_no']}.\n\n"
            f"Applicant Name: {full_name}\n"
            f"HKID / Reference: {masked_reference}\n"
            f"Effective Date: {effective_date}\n"
            f"Day-time Contact Telephone No.: {phone}\n\n"
            "Please contact me if further information is required.\n\n"
            f"Regards,\n{signer_name or full_name}"
        )
        return {
            "to": route_rules.get("submission_email"),
            "subject": subject,
            "body": body,
            "attachment_path": pdf_artifacts.get("final_path"),
        }

    def send_mail(self, mail_preview: dict[str, Any]) -> dict[str, Any]:
        if settings.SCENE_MAIL_DELIVERY_MODE != "send_enabled":
            raise ValueError("MAIL_SEND_BLOCKED")

        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise ValueError("MAIL_SEND_FAILED")

        message = EmailMessage()
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = mail_preview["to"]
        message["Subject"] = mail_preview["subject"]
        message.set_content(mail_preview["body"])

        attachment_path = mail_preview.get("attachment_path")
        if attachment_path and Path(attachment_path).exists():
            attachment_bytes = Path(attachment_path).read_bytes()
            message.add_attachment(
                attachment_bytes,
                maintype="application",
                subtype="pdf",
                filename=Path(attachment_path).name,
            )

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as client:
            if settings.SMTP_USE_TLS:
                client.starttls()
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            client.send_message(message)

        return {
            "status": "sent",
            "to": mail_preview["to"],
            "subject": mail_preview["subject"],
            "sent_at": datetime.utcnow().isoformat() + "Z",
        }

    def _resolve_template_path(self, form_no: str) -> Path:
        template_root = Path(settings.SCENE_TEMPLATE_ROOT)
        if not template_root.is_absolute():
            template_root = Path.cwd() / template_root
        template_root.mkdir(parents=True, exist_ok=True)

        if form_no == "IR1249":
            target_path = template_root / "ir1249.pdf"
            source_url = settings.SCENE_IR1249_TEMPLATE_URL
            fallback_candidates = [
                Path("/tmp/ir1249.pdf"),
            ]
        elif form_no == "IRC3111A":
            target_path = template_root / "irc3111a_normal.pdf"
            source_url = settings.SCENE_IRC3111A_TEMPLATE_URL
            fallback_candidates = [
                Path("/tmp/irc3111a_normal.pdf"),
            ]
        else:
            raise ValueError("PDF_GENERATION_FAILED")

        if not target_path.exists():
            copied = False
            for candidate in fallback_candidates:
                if candidate.exists():
                    shutil.copyfile(candidate, target_path)
                    copied = True
                    break
            if not copied:
                response = httpx.get(
                    source_url,
                    timeout=30,
                    follow_redirects=True,
                    headers={"User-Agent": "nexusclaw-scene-runtime/1.0"},
                )
                response.raise_for_status()
                target_path.write_bytes(response.content)
        return target_path

    def _generate_ir1249_pdf(
        self,
        template_path: Path,
        mapping: dict[str, Any],
        payload: dict[str, Any],
        preview_path: Path,
        final_path: Path,
    ) -> None:
        reader = PdfReader(str(template_path))
        writer = PdfWriter()
        writer.append(reader)

        acro = writer._root_object.get("/AcroForm")
        if acro:
            acro.get_object().update({NameObject("/NeedAppearances"): BooleanObject(True)})

        text_values, checkbox_values = self._build_ir1249_values(mapping, payload)
        for page in writer.pages:
            annots_ref = page.get("/Annots")
            annots = annots_ref.get_object() if annots_ref else []
            for ann_ref in annots:
                annotation = ann_ref.get_object()
                field_name = annotation.get("/T")
                if field_name in text_values:
                    text_value = text_values[field_name]
                    annotation.update({NameObject("/V"): TextStringObject(text_value)})
                    parent = annotation.get("/Parent")
                    if parent:
                        parent.get_object().update({NameObject("/V"): TextStringObject(text_value)})
                if field_name in checkbox_values:
                    checkbox_value = NameObject(checkbox_values[field_name])
                    annotation.update({NameObject("/V"): checkbox_value, NameObject("/AS"): checkbox_value})
                    parent = annotation.get("/Parent")
                    if parent:
                        parent.get_object().update({NameObject("/V"): checkbox_value})

        address_field_names = set(mapping["acroform"]["address_fields"].values())
        overlay_text_values = {
            field_name: text_value
            for field_name, text_value in text_values.items()
            if field_name not in address_field_names and self._needs_ir1249_text_overlay(text_value)
        }
        self._remove_widget_annotations(writer, address_field_names | set(overlay_text_values.keys()))
        address_overlay_ops = self._build_ir1249_address_overlay_ops(reader, mapping, payload)
        generic_overlay_ops = self._build_ir1249_text_overlay_ops(reader, overlay_text_values)
        overlay_ops = [*address_overlay_ops, *generic_overlay_ops]
        if overlay_ops:
            overlay_pdf_path = preview_path.with_suffix(".overlay.pdf")
            first_page = reader.pages[0]
            self._write_image_overlay_pdf(
                overlay_pdf_path,
                float(first_page.mediabox.width),
                float(first_page.mediabox.height),
                overlay_ops,
            )
            overlay_reader = PdfReader(str(overlay_pdf_path))
            writer.pages[0].merge_page(overlay_reader.pages[0])
            overlay_pdf_path.unlink(missing_ok=True)

        with preview_path.open("wb") as file_obj:
            writer.write(file_obj)
        shutil.copyfile(preview_path, final_path)

    def _generate_overlay_pdf(
        self,
        template_path: Path,
        mapping: dict[str, Any],
        payload: dict[str, Any],
        preview_path: Path,
        final_path: Path,
    ) -> None:
        reader = PdfReader(str(template_path))
        page = reader.pages[0]
        overlay_config = mapping["overlay"]
        draw_ops = self._build_irc3111a_draw_ops(payload, overlay_config)

        overlay_pdf_path = preview_path.with_suffix(".overlay.pdf")
        self._write_overlay_pdf(
            overlay_pdf_path,
            float(page.mediabox.width),
            float(page.mediabox.height),
            draw_ops,
        )
        overlay_reader = PdfReader(str(overlay_pdf_path))

        writer = PdfWriter()
        for index, src_page in enumerate(reader.pages):
            page_obj = src_page
            if index == overlay_config.get("page_index", 0):
                page_obj.merge_page(overlay_reader.pages[0])
            writer.add_page(page_obj)

        with preview_path.open("wb") as file_obj:
            writer.write(file_obj)
        shutil.copyfile(preview_path, final_path)
        overlay_pdf_path.unlink(missing_ok=True)

    def _build_ir1249_values(self, mapping: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
        acroform = mapping["acroform"]
        text_values: dict[str, str] = {}
        checkbox_values: dict[str, str] = {}

        date_parts = self._parse_date_parts(payload.get("effective_date"))
        text_values[acroform["date_fields"]["day"]] = date_parts["day"]
        text_values[acroform["date_fields"]["month"]] = date_parts["month"]
        text_values[acroform["date_fields"]["year"]] = date_parts["year"]

        address_parts = self._build_ir1249_address_parts(payload)
        for key, field_name in acroform["address_fields"].items():
            text_values[field_name] = address_parts.get(key, "")

        reference_parts = self._split_reference_id(payload.get("reference_id", ""))
        if reference_parts["kind"] == "hkid":
            text_values[acroform["reference_fields"]["hkid_prefix"]] = reference_parts["prefix"]
            text_values[acroform["reference_fields"]["hkid_digits"]] = reference_parts["digits"]
            text_values[acroform["reference_fields"]["hkid_check_digit"]] = reference_parts["check_digit"]
        elif reference_parts["raw"]:
            fallback_field = (
                acroform["reference_fields"]["fallback_other_file_no"]
                if payload.get("applicant_type") in {"business owner", "employer"}
                else acroform["reference_fields"]["fallback_individual_file_no"]
            )
            text_values[fallback_field] = reference_parts["raw"]

        signer_name = payload.get("signer_name", "")
        full_name = payload.get("full_name") or signer_name
        text_values[acroform["text_fields"]["full_name"]] = full_name
        text_values[acroform["text_fields"]["signer_name"]] = signer_name
        text_values[acroform["text_fields"]["daytime_phone"]] = payload.get("daytime_phone", "")
        text_values[acroform["text_fields"]["daytime_phone_2"]] = payload.get("daytime_phone", "")
        text_values[acroform["text_fields"]["fax_no"]] = payload.get("fax_no", "")
        text_values[acroform["text_fields"]["designation"]] = payload.get("designation", "")
        today = datetime.utcnow().strftime("%Y-%m-%d")
        text_values[acroform["text_fields"]["signature_date"]] = today
        text_values[acroform["text_fields"]["signature_date_2"]] = today

        applicant_type = (payload.get("applicant_type") or "").strip()
        if applicant_type in {"salary earner", "property owner", "sole proprietor"}:
            text_values[acroform["text_fields"]["individual_name"]] = full_name
            individual_file_no = payload.get("individual_file_no") or reference_parts["raw"]
            if individual_file_no and (payload.get("individual_file_no") or reference_parts["kind"] != "hkid"):
                text_values[acroform["text_fields"]["individual_file_no"]] = individual_file_no
        if applicant_type == "property owner":
            text_values[acroform["text_fields"]["property_tax_location"]] = payload.get("property_tax_location", payload.get("new_address", ""))
            property_tax_file_no = payload.get("property_tax_file_no") or reference_parts["raw"]
            if property_tax_file_no and (payload.get("property_tax_file_no") or reference_parts["kind"] != "hkid"):
                text_values[acroform["text_fields"]["property_tax_file_no"]] = property_tax_file_no
        if applicant_type in {"sole proprietor", "business owner"}:
            text_values[acroform["text_fields"]["business_name"]] = payload.get("business_name", full_name)
            profits_tax_file_no = payload.get("profits_tax_file_no") or reference_parts["raw"]
            if profits_tax_file_no and (payload.get("profits_tax_file_no") or reference_parts["kind"] != "hkid"):
                text_values[acroform["text_fields"]["profits_tax_file_no"]] = profits_tax_file_no
        if applicant_type == "employer":
            text_values[acroform["text_fields"]["employer_name"]] = payload.get("business_name", full_name)
            employer_return_file_no = payload.get("employer_return_file_no") or reference_parts["raw"]
            if employer_return_file_no and (payload.get("employer_return_file_no") or reference_parts["kind"] != "hkid"):
                text_values[acroform["text_fields"]["employer_return_file_no"]] = employer_return_file_no

        area_key = self._resolve_area_key(payload, address_parts)
        checkbox_values[acroform["checkbox_groups"]["area"][area_key]] = "/0"

        file_type_checkbox_map = {
            "salary earner": "salary_earner",
            "property owner": "property_owner",
            "sole proprietor": "sole_proprietor",
            "business owner": "business_owner",
            "employer": "employer",
        }
        file_type_key = file_type_checkbox_map.get(applicant_type)
        if file_type_key:
            checkbox_values[acroform["checkbox_groups"]["file_type"][file_type_key]] = "/0"

        return text_values, checkbox_values

    def _build_ir1249_address_parts(self, payload: dict[str, Any]) -> dict[str, str]:
        analysis = self.address_analysis_service.analyze(
            str(payload.get("new_address") or ""),
            payload.get("address_structured"),
        )
        return dict(analysis.get("pdf_parts") or {})

    def _build_ir1249_address_overlay_ops(
        self,
        reader: PdfReader,
        mapping: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        address_parts = self._build_ir1249_address_parts(payload)
        if not any(address_parts.values()):
            return []

        field_name_by_key = mapping["acroform"]["address_fields"]
        rects = self._collect_field_rects(reader, set(field_name_by_key.values()))
        font_sizes = {
            "flat_room": 10.5,
            "block": 10.5,
            "floor": 10.5,
            "line1": 10.5,
            "line2": 10.5,
            "line3": 10.5,
        }
        ops: list[dict[str, Any]] = []
        for key, field_name in field_name_by_key.items():
            text = str(address_parts.get(key) or "").strip()
            rect = rects.get(field_name)
            if not text or not rect:
                continue
            x1, y1, x2, y2 = rect
            width = max(x2 - x1 - 4, 20)
            height = max(y2 - y1 - 2, 10)
            font_size = self._fit_font_size(text, font_sizes.get(key, 10.0), width)
            ops.append(
                {
                    "type": "rect",
                    "x": x1 + 1,
                    "y": y1 + 1,
                    "width": x2 - x1 - 2,
                    "height": y2 - y1 - 2,
                    "fill_rgb": (1, 1, 1),
                }
            )
            ops.append(
                {
                    "type": "text",
                    "text": text,
                    "x": x1 + 2,
                    "y": y1 + max((height - font_size) / 2, 1.5),
                    "font_size": font_size,
                    "box": (x1, y1, x2, y2),
                }
            )
        return ops

    def _build_ir1249_text_overlay_ops(
        self,
        reader: PdfReader,
        text_values: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not text_values:
            return []
        rects = self._collect_field_rects(reader, set(text_values.keys()))
        ops: list[dict[str, Any]] = []
        for field_name, text in text_values.items():
            rect = rects.get(field_name)
            if not rect:
                continue
            x1, y1, x2, y2 = rect
            height = max(y2 - y1 - 2, 10)
            preferred_size = min(max(height * 0.78, 8.5), 11.0)
            font_size = self._fit_font_size(str(text).strip(), preferred_size, max(x2 - x1 - 4, 20))
            ops.append(
                {
                    "type": "text",
                    "text": str(text).strip(),
                    "x": x1 + 2,
                    "y": y1 + max((height - font_size) / 2, 1.5),
                    "font_size": font_size,
                    "box": (x1, y1, x2, y2),
                }
            )
        return ops

    def _collect_field_rects(self, reader: PdfReader, field_names: set[str]) -> dict[str, tuple[float, float, float, float]]:
        rects: dict[str, tuple[float, float, float, float]] = {}
        for page in reader.pages:
            annots_ref = page.get("/Annots")
            annots = annots_ref.get_object() if annots_ref else []
            for ann_ref in annots:
                annotation = ann_ref.get_object()
                field_name = annotation.get("/T")
                rect = annotation.get("/Rect")
                if field_name not in field_names or not rect:
                    continue
                rects[str(field_name)] = tuple(float(value) for value in rect)
        return rects

    def _remove_widget_annotations(self, writer: PdfWriter, field_names: set[str]) -> None:
        for page in writer.pages:
            annots_ref = page.get("/Annots")
            annots = annots_ref.get_object() if annots_ref else None
            if annots is None:
                continue
            filtered = ArrayObject()
            changed = False
            for ann_ref in annots:
                annotation = ann_ref.get_object()
                if annotation.get("/T") in field_names:
                    changed = True
                    continue
                filtered.append(ann_ref)
            if changed:
                page[NameObject("/Annots")] = filtered

    def _needs_ir1249_text_overlay(self, text: str) -> bool:
        value = str(text or "").strip()
        if not value:
            return False
        return self._contains_cjk(value)

    def _contains_cjk(self, text: str) -> bool:
        return any(
            "\u4e00" <= char <= "\u9fff"
            or "\u3400" <= char <= "\u4dbf"
            or "\uf900" <= char <= "\ufaff"
            for char in text
        )

    def _sanitize_structured_address(self, structured: dict[str, Any], raw_address: str) -> dict[str, Any]:
        return {
            key: " ".join(str(value).strip().split())
            for key, value in structured.items()
            if isinstance(value, str) and " ".join(str(value).strip().split())
        }

    def _get_structured_address_confidence(self, payload: dict[str, Any]) -> str:
        confidence_map = payload.get("_field_confidence")
        if not isinstance(confidence_map, dict):
            return ""
        confidence = confidence_map.get("address_structured")
        if not isinstance(confidence, str):
            return ""
        return confidence.strip().lower()

    def _resolve_area_key(self, payload: dict[str, Any], address_parts: dict[str, str]) -> str:
        structured_area = str(address_parts.get("area") or "").strip().lower()
        if structured_area in {"hk", "kln", "nt", "others"}:
            return structured_area
        return self._detect_area_key(payload.get("new_address", ""))

    def _build_irc3111a_draw_ops(self, payload: dict[str, Any], overlay_config: dict[str, Any]) -> list[dict[str, Any]]:
        self._ensure_reportlab_font()
        draw_ops: list[dict[str, Any]] = []
        for field_key, spec in overlay_config["text_fields"].items():
            value = payload.get(field_key)
            if not value:
                continue
            draw_ops.extend(self._build_text_ops(str(value), spec))

        date_parts = self._parse_date_parts(payload.get("effective_date"))
        for part, spec in overlay_config["date_fields"].items():
            if date_parts.get(part):
                draw_ops.append({**spec, "text": date_parts[part]})

        draw_ops.append({**overlay_config["checkboxes"]["business_address"]})
        if payload.get("change_related_profits_tax_postal_address"):
            draw_ops.append({**overlay_config["checkboxes"]["profits_tax_postal_address"]})
        if payload.get("change_related_employer_return_postal_address"):
            draw_ops.append({**overlay_config["checkboxes"]["employer_return_postal_address"]})

        draw_ops.append(
            {
                **overlay_config["signature_date"],
                "text": datetime.utcnow().strftime("%Y-%m-%d"),
            }
        )

        return draw_ops

    def _build_text_ops(self, text: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
        max_width = spec.get("max_width")
        max_lines = spec.get("max_lines", 1)
        line_height = spec.get("line_height", spec["font_size"] + 2)
        lines = [text.strip()]
        if max_width:
            lines = self._wrap_text(text.strip(), spec["font_size"], max_width, max_lines)
        ops = []
        for index, line in enumerate(lines):
            if not line:
                continue
            ops.append(
                {
                    "x": spec["x"],
                    "y": spec["y"] - index * line_height,
                    "font_size": spec["font_size"],
                    "text": line,
                }
            )
        return ops

    def _parse_date_parts(self, value: str | None) -> dict[str, str]:
        raw = (value or "").strip()
        if not raw:
            return {"day": "", "month": "", "year": ""}

        if "下个月" in raw:
            day_match = re.search(r"(\d+)\s*号", raw)
            month = datetime.utcnow().month + 1
            year = datetime.utcnow().year
            if month > 12:
                month = 1
                year += 1
            return {"day": f"{int(day_match.group(1)):02d}" if day_match else "", "month": f"{month:02d}", "year": str(year)}

        match = re.search(r"(?P<year>\d{4})[/-](?P<month>\d{1,2})[/-](?P<day>\d{1,2})", raw)
        if match:
            return {
                "day": f"{int(match.group('day')):02d}",
                "month": f"{int(match.group('month')):02d}",
                "year": match.group("year"),
            }
        match = re.search(r"(?P<day>\d{1,2})[/-](?P<month>\d{1,2})[/-](?P<year>\d{2,4})", raw)
        if match:
            year = match.group("year")
            if len(year) == 2:
                year = f"20{year}"
            return {
                "day": f"{int(match.group('day')):02d}",
                "month": f"{int(match.group('month')):02d}",
                "year": year,
            }
        match = re.search(r"(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})", raw)
        if match:
            return {
                "day": match.group("day"),
                "month": match.group("month"),
                "year": match.group("year"),
            }
        match = re.search(r"(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日", raw)
        if match:
            return {
                "day": f"{int(match.group('day')):02d}",
                "month": f"{int(match.group('month')):02d}",
                "year": str(datetime.utcnow().year),
            }
        return {"day": "", "month": "", "year": ""}

    def _split_postal_address(self, value: str) -> dict[str, str]:
        normalized = re.sub(r"[\r\n]+", " ", value.strip())
        normalized = re.sub(r"\s+", " ", normalized).strip(" ,，;；")
        working = normalized

        hk_compact_components, working = self._extract_hk_compact_unit(working)
        flat_room = hk_compact_components.get("flat_room", "")
        block = hk_compact_components.get("block", "")
        floor = hk_compact_components.get("floor", "")

        if not flat_room:
            flat_room, working = self._extract_address_component(
                working,
                [
                    r"\b(?:FLAT|ROOM|UNIT)\s*[A-Z0-9/-]+\b",
                    r"[A-Z0-9/-]+\s*(?:室|房)\b",
                ],
            )
        if not floor:
            floor, working = self._extract_address_component(
                working,
                [
                    r"\b(?:G/F|LG/F|UG/F)\b",
                    r"\b\d+\s*(?:/F|FLOOR|F)\b",
                    r"\d+\s*(?:樓|楼)\b",
                ],
            )
        if not block:
            block, working = self._extract_address_component(
                working,
                [
                    r"\b(?:BLOCK|TOWER)\s*[A-Z0-9-]+\b",
                    r"[A-Z0-9-]+\s*(?:座|棟|栋)\b",
                ],
            )

        working = self._strip_area_prefix(working)
        district, working = self._extract_district(working)
        building, working = self._extract_building_name(working)
        street = self._cleanup_address_fragment(working)

        if not building and not district and street:
            segments = [item.strip() for item in re.split(r"[，,;；]+", street) if item.strip()]
            if len(segments) >= 2:
                building = self._cleanup_address_fragment(segments[0])
                street = self._cleanup_address_fragment(" ".join(segments[1:]))

        return {
            "flat_room": flat_room[:80],
            "block": block[:80],
            "floor": floor[:80],
            "line1": building[:80],
            "line2": street[:80],
            "line3": district[:80],
        }

    def _extract_hk_compact_unit(self, text: str) -> tuple[dict[str, str], str]:
        compact_patterns = [
            re.compile(
                r"(?P<full>(?:第)?(?P<block>[A-Z]|\d{1,2})\s*座\s*(?P<floor>\d{1,2})\s*(?:樓|楼|F)?\s*(?P<flat>[A-Z]\d?)\s*(?:室|房)?)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?P<full>(?:TOWER|BLOCK)\s*(?P<block>\d{1,2}|[A-Z])[,\\s/-]*(?P<floor>\d{1,2})\s*(?:/F|FLOOR|F)[,\\s/-]*(?:FLAT|ROOM|UNIT)?\s*(?P<flat>[A-Z]\d?))",
                re.IGNORECASE,
            ),
            re.compile(
                r"(?P<full>(?P<floor>\d{1,2})\s*(?:樓|楼|F)?\s*(?P<flat>[A-Z]\d?)\s*(?:室|房))",
                re.IGNORECASE,
            ),
        ]

        for pattern in compact_patterns:
            match = pattern.search(text)
            if not match:
                continue

            block = (match.groupdict().get("block") or "").strip()
            floor = (match.groupdict().get("floor") or "").strip()
            flat = (match.groupdict().get("flat") or "").strip().upper()

            components = {
                "flat_room": f"{flat}室" if flat else "",
                "block": f"{block}座" if block and "座" not in block.upper() and "TOWER" not in block.upper() and "BLOCK" not in block.upper() else block,
                "floor": floor,
            }
            remaining = self._cleanup_address_fragment(f"{text[:match.start('full')]} {text[match.end('full'):]}")
            return components, remaining

        return {}, self._cleanup_address_fragment(text)

    def _extract_address_component(self, text: str, patterns: list[str]) -> tuple[str, str]:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            component = self._cleanup_address_fragment(match.group(0))
            remaining = self._cleanup_address_fragment(f"{text[:match.start()]} {text[match.end():]}")
            return component, remaining
        return "", self._cleanup_address_fragment(text)

    def _strip_area_prefix(self, text: str) -> str:
        stripped = text.strip()
        prefixes = [
            r"^(?:香港|Hong Kong|H\.?K\.?)",
            r"^(?:九龍|九龙|Kowloon|KLN\.?)",
            r"^(?:新界|New Territories|N\.?T\.?)",
        ]
        changed = True
        while changed:
            changed = False
            for pattern in prefixes:
                next_value = re.sub(pattern, "", stripped, count=1, flags=re.IGNORECASE).strip(" ,，")
                if next_value != stripped:
                    stripped = next_value
                    changed = True
        return self._cleanup_address_fragment(stripped)

    def _extract_district(self, text: str) -> tuple[str, str]:
        districts = [
            "中西區", "灣仔", "东区", "東區", "南區", "油尖旺", "深水埗", "九龙城", "九龍城", "黄大仙", "黃大仙",
            "观塘", "觀塘", "荃湾", "荃灣", "屯门", "屯門", "元朗", "北區", "北区", "大埔", "西貢", "西贡",
            "沙田", "葵青", "离岛", "離島",
        ]
        segments = [item.strip() for item in re.split(r"[\n,，;；]+", text) if item.strip()]
        street_markers = ("道", "街", "路", "里", "坊", "徑", "巷")
        for segment in segments:
            compact_segment = re.sub(r"\s+", "", segment)
            for district in districts:
                if segment == district or segment.endswith(f" {district}") or segment.endswith(district):
                    remaining_segments = [item for item in segments if item != segment]
                    if segment != district:
                        leading = self._cleanup_address_fragment(segment.removesuffix(district))
                        if leading:
                            remaining_segments.append(leading)
                    return district, self._cleanup_address_fragment(" ".join(remaining_segments))
                if compact_segment.startswith(district):
                    remainder = compact_segment[len(district):]
                    if remainder.startswith(street_markers):
                        return district, self._cleanup_address_fragment(text)
        return "", self._cleanup_address_fragment(text)

    def _extract_building_name(self, text: str) -> tuple[str, str]:
        segments = [item.strip() for item in re.split(r"[\n,，;；]+", text) if item.strip()]
        building_markers = ["大厦", "大廈", "中心", "廣場", "广场", "商業大廈", "商业大厦", "building", "tower", "centre", "center", "plaza"]
        for segment in segments:
            lowered = segment.lower()
            if any(marker in segment or marker in lowered for marker in building_markers):
                remaining_segments = [item for item in segments if item != segment]
                return self._cleanup_address_fragment(segment), self._cleanup_address_fragment(" ".join(remaining_segments))
        return "", self._cleanup_address_fragment(text)

    def _cleanup_address_fragment(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value or "").strip(" ,，;；")
        return cleaned

    def _split_reference_id(self, value: str) -> dict[str, str]:
        raw = (
            (value or "")
            .strip()
            .upper()
            .replace("（", "(")
            .replace("）", ")")
            .replace(" ", "")
            .replace("-", "")
            .replace("/", "")
        )
        match = re.match(r"^([A-Z]{1,2})(\d{6})\(?([0-9A])\)?$", raw)
        if match:
            return {
                "kind": "hkid",
                "prefix": match.group(1),
                "digits": match.group(2),
                "check_digit": match.group(3),
                "raw": f"{match.group(1)}{match.group(2)}({match.group(3)})",
            }
        return {"kind": "other", "prefix": "", "digits": "", "check_digit": "", "raw": raw}

    def _detect_area_key(self, address: str) -> str:
        lowered = (address or "").lower()
        if any(token in lowered for token in ["九龍", "九龙", "kln", "kowloon"]):
            return "kln"
        if any(token in lowered for token in ["新界", "n.t.", "new territories"]):
            return "nt"
        if any(token in lowered for token in ["香港", "h.k.", "hong kong"]):
            return "hk"
        return "others"

    def _wrap_text(self, text: str, font_size: float, max_width: float, max_lines: int) -> list[str]:
        if not text:
            return [""]
        tokens = list(text)
        lines: list[str] = []
        current = ""
        for token in tokens:
            candidate = f"{current}{token}"
            candidate_width = pdfmetrics.stringWidth(candidate, self.OVERLAY_FONT_NAME, font_size)
            if current and candidate_width > max_width:
                lines.append(current)
                current = token
                if len(lines) >= max_lines - 1:
                    break
            else:
                current = candidate
        remainder = "".join(tokens[len("".join(lines) + current):])
        if current:
            if remainder and len(lines) >= max_lines - 1:
                current = current[:-1] + "…"
            lines.append(current)
        return lines[:max_lines]

    def _fit_font_size(self, text: str, preferred_size: float, max_width: float, min_size: float = 8.5) -> float:
        self._ensure_reportlab_font()
        size = preferred_size
        while size > min_size and pdfmetrics.stringWidth(text, self.OVERLAY_FONT_NAME, size) > max_width:
            size -= 0.5
        return max(size, min_size)

    def _write_overlay_pdf(self, path: Path, page_width: float, page_height: float, draw_ops: list[dict[str, Any]]) -> None:
        self._ensure_reportlab_font()
        overlay = canvas.Canvas(str(path), pagesize=(page_width, page_height))
        for op in draw_ops:
            if op.get("type") == "rect":
                fill_rgb = op.get("fill_rgb") or (1, 1, 1)
                overlay.setFillColorRGB(*fill_rgb)
                overlay.setStrokeColorRGB(*fill_rgb)
                overlay.rect(
                    float(op["x"]),
                    float(op["y"]),
                    float(op["width"]),
                    float(op["height"]),
                    fill=1,
                    stroke=0,
                )
                continue
            text = str(op.get("text", "")).strip()
            if not text:
                continue
            overlay.setFillColorRGB(0, 0, 0)
            overlay.setFont(self.OVERLAY_FONT_NAME, float(op.get("font_size", 12)))
            overlay.drawString(float(op["x"]), float(op["y"]), text)
        overlay.save()

    def _write_image_overlay_pdf(self, path: Path, page_width: float, page_height: float, draw_ops: list[dict[str, Any]]) -> None:
        scale = 4
        image = Image.new("RGBA", (int(page_width * scale), int(page_height * scale)), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        font_path = self._get_overlay_font_path()

        for op in draw_ops:
            if op.get("type") == "rect":
                x = int(float(op["x"]) * scale)
                y = int((page_height - float(op["y"]) - float(op["height"])) * scale)
                width = int(float(op["width"]) * scale)
                height = int(float(op["height"]) * scale)
                draw.rectangle(
                    [x, y, x + width, y + height],
                    fill=(255, 255, 255, 255),
                )
                continue

            text = str(op.get("text", "")).strip()
            if not text:
                continue
            font_size = max(int(round(float(op.get("font_size", 12)) * scale)), 1)
            font = ImageFont.truetype(font_path, font_size)
            box = op.get("box")
            if box:
                x1, y1, x2, y2 = [float(value) for value in box]
                left = (x1 + 2) * scale
                top = (page_height - y2) * scale
                content_height = max((y2 - y1 - 2) * scale, font_size)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_height = bbox[3] - bbox[1]
                text_top = top + max((content_height - text_height) / 2, 0) - bbox[1]
                draw.text((left, text_top), text, fill=(0, 0, 0, 255), font=font)
            else:
                baseline_x = float(op["x"]) * scale
                baseline_y = (page_height - float(op["y"])) * scale
                bbox = draw.textbbox((0, 0), text, font=font)
                text_top = baseline_y - (bbox[3] - bbox[1])
                draw.text((baseline_x, text_top), text, fill=(0, 0, 0, 255), font=font)

        png_path = path.with_suffix(".png")
        image.save(png_path)

        overlay = canvas.Canvas(str(path), pagesize=(page_width, page_height))
        overlay.drawImage(ImageReader(str(png_path)), 0, 0, width=page_width, height=page_height, mask="auto")
        overlay.save()
        png_path.unlink(missing_ok=True)

    def _get_overlay_font_path(self) -> str:
        for candidate in self.OVERLAY_FONT_CANDIDATES:
            if Path(candidate).exists():
                return candidate
        return "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

    def _ensure_reportlab_font(self) -> None:
        try:
            pdfmetrics.getFont(self.OVERLAY_FONT_NAME)
        except KeyError:
            for candidate in self.OVERLAY_FONT_CANDIDATES:
                if not Path(candidate).exists():
                    continue
                try:
                    pdfmetrics.registerFont(TTFont(self.OVERLAY_FONT_NAME, candidate))
                    return
                except Exception:
                    continue
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
