"""本地演示股东名册。只认文件里的 FCC-DEMO-REGISTER-V1 标记，其它文件仍是空抽取。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MARKER = "FCC-DEMO-REGISTER-V1"
END = "END-FCC-DEMO-REGISTER"


@dataclass(frozen=True)
class DemoParty:
    temp_key: str
    kind: str
    legal_name: str
    entity_type: str | None
    title: str
    ownership_percent: Decimal
    country: str
    confidence: Decimal
    quote: str
    relations: tuple[tuple[str, Decimal | None], ...]


def page_text_from_bytes(raw: bytes) -> str | None:
    parties = parties_from_bytes(raw)
    if not parties:
        return None
    lines = [
        "Shareholder Register",
        "Cedar & Pine Holdings Inc.",
        "Ontario (OBCA) · BN 81920 4471",
        "Issued common shares: 1,000",
        "",
    ]
    lines.extend(party.quote for party in parties)
    lines.append("")
    lines.append(MARKER)
    for party in parties:
        entity_type = party.entity_type or ""
        lines.append(
            "|".join(
                (
                    party.legal_name,
                    party.kind,
                    entity_type,
                    party.title,
                    format(party.ownership_percent, "f"),
                    party.country,
                    format(party.confidence, "f"),
                    party.quote,
                )
            )
        )
    lines.append(END)
    return "\n".join(lines)


def parties_from_bytes(raw: bytes) -> list[DemoParty]:
    text = raw.decode("latin-1", errors="ignore")
    return parties_from_text(text)


def parties_from_text(text: str) -> list[DemoParty]:
    start = text.find(MARKER)
    end = text.find(END)
    if start < 0 or end < start:
        return []
    block = text[start + len(MARKER) : end]
    parties: list[DemoParty] = []
    index = 0
    for raw_line in block.splitlines():
        line = raw_line.strip().lstrip("%").strip()
        if not line or line == MARKER:
            continue
        parts = [item.strip() for item in line.split("|")]
        if len(parts) != 8:
            continue
        legal_name, kind, entity_type, title, percent, country, confidence, quote = parts
        if kind not in {"PERSON", "ENTITY"} or not legal_name or not quote:
            continue
        index += 1
        ownership = Decimal(percent)
        parties.append(
            DemoParty(
                temp_key=f"e{index}",
                kind=kind,
                legal_name=legal_name,
                entity_type=entity_type or None,
                title=title,
                ownership_percent=ownership,
                country=country or "Canada",
                confidence=Decimal(confidence),
                quote=quote,
                relations=_relations(title, ownership),
            )
        )
    return parties


def _relations(title: str, ownership: Decimal) -> tuple[tuple[str, Decimal | None], ...]:
    lowered = title.casefold()
    found: list[tuple[str, Decimal | None]] = []
    if ownership > 0 or "shareholder" in lowered:
        found.append(("OWNS", ownership))
    if "director" in lowered:
        found.extend((("DIRECTOR_OF", None), ("SIGNS", None)))
    elif "trustee" in lowered:
        found.extend((("TRUSTEE_OF", None), ("SIGNS", None)))
    elif "secretary" in lowered or "officer" in lowered or "sign" in lowered:
        found.extend((("OFFICER_OF", None), ("SIGNS", None)))
    return tuple(found)
