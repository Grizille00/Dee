from __future__ import annotations

import ast
from typing import Any

from dosimetry_app.database import dump_json, execute, execute_transaction, load_json, query_all, query_one

ALLOWED_FUNCTIONS = {
    "abs": abs,
    "min": min,
    "max": max,
    "round": round,
}

ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.UAdd,
    ast.USub,
    ast.Constant,
    ast.Name,
    ast.Load,
    ast.Call,
)

DEFAULT_FORMULAS = [
    {
        "name": "dw_photon_default",
        "beam_type": "photon",
        "expression": "M_Q * N_Dw_60Co * k_Q * depth_factor",
        "variables": ["M_Q", "N_Dw_60Co", "k_Q", "depth_factor"],
        "units": {"output": "Gy per measurement"},
        "notes": "Default photon formula",
    },
    {
        "name": "dw_electron_default",
        "beam_type": "electron",
        "expression": "M_Q * N_Dw_60Co * k_ecal * k_R50 * P_Q_gr",
        "variables": ["M_Q", "N_Dw_60Co", "k_ecal", "k_R50", "P_Q_gr"],
        "units": {"output": "Gy per measurement"},
        "notes": "Default electron formula",
    },
]


def validate_formula_expression(expression: str, variables: list[str]) -> list[str]:
    errors: list[str] = []
    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        return [f"Invalid formula syntax: {exc.msg}"]

    allowed_names = set(variables) | set(ALLOWED_FUNCTIONS.keys())
    for node in ast.walk(parsed):
        if not isinstance(node, ALLOWED_NODES):
            errors.append(f"Unsupported expression element: {type(node).__name__}")
            continue

        if isinstance(node, ast.Name) and node.id not in allowed_names:
            errors.append(f"Variable '{node.id}' is not declared in variables list.")

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                errors.append("Only safe built-in functions are allowed (abs, min, max, round).")
            if node.keywords:
                errors.append("Keyword arguments are not allowed in formulas.")

    return sorted(set(errors))


def safe_eval_formula(expression: str, values: dict[str, Any]) -> float:
    parsed = ast.parse(expression, mode="eval")
    for node in ast.walk(parsed):
        if not isinstance(node, ALLOWED_NODES):
            raise ValueError(f"Unsupported expression node: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
                raise ValueError("Unsafe function call in expression.")
            if node.keywords:
                raise ValueError("Keyword args are not allowed.")
        if isinstance(node, ast.Name):
            if node.id not in values and node.id not in ALLOWED_FUNCTIONS:
                raise ValueError(f"Missing formula variable: {node.id}")

    scope = dict(ALLOWED_FUNCTIONS)
    scope.update(values)
    result = eval(compile(parsed, "<formula>", "eval"), {"__builtins__": {}}, scope)  # noqa: S307
    return float(result)


def _next_formula_version(name: str, beam_type: str) -> int:
    row = query_one(
        """
        SELECT COALESCE(MAX(version), 0) AS max_version
        FROM formulas
        WHERE name = ? AND beam_type = ?
        """,
        (name, beam_type),
    )
    return int(row["max_version"]) + 1 if row else 1


def create_formula(
    name: str,
    beam_type: str,
    expression: str,
    variables: list[str],
    units: dict[str, Any] | None,
    created_by: str,
    notes: str | None = None,
) -> tuple[int, list[str]]:
    version = _next_formula_version(name, beam_type)
    errors = validate_formula_expression(expression, variables)
    status = "invalid" if errors else "inactive"

    formula_id = execute(
        """
        INSERT INTO formulas (
            name, beam_type, expression, variables_json, units_json,
            status, validation_errors_json, version, notes, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            beam_type,
            expression,
            dump_json(variables),
            dump_json(units or {}),
            status,
            dump_json(errors),
            version,
            notes,
            created_by,
        ),
    )
    return formula_id, errors


def list_formulas(beam_type: str | None = None) -> list[dict]:
    if beam_type:
        rows = query_all(
            """
            SELECT *
            FROM formulas
            WHERE beam_type = ?
            ORDER BY beam_type, name, version DESC
            """,
            (beam_type,),
        )
    else:
        rows = query_all(
            """
            SELECT *
            FROM formulas
            ORDER BY beam_type, name, version DESC
            """
        )

    for row in rows:
        row["variables"] = load_json(row.get("variables_json"), [])
        row["units"] = load_json(row.get("units_json"), {})
        row["validation_errors"] = load_json(row.get("validation_errors_json"), [])
    return rows


def activate_formula(formula_id: int) -> None:
    formula = query_one("SELECT * FROM formulas WHERE id = ?", (formula_id,))
    if not formula:
        raise ValueError("Formula not found.")
    if formula["status"] == "invalid":
        raise ValueError("Invalid formulas cannot be activated.")

    execute_transaction(
        [
            ("UPDATE formulas SET status = 'inactive' WHERE beam_type = ?", (formula["beam_type"],)),
            ("UPDATE formulas SET status = 'active' WHERE id = ?", (formula_id,)),
        ]
    )


def get_active_formula(beam_type: str) -> dict | None:
    row = query_one(
        """
        SELECT *
        FROM formulas
        WHERE beam_type = ? AND status = 'active'
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (beam_type,),
    )
    if not row:
        return None

    row["variables"] = load_json(row.get("variables_json"), [])
    row["units"] = load_json(row.get("units_json"), {})
    row["validation_errors"] = load_json(row.get("validation_errors_json"), [])
    return row


def seed_default_formulas() -> None:
    for default in DEFAULT_FORMULAS:
        existing = query_one(
            """
            SELECT id
            FROM formulas
            WHERE beam_type = ? AND status = 'active'
            LIMIT 1
            """,
            (default["beam_type"],),
        )
        if existing:
            continue

        formula_id, errors = create_formula(
            name=default["name"],
            beam_type=default["beam_type"],
            expression=default["expression"],
            variables=default["variables"],
            units=default["units"],
            created_by="system",
            notes=default["notes"],
        )
        if errors:
            continue
        activate_formula(formula_id)

