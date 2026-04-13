import base64
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import fitz
import pdfplumber
from dateutil import parser as date_parser

from app.core.config import settings


logger = logging.getLogger(__name__)


INVOICE_EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "total_amount",
        "tax_amount",
        "line_items",
    ],
    "properties": {
        "vendor_name": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "invoice_number": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "invoice_date": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "currency": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "total_amount": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "tax_amount": {"anyOf": [{"type": "number"}, {"type": "null"}]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "quantity", "unit_price", "line_total"],
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "unit_price": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "line_total": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                },
            },
        },
    },
}


class AIService:
    FIELD_ALIASES = {
        "invoice_number": [
            "invoice number",
            "invoice no",
            "invoice #",
            "inv #",
            "inv no",
            "bill id",
            "bill number",
            "reference",
        ],
        "invoice_date": [
            "invoice date",
            "bill date",
            "date",
        ],
        "total_amount": [
            "total due",
            "amount due",
            "grand total",
            "invoice total",
            "total amount",
            "total",
        ],
        "tax_amount": [
            "tax",
            "vat",
            "gst",
            "sales tax",
        ],
    }
    TABLE_HEADERS = {
        "description": ["description", "service", "item", "details", "product"],
        "quantity": ["qty", "quantity", "hrs/qty", "hours", "hrs"],
        "unit_price": ["unit price", "rate", "price", "rate/price", "rate price"],
        "line_total": ["line total", "sub total", "subtotal", "amount", "total"],
    }
    INVALID_VENDOR_PATTERNS = [
        "page ",
        "paid",
        "tax",
        "total due",
        "subtotal",
        "amount due",
    ]
    CURRENCY_MAP = {
        "$": "USD",
        "USD": "USD",
        "AUD": "AUD",
        "CAD": "CAD",
        "EUR": "EUR",
        "GBP": "GBP",
        "INR": "INR",
        "Rs": "INR",
        "Rs.": "INR",
        "AUD$": "AUD",
        "US$": "USD",
        "CAD$": "CAD",
        "\u20ac": "EUR",
        "\u00a3": "GBP",
    }

    @staticmethod
    async def extract_text_from_pdf(pdf_path: str) -> str:
        context = AIService._build_pdf_context(pdf_path)
        return context["text"]

    @staticmethod
    async def extract_structured_data(
        text: str,
        prompt_text: str | None = None,
        pdf_path: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt_body = prompt_text or settings.DEFAULT_PROMPT_TEXT
        provider = settings.EXTRACTION_PROVIDER.lower()
        context = AIService._build_pdf_context(pdf_path, fallback_text=text)
        attempts: list[dict[str, Any]] = []

        if provider in {"auto", "openai"} and settings.OPENAI_API_KEY and pdf_path:
            try:
                payload = AIService._extract_with_openai(prompt_body, context, pdf_path)
                return payload, {
                    "provider": "openai",
                    "model": settings.OPENAI_MODEL,
                    "attempts": attempts,
                }
            except Exception as exc:
                logger.exception("OpenAI extraction failed")
                attempts.append({"provider": "openai", "error": str(exc)})
                if provider == "openai":
                    raise

        if provider in {"auto", "gemini"} and settings.GEMINI_API_KEY:
            try:
                payload = AIService._extract_with_gemini(prompt_body, context)
                return payload, {
                    "provider": "gemini",
                    "model": settings.GEMINI_MODEL,
                    "attempts": attempts,
                }
            except Exception as exc:
                logger.exception("Gemini extraction failed")
                attempts.append({"provider": "gemini", "error": str(exc)})
                if provider == "gemini":
                    raise

        payload = AIService._heuristic_extraction(context)
        return payload, {
            "provider": "heuristic",
            "model": "rules-and-layout",
            "attempts": attempts,
        }

    @staticmethod
    def _build_pdf_context(pdf_path: str | None, fallback_text: str | None = None) -> dict[str, Any]:
        if not pdf_path:
            lines = [line.strip() for line in (fallback_text or "").splitlines() if line.strip()]
            return {
                "text": "\n".join(lines),
                "lines": lines,
                "tables": [],
            }

        text_parts: list[str] = []
        tables: list[list[list[str]]] = []

        with fitz.open(pdf_path) as document:
            for page in document:
                page_text = page.get_text("text").strip()
                if page_text:
                    text_parts.append(page_text)

        with pdfplumber.open(pdf_path) as document:
            for page in document.pages:
                page_text = (page.extract_text() or "").strip()
                if page_text and page_text not in text_parts:
                    text_parts.append(page_text)

                for table in page.extract_tables() or []:
                    cleaned_table = []
                    for row in table:
                        cleaned_table.append([str(cell or "").strip() for cell in row])
                    if cleaned_table:
                        tables.append(cleaned_table)

        text = "\n".join(part for part in text_parts if part.strip())
        if not text and fallback_text:
            text = fallback_text

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return {
            "text": text,
            "lines": lines,
            "tables": tables,
        }

    @staticmethod
    def _extract_with_openai(prompt_text: str, context: dict[str, Any], pdf_path: str) -> dict[str, Any]:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS)
        with open(pdf_path, "rb") as file_handle:
            encoded_pdf = base64.b64encode(file_handle.read()).decode("utf-8")

        supplemental_context = AIService._build_llm_context(context)
        response = client.responses.create(
            model=settings.OPENAI_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt_text,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "filename": pdf_path.split("\\")[-1].split("/")[-1],
                            "file_data": f"data:application/pdf;base64,{encoded_pdf}",
                        },
                        {
                            "type": "input_text",
                            "text": supplemental_context,
                        },
                    ],
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "invoice_extraction",
                    "strict": True,
                    "schema": INVOICE_EXTRACTION_SCHEMA,
                }
            },
        )
        if not response.output_text:
            raise ValueError("OpenAI did not return structured output text.")
        return AIService._coerce_payload(json.loads(response.output_text))

    @staticmethod
    def _extract_with_gemini(prompt_text: str, context: dict[str, Any]) -> dict[str, Any]:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(
            (
                f"{prompt_text}\n\n"
                "Return JSON only for the invoice schema described.\n\n"
                f"{AIService._build_llm_context(context)}"
            ),
            generation_config={"response_mime_type": "application/json"},
        )
        return AIService._coerce_payload(json.loads(response.text))

    @staticmethod
    def _build_llm_context(context: dict[str, Any]) -> str:
        table_preview = []
        for index, table in enumerate(context["tables"][: settings.MAX_TABLES_FOR_LLM], start=1):
            table_preview.append(f"Table {index}: {json.dumps(table[: settings.MAX_ROWS_PER_TABLE], ensure_ascii=True)}")
        return (
            "Extract invoice fields from the PDF. Use the PDF as source of truth. "
            "Do not invent missing values. Use null when a field is not present. "
            "Only include actual billed rows in line_items, not subtotal, tax, total, payment, or banking rows.\n\n"
            f"OCR text:\n{context['text'][: settings.LLM_TEXT_LIMIT]}\n\n"
            f"Detected tables:\n{chr(10).join(table_preview)[: settings.LLM_TEXT_LIMIT]}"
        )

    @staticmethod
    def _heuristic_extraction(context: dict[str, Any]) -> dict[str, Any]:
        lines = context["lines"]
        vendor_name = AIService._extract_vendor(lines)
        invoice_number = AIService._extract_labeled_value(lines, AIService.FIELD_ALIASES["invoice_number"])
        invoice_date = AIService._extract_labeled_value(lines, AIService.FIELD_ALIASES["invoice_date"])
        total_amount_raw = AIService._extract_labeled_value(lines, AIService.FIELD_ALIASES["total_amount"])
        tax_amount_raw = AIService._extract_labeled_value(lines, AIService.FIELD_ALIASES["tax_amount"])

        line_items = AIService._extract_line_items_from_tables(context["tables"])
        if not line_items:
            line_items = AIService._extract_line_items_from_lines(lines)

        total_amount = AIService._parse_money(total_amount_raw)
        tax_amount = AIService._parse_money(tax_amount_raw, default=0.0)
        if total_amount is None and line_items:
            inferred_total = sum(item["line_total"] for item in line_items)
            total_amount = round(inferred_total + (tax_amount or 0.0), 2)

        currency = AIService._detect_currency(context["text"], total_amount_raw, tax_amount_raw)
        if not currency and total_amount_raw:
            currency = AIService._infer_currency_from_locale(context["text"])

        return {
            "vendor_name": vendor_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "currency": currency,
            "total_amount": total_amount,
            "tax_amount": tax_amount,
            "line_items": line_items,
        }

    @staticmethod
    def _extract_vendor(lines: list[str]) -> str | None:
        section_vendor = AIService._extract_party_from_section(lines, "from", stop_labels=["to", "invoice number", "bill to"])
        if section_vendor:
            return section_vendor

        for line in lines[:10]:
            normalized = line.lower()
            if normalized in {"invoice", "tax invoice"}:
                continue
            if any(pattern in normalized for pattern in AIService.INVALID_VENDOR_PATTERNS):
                continue
            if normalized in {"from:", "to:"}:
                continue
            if re.fullmatch(r"page\s+\d+(/\d+)?", normalized):
                continue
            if "@" in line or re.search(r"\d", line):
                continue
            return line.strip()
        return None

    @staticmethod
    def _extract_party_from_section(lines: list[str], label: str, stop_labels: list[str]) -> str | None:
        for index, line in enumerate(lines):
            normalized = line.lower().strip()
            if normalized.rstrip(":") != label:
                continue

            collected: list[str] = []
            for candidate in lines[index + 1 :]:
                candidate_normalized = candidate.lower().strip().rstrip(":")
                if candidate_normalized in stop_labels:
                    break
                if any(candidate_normalized.startswith(stop_label) for stop_label in stop_labels):
                    break
                if not candidate.strip():
                    if collected:
                        break
                    continue
                collected.append(candidate.strip())
                if len(collected) >= 4:
                    break

            for candidate in collected:
                if "@" in candidate:
                    continue
                return candidate
        return None

    @staticmethod
    def _extract_labeled_value(lines: list[str], aliases: list[str]) -> str | None:
        normalized_aliases = [alias.lower() for alias in aliases]
        for index, line in enumerate(lines):
            normalized_line = " ".join(line.lower().split())
            for alias in normalized_aliases:
                if not normalized_line.startswith(alias):
                    continue

                suffix = line[len(line[: len(alias)]) :].strip(" :-\t")
                if suffix and suffix.lower() != alias:
                    return suffix

                if ":" in line:
                    suffix = line.split(":", 1)[1].strip()
                    if suffix:
                        return suffix

                tokens = line.split()
                alias_tokens = alias.split()
                if len(tokens) > len(alias_tokens):
                    candidate = " ".join(tokens[len(alias_tokens) :]).strip()
                    if candidate:
                        return candidate

                next_value = AIService._next_meaningful_line(lines, index + 1)
                if next_value:
                    return next_value

        combined_text = "\n".join(lines)
        for alias in normalized_aliases:
            pattern = re.compile(rf"{re.escape(alias)}\s*[:\-]?\s*(.+)", re.IGNORECASE)
            match = pattern.search(combined_text)
            if match:
                candidate = match.group(1).splitlines()[0].strip()
                if candidate:
                    return candidate
        return None

    @staticmethod
    def _next_meaningful_line(lines: list[str], start_index: int) -> str | None:
        for candidate in lines[start_index : start_index + 3]:
            stripped = candidate.strip()
            if stripped:
                return stripped
        return None

    @staticmethod
    def _extract_line_items_from_tables(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for table in tables:
            if not table:
                continue

            header = [AIService._normalize_header(cell) for cell in table[0]]
            column_map = AIService._map_table_columns(header)
            if "description" not in column_map or "line_total" not in column_map:
                continue

            for row in table[1:]:
                if not row:
                    continue
                item = AIService._build_line_item_from_row(row, column_map)
                if item:
                    items.append(item)

        return items

    @staticmethod
    def _normalize_header(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower()).strip()

    @staticmethod
    def _map_table_columns(header: list[str]) -> dict[str, int]:
        mapping: dict[str, int] = {}
        for index, column_name in enumerate(header):
            for target, aliases in AIService.TABLE_HEADERS.items():
                if any(alias == column_name or alias in column_name for alias in aliases):
                    mapping[target] = index
                    break
        return mapping

    @staticmethod
    def _build_line_item_from_row(row: list[str], column_map: dict[str, int]) -> dict[str, Any] | None:
        description = row[column_map["description"]].strip() if column_map.get("description") is not None else ""
        if not description or AIService._is_summary_row(description):
            return None

        quantity = AIService._parse_number(AIService._get_row_value(row, column_map, "quantity"))
        unit_price = AIService._parse_money(AIService._get_row_value(row, column_map, "unit_price"))
        line_total = AIService._parse_money(AIService._get_row_value(row, column_map, "line_total"))

        if line_total is None and quantity is not None and unit_price is not None:
            line_total = round(quantity * unit_price, 2)

        if line_total is None:
            return None

        return {
            "description": description,
            "quantity": quantity or 0.0,
            "unit_price": unit_price or 0.0,
            "line_total": line_total,
        }

    @staticmethod
    def _get_row_value(row: list[str], column_map: dict[str, int], key: str) -> str | None:
        index = column_map.get(key)
        if index is None or index >= len(row):
            return None
        return row[index]

    @staticmethod
    def _extract_line_items_from_lines(lines: list[str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        header_index = None

        for index, line in enumerate(lines):
            normalized = AIService._normalize_header(line)
            if (
                any(token in normalized for token in ["description", "service", "item"])
                and any(token in normalized for token in ["qty", "hrs", "quantity"])
                and any(token in normalized for token in ["price", "rate", "subtotal", "total"])
            ):
                header_index = index + 1
                break

        if header_index is None:
            return items

        current_description: list[str] = []
        current_numbers: list[float] = []
        for line in lines[header_index:]:
            normalized = AIService._normalize_header(line)
            if AIService._is_summary_row(normalized):
                break

            numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", line)
            money_like = bool(re.search(r"[$]|usd|aud|eur|gbp|inr|cad", line, re.IGNORECASE))
            if numbers and money_like:
                current_numbers.extend(float(number) for number in numbers)
            else:
                current_description.append(line)

            if current_description and len(current_numbers) >= 3:
                description = " ".join(part.strip() for part in current_description if part.strip())
                quantity = current_numbers[0]
                unit_price = current_numbers[-2]
                line_total = current_numbers[-1]
                if description and not AIService._is_summary_row(description):
                    items.append(
                        {
                            "description": description,
                            "quantity": quantity,
                            "unit_price": unit_price,
                            "line_total": line_total,
                        }
                    )
                current_description = []
                current_numbers = []

        return items

    @staticmethod
    def _is_summary_row(value: str) -> bool:
        normalized = AIService._normalize_header(value)
        return any(
            token in normalized
            for token in ["subtotal", "sub total", "tax", "total", "amount due", "balance", "payment", "bank"]
        )

    @staticmethod
    def _detect_currency(*values: str | None) -> str | None:
        explicit_map = {key: value for key, value in AIService.CURRENCY_MAP.items() if key != "$"}
        for value in values:
            if not value:
                continue
            upper_value = str(value).upper()
            for token, currency in explicit_map.items():
                if token.isalpha() and re.search(rf"\b{re.escape(token.upper())}\b", upper_value):
                    return currency
                if not token.isalpha() and token.upper() in upper_value:
                    return currency
        joined = " ".join(str(value) for value in values if value)
        if "$" in joined:
            return AIService._infer_currency_from_locale(joined) or "USD"
        return None

    @staticmethod
    def _infer_currency_from_locale(text: str) -> str | None:
        upper_text = text.upper()
        if any(token in upper_text for token in ["MELBOURNE", "SYDNEY", "VIC", "NSW", "ANZ BANK", "AUSTRALIA"]):
            return "AUD"
        if any(token in upper_text for token in ["LONDON", "UNITED KINGDOM"]):
            return "GBP"
        if any(token in upper_text for token in ["GERMANY", "FRANCE", "SPAIN", "ITALY", "EUROPEAN UNION"]):
            return "EUR"
        if any(token in upper_text for token in ["INDIA", "BENGALURU", "MUMBAI", "DELHI"]):
            return "INR"
        return "USD" if "$" in text else None

    @staticmethod
    def _coerce_payload(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Structured extraction payload must be an object.")

        payload.setdefault("line_items", [])
        if not isinstance(payload["line_items"], list):
            payload["line_items"] = []
        return payload

    @staticmethod
    def _parse_money(value: str | float | int | None, default: float | None = None) -> float | None:
        if value is None or value == "":
            return default
        if isinstance(value, (int, float)):
            return round(float(value), 2)

        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if not cleaned:
            return default
        try:
            return round(float(Decimal(cleaned)), 2)
        except (InvalidOperation, ValueError):
            return default

    @staticmethod
    def _parse_number(value: str | float | int | None) -> float | None:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)

        cleaned = re.sub(r"[^0-9.\-]", "", str(value))
        if not cleaned:
            return None
        try:
            return float(Decimal(cleaned))
        except (InvalidOperation, ValueError):
            return None


class ValidationService:
    REQUIRED_FIELDS = [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "currency",
        "total_amount",
        "line_items",
    ]

    @staticmethod
    def validate_invoice(data: dict[str, Any]) -> dict[str, Any]:
        normalized = ValidationService._normalize_payload(data)
        errors: list[str] = []
        missing_fields: list[str] = []

        for field in ValidationService.REQUIRED_FIELDS:
            if ValidationService._is_missing(normalized.get(field)):
                missing_fields.append(field)
                errors.append(f"Missing field: {field}")

        if normalized["vendor_name"] and ValidationService._looks_invalid_vendor(normalized["vendor_name"]):
            errors.append("Vendor name looks invalid or extracted from a non-vendor label.")

        if normalized["invoice_number"] and not re.search(r"\d", normalized["invoice_number"]):
            errors.append("Invoice number does not contain a numeric component.")

        if normalized["total_amount"] is not None and normalized["total_amount"] <= 0:
            errors.append("Total amount must be greater than zero.")

        if normalized["line_items"]:
            line_item_sum = round(sum(item["line_total"] for item in normalized["line_items"]), 2)
            total_amount = normalized.get("total_amount") or 0.0
            tax_amount = normalized.get("tax_amount") or 0.0
            delta = abs((line_item_sum + tax_amount) - total_amount)
            if total_amount and delta > settings.TOTAL_TOLERANCE:
                errors.append(
                    f"Line items plus tax ({line_item_sum + tax_amount:.2f}) do not match total ({total_amount:.2f})."
                )
        else:
            errors.append("No line items were detected.")

        confidence = 0.98
        confidence -= len(set(missing_fields)) * 0.12
        confidence -= len(errors) * 0.05
        if normalized["line_items"]:
            blank_descriptions = sum(1 for item in normalized["line_items"] if not item["description"])
            confidence -= blank_descriptions * 0.03

        return {
            "normalized_data": normalized,
            "errors": sorted(set(errors)),
            "missing_fields": missing_fields,
            "confidence_score": round(max(0.1, min(0.99, confidence)), 2),
        }

    @staticmethod
    def _normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        normalized["vendor_name"] = ValidationService._clean_text(normalized.get("vendor_name"))
        normalized["invoice_number"] = ValidationService._clean_text(normalized.get("invoice_number"))
        normalized["invoice_date"] = ValidationService._normalize_date(normalized.get("invoice_date"))
        normalized["currency"] = ValidationService._normalize_currency(normalized.get("currency"))
        normalized["total_amount"] = AIService._parse_money(normalized.get("total_amount"))
        normalized["tax_amount"] = AIService._parse_money(normalized.get("tax_amount"), default=0.0) or 0.0
        normalized["line_items"] = ValidationService._normalize_line_items(normalized.get("line_items", []))
        return normalized

    @staticmethod
    def _normalize_date(value: Any) -> str | None:
        if not value:
            return None
        try:
            return date_parser.parse(str(value), fuzzy=True).date().isoformat()
        except Exception:
            return str(value).strip()

    @staticmethod
    def _normalize_currency(value: Any) -> str | None:
        if not value:
            return None
        normalized = str(value).strip().upper()
        return AIService.CURRENCY_MAP.get(normalized, normalized)

    @staticmethod
    def _normalize_line_items(items: Any) -> list[dict[str, Any]]:
        normalized_items: list[dict[str, Any]] = []
        if not isinstance(items, list):
            return normalized_items

        for item in items:
            if not isinstance(item, dict):
                continue
            description = ValidationService._clean_text(item.get("description")) or ""
            quantity = AIService._parse_number(item.get("quantity")) or 0.0
            unit_price = AIService._parse_money(item.get("unit_price"), default=0.0) or 0.0
            line_total = AIService._parse_money(item.get("line_total"))
            if line_total is None:
                line_total = round(quantity * unit_price, 2)
            if not description and line_total == 0:
                continue
            normalized_items.append(
                {
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
        return normalized_items

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        return cleaned or None

    @staticmethod
    def _looks_invalid_vendor(value: str) -> bool:
        normalized = value.lower()
        return normalized in {"invoice", "tax invoice", "page 1/1", "page 1"}

    @staticmethod
    def _is_missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
        if isinstance(value, list) and len(value) == 0:
            return True
        return False
