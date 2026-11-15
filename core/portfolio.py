"""Parse a `ticker,montant` CSV (amounts in CAD) into a Portfolio contract dict.

Rules:
- comma separator, decimal point; header optional (`ticker,montant` or `ticker,amount`);
- tickers are trimmed and upper-cased; `RY` is read as `RY.TO` when only the TSX listing
  is in the universe (with a warning);
- duplicate tickers are summed (warning); zero amounts are ignored (warning);
- tickers outside the 31-asset universe go to `unanalyzed` with their share of the total;
- `Position.weight` is the share of the analyzed total (weights sum to 1).
Clear refusals (code `INVALID_CSV`): empty file, `;` separator, decimal comma,
non-numeric or negative amounts. No analyzable position: `UNKNOWN_TICKER`.
"""

from __future__ import annotations

import csv
import io
import math
import re
from typing import Any

from core.data import load_universe
from core.errors import AlphaForgeError

MAX_ROWS = 200
HEADER_TICKER = {"ticker", "symbole", "symbol"}
HEADER_AMOUNT = {"montant", "amount", "montant_cad", "amount_cad", "valeur", "value"}
_AMOUNT_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _invalid(message: str, **details: Any) -> AlphaForgeError:
    return AlphaForgeError("INVALID_CSV", message, details=details or None)


def _parse_amount(raw: str, line_no: int, ticker: str) -> float:
    cleaned = raw.strip().replace("$", "").replace(" ", "").replace(" ", "").replace(" ", "")
    if not _AMOUNT_RE.match(cleaned):
        raise _invalid(
            f"Ligne {line_no}: le montant « {raw.strip()} » pour {ticker} n'est pas un nombre "
            "(utilise un point pour les décimales, ex.: 1500.50).",
            line=line_no,
        )
    value = float(cleaned)
    if value < 0:
        raise _invalid(f"Ligne {line_no}: le montant de {ticker} est négatif.", line=line_no)
    return value


def _resolve_ticker(raw: str, universe: set[str]) -> tuple[str, str | None]:
    t = raw.strip().upper()
    if t in universe:
        return t, None
    if f"{t}.TO" in universe:
        return f"{t}.TO", f"{t} interprété comme {t}.TO (Bourse de Toronto)."
    return t, None


def _rows(csv_text: str) -> list[tuple[int, list[str]]]:
    text = csv_text.lstrip("﻿")
    if not text.strip():
        raise _invalid("Le fichier CSV est vide.")
    if ";" in text:
        raise _invalid("Le séparateur doit être une virgule (« , »), pas un point-virgule (« ; »).")
    rows = []
    for line_no, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        cells = [c.strip() for c in row]
        if not any(cells):
            continue
        rows.append((line_no, cells))
    if len(rows) > MAX_ROWS + 1:
        raise _invalid(f"Le fichier contient trop de lignes (maximum {MAX_ROWS}).")
    return rows


def _looks_like_header(cells: list[str]) -> bool:
    return len(cells) >= 2 and cells[0].lower() in HEADER_TICKER and cells[1].lower() in HEADER_AMOUNT


def parse_portfolio(csv_text: str) -> dict[str, Any]:
    """CSV text -> Portfolio dict (see module docstring)."""
    rows = _rows(csv_text)
    if rows and _looks_like_header(rows[0][1]):
        rows = rows[1:]
    if not rows:
        raise _invalid("Le fichier CSV ne contient aucune position.")

    uni = load_universe()
    known = set(uni.index)
    warnings: list[str] = []
    amounts: dict[str, float] = {}
    order: list[str] = []
    for line_no, cells in rows:
        if len(cells) == 3 and cells[1].lstrip("+-").isdigit() and cells[2].isdigit():
            raise _invalid(
                f"Ligne {line_no}: le montant semble utiliser une virgule décimale "
                f"(« {cells[1]},{cells[2]} »). Utilise un point: {cells[1]}.{cells[2]}.",
                line=line_no,
            )
        if len(cells) != 2:
            raise _invalid(
                f"Ligne {line_no}: on attend 2 colonnes « ticker,montant », trouvé {len(cells)}.", line=line_no
            )
        if not cells[0]:
            raise _invalid(f"Ligne {line_no}: ticker manquant.", line=line_no)
        ticker, note = _resolve_ticker(cells[0], known)
        amount = _parse_amount(cells[1], line_no, ticker)
        if note and note not in warnings:
            warnings.append(note)
        if ticker in amounts:
            warnings.append(f"{ticker} apparaît plusieurs fois: les montants ont été additionnés.")
        else:
            order.append(ticker)
        amounts[ticker] = amounts.get(ticker, 0.0) + amount

    for t in [t for t in order if amounts[t] == 0]:
        warnings.append(f"{t} a un montant nul et a été ignoré.")
        order.remove(t)
        del amounts[t]
    if not amounts:
        raise _invalid("Tous les montants sont nuls.")

    total = math.fsum(amounts.values())
    analyzed = [t for t in order if t in known]
    outside = [t for t in order if t not in known]
    analyzed_total = math.fsum(amounts[t] for t in analyzed)
    if not analyzed:
        raise AlphaForgeError(
            "UNKNOWN_TICKER",
            "Aucun ticker du fichier ne fait partie des 31 actifs analysés.",
            details={"tickers": outside},
        )
    if outside:
        warnings.append(
            f"{len(outside)} ticker(s) hors des 31 actifs analysés: {', '.join(outside)}. "
            "Ils sont comptés dans le total mais pas analysés."
        )

    positions = [
        {
            "ticker": t,
            "amount": round(amounts[t], 2),
            "weight": amounts[t] / analyzed_total,
            "asset_class": str(uni.loc[t, "asset_class"]),
            "price_currency": str(uni.loc[t, "price_currency"]),
            "in_universe": True,
        }
        for t in sorted(analyzed, key=lambda t: (-amounts[t], t))
    ]
    return {
        "base_currency": "CAD",
        "total_amount": round(total, 2),
        "positions": positions,
        "unanalyzed": {"tickers": outside, "weight": math.fsum(amounts[t] for t in outside) / total},
        "warnings": warnings,
    }
