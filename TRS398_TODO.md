# TRS398 Implementation TODO (from audit)

## A. Add TRS398 chamber constants (highest priority)
1. Extend the TRS-398 chamber database/schema to include **all 22 chambers** and the required Table 45 parameters:
   - `a`
   - `b`
   - `r_cav`
   - chamber `type`
   - `f_ch(60Co)` (and any other fields required by the existing code)
2. Current state (blocking): `data/seed/chamber_defaults.csv` only contains:
   - `chamber_type, ndw_60co, rcav_cm, reference_polarity`
   - **Missing**: `a`, `b`, `type`, `f_ch`
3. Update dataset loading code:
   - Modify `dosimetry_app/datasets.py` (function `get_chamber_defaults`) to return TRS398 parameters; or
   - Add a new function like `get_chamber_trs398_params()` and wire it into TRS398 mode.
4. Update TRS398 UI chamber panel (`pages/1_Calculator.py`) to display chamber parameters after selection:
   - show `a`, `b`, `r_cav` (plus `type` / `f_ch` if desired)

## B. Wire kQ fitting to chamber selection (spec compliance)
5. Update TRS398 kQ computation flow so that:
   - “Advanced k_Q fitting” uses **chamber-loaded** `a` and `b`
   - “Manual k_Q” overrides the computed value
6. Remove/avoid dependence on hardcoded session default `kq_a/kq_b` values unless user explicitly overrides them.
7. Add UI guardrails so users cannot accidentally compute TRS398 using mismatched kQ parameter sources.

## C. UI labeling alignment with TRS398 terminology
8. Ensure TRS398 labels and intermediate cards match the guide consistently:
   - `k_TP`, `k_s`, `k_pol`, `k_Q` (not TG-51 names like `P_TP`, `P_ion`, `P_pol`)
9. Ensure chamber parameter panel clearly labels:
   - `a`/`b` as **TRS398 fitting parameters**.

## D. Run record / audit fields (governance)
10. Enhance run record storage to include TRS398-specific metadata required by the guide (at minimum):
   - `protocol_mode: TRS-398`
   - `beam_quality_type: TPR20_10`
   - `beam_quality_value`
   - `T0_cert`, `P0_cert` used
   - `k_Q_computed`, `k_TP_computed`, `k_s_computed`, `k_pol_computed`
   - `chamber_a`, `chamber_b`, `chamber_r_cav`

## E. Validation & regression tests
11. Implement and/or run the TRS-398 validation tests from the guide (especially DS-03):
   - k_TP at reference conditions
   - k_Q for NE 2571 at TPR=0.670
   - full DS-03 calculation
12. Add regression checks to ensure TG-51 mode remains unchanged.

## F. Your additional requirement: “Manual KQ appears in TPR”
13. Clarify and implement the exact UX behavior requested:
   - likely means ensure the UI clearly links the chosen kQ mode (manual kQ vs fitted kQ via TPR20,10) so physicists don’t confuse TPR inputs vs kQ overrides.
   - Implement according to what “appears in TPR” means in your UI.

