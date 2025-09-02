#!/usr/bin/env python3
"""
JSON Flow Runner: Allows non-Python users to define tests as JSON files with TEST_STEPS.
Usage: python tests/json_runner.py path/to/flow.json PROJECT_NAME
Backwards compatible with TARGET/BRAND inputs.
"""

import os
import sys
import json

# Ensure project root on path
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tests.base_test_engine import BaseTestEngine


def normalize_prefix(name: str) -> str:
    return (name or "").upper().replace("-", "_").replace(" ", "_")


def _validate_flow_json(data: dict) -> list:
    """Return a list of human-friendly error messages if JSON is invalid."""
    errors = []
    if not isinstance(data, dict):
        return ["Flow root must be an object"]

    project = data.get("PROJECT_CONFIG") or data.get("TARGET_CONFIG") or data.get("BRAND_CONFIG")
    if not isinstance(project, dict):
        errors.append("PROJECT_CONFIG must be an object")
    else:
        name = project.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append("PROJECT_CONFIG.name is required and must be non-empty string")

    steps = data.get("TEST_STEPS")
    if not isinstance(steps, list) or len(steps) == 0:
        errors.append("TEST_STEPS must be a non-empty array")
        return errors

    for idx, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            errors.append(f"Step {idx}: must be an object")
            continue
        name = step.get("name")
        action = step.get("action")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"Step {idx}: 'name' is required")
        if action not in {"navigate", "click", "fill", "wait", "custom"}:
            errors.append(f"Step {idx}: 'action' must be one of navigate/click/fill/wait/custom")
            continue
        if action == "navigate" and not (isinstance(step.get("url"), str) and step.get("url").strip()):
            errors.append(f"Step {idx}: 'url' is required for action=navigate")
        if action in {"click", "wait", "fill"} and not (isinstance(step.get("selector"), str) and step.get("selector").strip()):
            errors.append(f"Step {idx}: 'selector' is required for action={action}")
        if action == "fill" and not (isinstance(step.get("value"), str)):
            errors.append(f"Step {idx}: 'value' is required for action=fill")
        timeout = step.get("timeout", 40)
        if timeout is not None and not (isinstance(timeout, int) and timeout > 0):
            errors.append(f"Step {idx}: 'timeout' must be a positive integer if provided")
    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: json_runner.py <flow.json> [PROJECT_NAME]")
        sys.exit(1)
    json_path = sys.argv[1]
    project_name = (
        sys.argv[2]
        if len(sys.argv) > 2
        else os.getenv("PROJECT", os.getenv("TARGET", os.getenv("BRAND", "UNKNOWN")))
    )

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Minimal validation before running
    validation_errors = _validate_flow_json(data)
    if validation_errors:
        print("Invalid flow JSON:")
        for err in validation_errors:
            print(f" - {err}")
        sys.exit(2)

    project_config = data.get("PROJECT_CONFIG", data.get("TARGET_CONFIG", data.get("BRAND_CONFIG", {})))
    if "name" not in project_config:
        project_config["name"] = project_name

    # Generic env injection for any project
    prefix = normalize_prefix(project_name or project_config.get("name", ""))
    default_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    project_config.setdefault("email", os.getenv(f"{prefix}_EMAIL", ""))
    project_config.setdefault("password", os.getenv(f"{prefix}_PASSWORD", ""))
    project_config.setdefault("user_agent", os.getenv(f"{prefix}_USER_AGENT", default_ua))

    test_steps = data.get("TEST_STEPS", [])
    if not isinstance(test_steps, list) or not test_steps:
        print("No TEST_STEPS found in JSON flow")
        sys.exit(2)

    # Resolve special tokens in step values
    resolved_steps = []
    for step in test_steps:
        st = dict(step)
        if st.get("action") == "fill":
            val = st.get("value")
            if isinstance(val, str):
                if val == "$EMAIL":
                    st["value"] = project_config.get("email", "")
                elif val == "$PASSWORD":
                    st["value"] = project_config.get("password", "")
        resolved_steps.append(st)

    engine = BaseTestEngine(project_config)
    engine.run_test(resolved_steps)


if __name__ == "__main__":
    main()
