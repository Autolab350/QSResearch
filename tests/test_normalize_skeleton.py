import pytest

from strategy import Allocation, equal_weight, inverse_vol, normalize, parse_occ, propose

QQQ_PATIENT = """$QQQ
$756 CALLS
 EXPIRATION 10/2/2026
$.42 Entry AVG
@everyone

$754/$755 PT zone
I will advise you all to be PATIENT. HAVE NO FOMO, & wait for backtests to DCA
"""

SPY_LOTTO = """$SPY
$775 CALLS
 EXPIRATION 10/2/2026
$.3 Entry
high risk lotto, size for $0, or skip
$775 final zone pt
"""

QQQ_LUNCH = """$QQQ
$733 PUTS
 EXPIRATION 10/1/2026
$.35 Entry
please size 1/4 regular size initially and leave 3/4 for DCA room
we are entering “lunch time chop” period
"""

SPY_ROUND2 = """$SPY
$755 PUTS
 EXPIRATION 10/1/2026
$.27 Entry
rollout round 2
$757 pt 1
$755 pt 2
"""

TSLA_HOLD = """$TSLA
$375 CALLS
 EXPIRATION 10/2/2026
$.55 Entry
A hold of $359/$360 will then target $370, $372.5 and finally $375
"""


def test_skeleton_builds_occ_and_ceiling():
    it = normalize(QQQ_PATIENT)
    assert it.occ == "QQQ261002C00756000"
    assert it.entry_ceiling == 0.42
    assert it.right == "C" and it.strike == 756 and it.expiry == "2026-10-02"
    assert parse_occ(it.occ)["strike"] == 756.0


def test_patient_paste_sets_no_chase_and_band():
    it = normalize(QQQ_PATIENT)
    assert it.chase_allowed is False
    assert it.add_on == "premium_retrace"
    assert {"role": "band", "lo": 754.0, "hi": 755.0, "seq": 1} in it.levels


def test_speculative_paste_is_one_lot_flagged():
    it = normalize(SPY_LOTTO)
    assert it.speculative is True
    assert it.planned_total == 1 and it.base_qty == 1 and it.add_qty_room == 0
    assert it.occ == "SPY261002C00775000"


def test_fraction_and_session_window():
    it = normalize(QQQ_LUNCH, regular_size=4)
    assert it.base_qty == 1 and it.add_qty_room == 3 and it.planned_total == 4
    assert it.session_window == "midday"
    assert it.right == "P"


def test_round_two_and_ordered_targets():
    it = normalize(SPY_ROUND2)
    assert it.round == 2
    tgts = sorted((l["seq"], l["lo"]) for l in it.levels if l["role"] == "target")
    assert tgts == [(1, 757.0), (2, 755.0)]


def test_hold_band_and_target_ladder():
    it = normalize(TSLA_HOLD)
    hold = [l for l in it.levels if l["role"] == "hold"][0]
    assert (hold["lo"], hold["hi"]) == (359.0, 360.0)
    tg = [l["lo"] for l in sorted(it.levels, key=lambda l: l["seq"]) if l["role"] == "target"]
    assert tg == [370.0, 372.5, 375.0]


def test_propose_stands_down_without_premium():
    p = propose("$SPY\n$760 PUTS\nEXPIRATION 10/2/2026\n")
    assert p.status == "STAND_DOWN"
    assert propose(QQQ_PATIENT).status == "PROPOSE"


def test_no_ticker_raises():
    with pytest.raises(ValueError):
        normalize("buy some calls")


def test_equal_weight_sums_to_one():
    w = equal_weight(["spy", "QQQ", "IWM"])
    assert set(w) == {"SPY", "QQQ", "IWM"} and round(sum(w.values()), 6) == 1.0
    Allocation(w)


def test_inverse_vol_prefers_calm_name():
    calm = [100 + i * 0.1 for i in range(40)]
    wild = [100 + ((-1) ** i) * 3 + i * 0.1 for i in range(40)]
    w = inverse_vol({"CALM": calm, "WILD": wild})
    assert w["CALM"] > w["WILD"] and round(sum(w.values()), 6) == 1.0
