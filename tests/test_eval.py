"""A8: classifier evaluation tool (mock classifier, temporary labels file)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import rules_engine as engine
from tools import run_eval

HEADER = ("id,title,ticker,category,controversy,horizon_relevance,expected_relevance_robert,"
          "expected_relevance_amira,expected_relevance_mateo,is_synthetic,notes\n")
LABELS = HEADER + """1,NVIDIA reports record quarterly earnings,NVDA,earnings_results,false,structural,,,,true,
2,Royal Bank raises its dividend by 4%,RY.TO,dividend,false,structural,,,,true,
3,Enbridge hit by lawsuit after pipeline spill,ENB.TO,controversy,true,structural,,,,true,
4,Bank of Canada holds its key interest rate,,macro_rates,false,macro_context,,,,true,
5,Analyst raises Microsoft price target,MSFT,analyst_rating,false,short_term_noise,,,,true,
6,Shopify unveils new AI tools for merchants,SHOP.TO,guidance_strategy,false,structural,,,,true,deliberate error
"""


@pytest.fixture(autouse=True)
def _rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(engine.EXAMPLE_RULES_DIR))
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    engine.clear_cache()


def test_eval_report(tmp_path: Path) -> None:
    labels = tmp_path / "labeled_headlines.csv"
    labels.write_text(LABELS, encoding="utf-8")
    out = tmp_path / "reports"
    assert run_eval.main(["--labels", str(labels), "--out", str(out)]) == 0
    (report,) = out.glob("classifier_*.md")
    text = report.read_text(encoding="utf-8")
    assert "Accord global sur la catégorie: 83,3 %" in text  # 5/6: the product headline is labeled strategy
    assert "Matrice de confusion" in text and "attendu **guidance_strategy**, prédit **product**" in text
    assert "mock-keywords" in text


def test_missing_labels(tmp_path: Path) -> None:
    assert run_eval.main(["--labels", str(tmp_path / "nope.csv"), "--out", str(tmp_path)]) == 1


def test_missing_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("id,headline\n1,x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        run_eval.load_labels(bad)
