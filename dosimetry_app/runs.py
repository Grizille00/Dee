from __future__ import annotations

from dosimetry_app.database import dump_json, execute, load_json, query_all, query_one


def record_run(
    user_id: int | None,
    username: str,
    beam_type: str,
    inputs: dict,
    outputs: dict,
    formula_name: str,
    formula_version: int,
    dataset_versions: dict,
) -> int:
    return execute(
        """
        INSERT INTO calculator_runs (
            user_id, username, beam_type, inputs_json, outputs_json,
            formula_name, formula_version, dataset_versions_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            username,
            beam_type,
            dump_json(inputs),
            dump_json(outputs),
            formula_name,
            formula_version,
            dump_json(dataset_versions),
        ),
    )


def list_runs(limit: int = 200) -> list[dict]:
    rows = query_all(
        """
        SELECT *
        FROM calculator_runs
        ORDER BY run_ts DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    for row in rows:
        row["inputs"] = load_json(row.get("inputs_json"), {})
        row["outputs"] = load_json(row.get("outputs_json"), {})
        row["dataset_versions"] = load_json(row.get("dataset_versions_json"), {})
    return rows


def get_run(run_id: int) -> dict | None:
    row = query_one("SELECT * FROM calculator_runs WHERE id = ?", (run_id,))
    if not row:
        return None
    row["inputs"] = load_json(row.get("inputs_json"), {})
    row["outputs"] = load_json(row.get("outputs_json"), {})
    row["dataset_versions"] = load_json(row.get("dataset_versions_json"), {})
    return row

