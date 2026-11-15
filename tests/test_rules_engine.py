"""A3 acceptance: rules engine (deterministic, no LLM) and rule-file validation."""

from __future__ import annotations

import inspect
import shutil
from pathlib import Path

import pytest

from core import rules_engine as engine
from core.errors import AlphaForgeError
from core.evidence import EvidenceRegistry
from core.portfolio import parse_portfolio
from tests.test_contracts import assert_valid
from tools import validate_rules

EXAMPLES = engine.EXAMPLE_RULES_DIR
ANSWERS = {
    "robert": {"q_horizon": "h_3_5", "q_drop": "d_hold", "q_objective": "o_preserve", "q_loss": "l_10",
               "q_experience": "e_intermediate", "q_ethics": "x_none", "q_interests": "i_dividends",
               "q_expenses": "m_gt5k"},
    "amira": {"q_horizon": "h_gt12", "q_drop": "d_buy", "q_objective": "o_growth", "q_loss": "l_35",
              "q_experience": "e_intermediate", "q_ethics": "x_none", "q_interests": "i_crypto"},
    "mateo": {"q_horizon": "h_6_12", "q_drop": "d_hold", "q_objective": "o_balanced", "q_loss": "l_20",
              "q_experience": "e_intermediate", "q_ethics": "x_energy", "q_interests": "i_none"},
}


@pytest.fixture(autouse=True)
def _example_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(EXAMPLES))
    engine.clear_cache()
    yield
    engine.clear_cache()


@pytest.fixture
def personas() -> dict[str, dict]:
    return {p["id"]: p for p in engine.load_personas()}


def portfolio_of(persona: dict) -> dict:
    return parse_portfolio(persona["sample_portfolio_csv"])


# --- profile -------------------------------------------------------------------------


@pytest.mark.parametrize("pid", ["robert", "amira", "mateo"])
def test_questionnaire_rebuilds_persona_profile(pid: str, personas: dict) -> None:
    prof = engine.score_profile(ANSWERS[pid])
    assert_valid("Profile", prof)
    expected = personas[pid]["profile"]
    for key in ("horizon_bucket", "risk_tolerance", "objective", "max_acceptable_loss_pct", "limits"):
        assert prof[key] == expected[key], key
    assert prof["source"] == "questionnaire"


def test_inconsistencies_are_reported() -> None:
    answers = {**ANSWERS["amira"], "q_horizon": "h_lt3", "q_experience": "e_beginner"}
    prof = engine.score_profile(answers)
    assert prof["risk_tolerance"] == "high"
    assert "Tolérance au risque élevée, mais horizon court." in prof["inconsistencies"]
    assert "Objectif de croissance, mais horizon de moins de 3 ans." in prof["inconsistencies"]


@pytest.mark.parametrize(("answers", "fragment"), [
    ({"q_unknown": "x"}, "inconnue"),
    ({"q_horizon": "h_3_5"}, "sans réponse"),
    ({**ANSWERS["robert"], "q_drop": "nope"}, "Option « nope » inconnue"),
    ("not a dict", "objet"),
])
def test_invalid_answers(answers: object, fragment: str) -> None:
    with pytest.raises(AlphaForgeError) as exc:
        engine.score_profile(answers)  # type: ignore[arg-type]
    assert exc.value.code == "INVALID_ANSWERS"
    assert fragment in exc.value.message


def test_optional_question_can_be_skipped() -> None:
    prof = engine.score_profile({k: v for k, v in ANSWERS["robert"].items() if k != "q_expenses"})
    assert prof["monthly_expenses_cad"] is None


# --- relevance -----------------------------------------------------------------------

CATEGORIES = ["earnings_results", "dividend", "macro_rates", "guidance_strategy", "product", "analyst_rating"]


def test_same_news_differs_between_robert_and_amira(personas: dict) -> None:
    rob, ami = personas["robert"]["profile"], personas["amira"]["profile"]
    different = []
    for cat in CATEGORIES:
        cls = {"category": cat, "controversy": False, "horizon_relevance": "structural"}
        a, b = engine.score_relevance(rob, cls), engine.score_relevance(ami, cls)
        if a["score"] != b["score"]:
            different.append(cat)
            assert a["rule_hits"][0]["text"] != b["rule_hits"][0]["text"]  # explained by a rule
    assert len(different) >= 3


def test_relevance_hits_and_hidden_reason(personas: dict) -> None:
    mateo = personas["mateo"]["profile"]
    pos = engine.position_context(portfolio_of(personas["mateo"]), ["ENB.TO"], 0.30)
    res = engine.score_relevance(mateo, {"category": "controversy", "controversy": True,
                                         "horizon_relevance": "structural"}, pos)
    ids = [h["rule_id"] for h in res["rule_hits"]]
    assert ids == ["R_BASE_CONTROVERSY", "R_PREF_CONTROVERSY", "R_EXCLUDED_SECTOR"]
    assert res["shown"] and res["level"] == "high" and res["score"] == 1.0
    noise = engine.score_relevance(mateo, {"category": "price_commentary", "controversy": False,
                                           "horizon_relevance": "short_term_noise"})
    assert not noise["shown"] and noise["level"] == "low"
    assert noise["hidden_reason"] == "Bruit de court terme pour ton horizon"


def test_position_bonus_and_over_limit(personas: dict) -> None:
    robert = personas["robert"]["profile"]
    port = parse_portfolio("ticker,montant\nNVDA,3000\nXBB.TO,7000\n")
    pos = engine.position_context(port, ["NVDA"], 0.30)
    res = engine.score_relevance(robert, {"category": "earnings_results", "controversy": False,
                                          "horizon_relevance": "structural"}, pos)
    ids = {h["rule_id"]: h for h in res["rule_hits"]}
    assert ids["R_POS_WEIGHT_20"]["observed"] == pytest.approx(0.3)
    assert ids["R_OVER_LIMIT"]["observed"] == pytest.approx(0.3)
    assert ids["R_OVER_LIMIT"]["limit"] == pytest.approx(0.10)
    assert "R_HIGH_VOL_SHORT" in ids


# --- coherence -----------------------------------------------------------------------


def test_robert_nvda_20_is_incoherent_with_two_quantified_reasons(personas: dict) -> None:
    reg = EvidenceRegistry()
    res = engine.check_coherence(personas["robert"]["profile"], portfolio_of(personas["robert"]),
                                 {"ticker": "NVDA", "intended_weight": 0.20}, reg)
    assert res["verdict"] == "incoherent"
    quantified = [h for h in res["rule_hits"] if "observed" in h and "limit" in h]
    assert len(quantified) >= 2
    for h in res["rule_hits"]:
        assert h["rule_id"] and h["text"] and "{" not in h["text"]
        assert_valid("RuleHit", h)
        for ev_id in res["rule_evidence"][h["rule_id"]]:
            assert ev_id in reg
    single = next(h for h in res["rule_hits"] if h["rule_id"] == "C_MAX_SINGLE")
    assert (single["observed"], single["limit"]) == (0.2, 0.1)
    assert res["metrics"]["max_drawdown"] == pytest.approx(-0.663, abs=0.005)


def test_amira_nvda_20_is_at_most_tension(personas: dict) -> None:
    res = engine.check_coherence(personas["amira"]["profile"], portfolio_of(personas["amira"]),
                                 {"ticker": "NVDA", "intended_weight": 0.20})
    assert res["verdict"] in ("coherent", "tension")


def test_crypto_rule_for_low_risk(personas: dict) -> None:
    res = engine.check_coherence(personas["robert"]["profile"], portfolio_of(personas["robert"]),
                                 {"ticker": "BTC-USD", "intended_weight": 0.05})
    assert "C_CRYPTO_LOW_RISK" in [h["rule_id"] for h in res["rule_hits"]]
    assert res["verdict"] == "incoherent"


def test_portfolio_after_math(personas: dict) -> None:
    port = parse_portfolio("ticker,montant\nSPY,8000\nNVDA,2000\n")
    after = engine.portfolio_after(port, "NVDA", 0.5)
    w = {p["ticker"]: p["weight"] for p in after["positions"]}
    assert w["NVDA"] == pytest.approx(0.5) and w["SPY"] == pytest.approx(0.5)
    after2 = engine.portfolio_after(port, "TSLA", 0.2)
    assert {p["ticker"]: p["weight"] for p in after2["positions"]}["TSLA"] == pytest.approx(0.2)


@pytest.mark.parametrize(("cons", "code"), [
    ({"ticker": "FOO", "intended_weight": 0.1}, "UNKNOWN_TICKER"),
    ({"ticker": "NVDA", "intended_weight": 1.5}, "INVALID_CONSIDERATION"),
    ({"ticker": "NVDA", "intended_weight": 0}, "INVALID_CONSIDERATION"),
])
def test_invalid_consideration(cons: dict, code: str, personas: dict) -> None:
    with pytest.raises(AlphaForgeError) as exc:
        engine.check_coherence(personas["robert"]["profile"], portfolio_of(personas["robert"]), cons)
    assert exc.value.code == code


def test_deterministic(personas: dict) -> None:
    args = (personas["robert"]["profile"], portfolio_of(personas["robert"]), {"ticker": "NVDA", "intended_weight": 0.2})
    assert engine.check_coherence(*args) == engine.check_coherence(*args)
    assert engine.score_profile(ANSWERS["amira"]) == engine.score_profile(ANSWERS["amira"])


def test_no_llm_in_rules_engine() -> None:
    src = inspect.getsource(engine)
    assert "agents" not in src and "boto3" not in src and "bedrock" not in src.lower()


# --- loading & validation ------------------------------------------------------------


def test_missing_rules_dir_falls_back_to_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RULES_DIR", str(tmp_path))
    engine.clear_cache()
    assert "questionnaire.yaml" in engine.rules_status()["example_fallbacks"]
    assert len(engine.load_personas()) == 3


def test_rules_dir_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copy(EXAMPLES / "profile_rules.yaml", tmp_path / "profile_rules.yaml")
    text = (tmp_path / "profile_rules.yaml").read_text(encoding="utf-8")
    (tmp_path / "profile_rules.yaml").write_text(text.replace("max_single_position: 0.10", "max_single_position: 0.12"),
                                                 encoding="utf-8")
    monkeypatch.setenv("RULES_DIR", str(tmp_path))
    engine.clear_cache()
    assert engine.score_profile(ANSWERS["robert"])["limits"]["max_single_position"] == 0.12
    assert "profile_rules.yaml" not in engine.rules_status()["example_fallbacks"]


def test_examples_pass_validation() -> None:
    rep = validate_rules.validate(EXAMPLES)
    assert rep.errors == [] and rep.warnings == []


def _broken_dir(tmp_path: Path, name: str, old: str, new: str) -> Path:
    shutil.copytree(EXAMPLES, tmp_path / "rules")
    p = tmp_path / "rules" / name
    text = p.read_text(encoding="utf-8")
    assert old in text
    p.write_text(text.replace(old, new, 1), encoding="utf-8")
    return tmp_path / "rules"


@pytest.mark.parametrize(("name", "old", "new", "fragment"), [
    ("coherence_rules.yaml", '"Cette position dépasserait la limite de {limit} par titre prévue pour ton profil (valeur: {observed})."',
     "Cette position dépasse: {limit}", "entre guillemets"),
    ("coherence_rules.yaml", "metric: position_weight_after", "metric: poids_apres", "métrique inconnue « poids_apres »"),
    ("coherence_rules.yaml", "severity: high", "severity: tres_haut", "valeurs possibles"),
    ("relevance_rules.yaml", "earnings_results: 0.50, dividend: 0.60", "earnings_resultz: 0.50, dividend: 0.60",
     "catégorie absente de taxonomy.yaml"),
    ("relevance_rules.yaml", "add: 0.40", "add: beaucoup", "on attend un nombre"),
    ("relevance_rules.yaml", "field: position.sector", "field: position.secteur", "chemin inconnu « position.secteur »"),
    ("profile_rules.yaml", "  high:         {max_single_position: 0.25, max_high_vol_share: 0.60}\n", "",
     "niveaux de risque sans limites: high"),
    ("questionnaire.yaml", "sets: {horizon_years: 2}", "sets: {horizon: 2}", "champ « horizon » non modifiable"),
    ("personas/robert_portfolio.csv", "ZST.TO,20000", "ZST.TO;20000", "point-virgule"),
])
def test_validator_messages_are_readable(tmp_path: Path, name: str, old: str, new: str, fragment: str) -> None:
    rep = validate_rules.validate(_broken_dir(tmp_path, name, old, new))
    joined = "\n".join(rep.errors)
    assert fragment in joined, joined
    assert name.split("/")[-1] in joined


def test_validator_cli_exit_codes(tmp_path: Path) -> None:
    assert validate_rules.main(["--dir", str(EXAMPLES)]) == 0
    assert validate_rules.main(["--dir", str(tmp_path)]) == 0  # missing files: warnings only
    assert validate_rules.main(["--dir", str(tmp_path), "--strict"]) == 1
