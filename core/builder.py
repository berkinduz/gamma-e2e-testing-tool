import os
import json
import re
import tkinter as tk
import tkinter.simpledialog as simpledialog
import tkinter.messagebox as messagebox


def refresh_flows_for_project(app, project_name: str) -> None:
    """Populate flow combobox with python files under the project's directory"""
    project_cfg = app.projects.get(project_name)
    if not project_cfg:
        return
    flow_dir = project_cfg.get("dir")
    flows = []
    label_to_path = {}
    if flow_dir and os.path.isdir(flow_dir):
        for fn in sorted(os.listdir(flow_dir)):
            # Support Python tests and JSON test definitions
            if (fn.endswith(".py") or fn.endswith(".json")) and fn != "__init__.py":
                label = os.path.splitext(fn)[0]
                full_path = os.path.join(flow_dir, fn)
                flows.append(label)
                label_to_path[label] = full_path
    if hasattr(app, "flow_combo"):
        app.flow_combo["values"] = flows
        current = getattr(app, "flow_var", tk.StringVar()).get()
        if current in flows:
            app.flow_combo.set(current)
        elif flows:
            last = app.prefs.get("flow", "") if isinstance(app.prefs, dict) else ""
            choose = last if last in flows else flows[0]
            app.flow_combo.set(choose)
            app.flow_var.set(choose)
        else:
            try:
                app.flow_combo.set("")
                app.flow_var.set("")
            except Exception:
                pass
    # Save map for run resolution
    app.flow_map[project_name] = label_to_path
    # Reflect availability in start button
    app.update_button_states()


def _normalize_project_folder(name: str) -> str:
    try:
        s = (name or "").strip()
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"[^A-Za-z0-9_-]", "", s)
        return s.lower()[:50] or "project"
    except Exception:
        return "project"


def refresh_all_project_combos(app, select_project: str | None = None) -> None:
    try:
        keys = list(app.projects.keys())
        if hasattr(app, "project_combo"):
            app.project_combo["values"] = keys
        if hasattr(app, "builder_project_combo"):
            app.builder_project_combo["values"] = keys
        if select_project and select_project in app.projects:
            app.project_var.set(select_project)
            app.builder_project_var.set(select_project)
            refresh_flows_for_project(app, select_project)
    except Exception:
        pass


def builder_create_new_project(app) -> None:
    try:
        name = simpledialog.askstring(
            "New Project", "Project name (e.g., SHOP):", parent=app.root
        )
        if not name or not name.strip():
            return
        folder = _normalize_project_folder(name)
        proj_root = os.path.join("tests", "projects")
        os.makedirs(proj_root, exist_ok=True)
        target_dir = os.path.join(proj_root, folder)
        if os.path.exists(target_dir):
            messagebox.showinfo("Info", f"Project already exists: {folder}")
        else:
            os.makedirs(target_dir, exist_ok=True)

        app.projects = app.discover_projects()
        select_key = folder
        refresh_all_project_combos(app, select_key)
        app.add_log(f"✅ Project created: {select_key}", "success")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create project: {e}")


def builder_add_step(app) -> None:
    try:
        action = app.step_action_var.get().strip()
        target = app.step_target_var.get().strip()
        value = app.step_value_var.get().strip()
        timeout = app.step_timeout_var.get().strip()
        # Reset previous error
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set("")
        # Validations
        if action == "navigate" and not target:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set("❌ URL is required for navigate action")
            else:
                app.builder_status_var.set("URL is required for navigate")
            return
        if action in ("click", "fill", "wait") and not target:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set(
                    "❌ Selector is required for click/fill/wait actions"
                )
            else:
                app.builder_status_var.set("Selector is required")
            return
        if action == "fill" and not value:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set("❌ Value is required for fill action")
            else:
                app.builder_status_var.set("Value is required for fill")
            return
        try:
            timeout_int = int(timeout) if timeout else 40
        except ValueError:
            timeout_int = 40

        # Generate name & artifact_tag (robust for selectors like [data-attr])
        short = _shorten_selector_for_name(target)
        if action == "navigate":
            name = f"Navigate to {target[:50]}"
        else:
            name = f"{action.capitalize()} {short}"
        slug = name.lower().replace(" ", "-").replace("/", "-")[:40]

        step = {
            "name": name,
            "action": action,
            ("url" if action == "navigate" else "selector"): target,
        }
        if action == "fill":
            step["value"] = value
        step["timeout"] = timeout_int
        step["critical"] = True
        step["artifact_tag"] = slug

        # Render in listbox
        app.steps_listbox.insert(tk.END, json.dumps(step))
        app.builder_status_var.set("✅ Step added successfully")
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set("")
        # Clear inputs for next step
        app.step_target_var.set("")
        if action == "fill":
            app.step_value_var.set("")
        # Focus back to selector/url for fast entry
        try:
            app.step_target_entry.focus_set()
        except Exception:
            pass
    except Exception as e:
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set(f"❌ Failed to add step: {e}")
        else:
            app.builder_status_var.set(f"Failed to add step: {e}")


def builder_remove_selected(app) -> None:
    try:
        sel = app.steps_listbox.curselection()
        if not sel:
            return
        app.steps_listbox.delete(sel[0])
        app.builder_status_var.set("Removed")
    except Exception as e:
        app.builder_status_var.set(f"Failed to remove: {e}")


def builder_save_flow(app) -> None:
    try:
        project = app.builder_project_var.get().strip()
        flow = app.builder_flow_var.get().strip()
        # Reset error
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set("")
        # Basic validations
        if not project or not flow:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set("❌ Project and flow name are required")
            else:
                app.builder_status_var.set("Project and flow name are required")
            return
        steps = []
        for i in range(app.steps_listbox.size()):
            raw = app.steps_listbox.get(i)
            steps.append(json.loads(raw))
        if not steps:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set(
                    "❌ At least one step is required before saving"
                )
            else:
                app.builder_status_var.set("At least one step is required")
            return

        flow_obj = {"PROJECT_CONFIG": {"name": project}, "TEST_STEPS": steps}

        # Minimal validation before saving
        errors = _validate_flow_data(flow_obj)
        if errors:
            if hasattr(app, "builder_error_var"):
                app.builder_error_var.set("\n".join([f"- {e}" for e in errors]))
            app.builder_status_var.set("")
            return
        # Map project selection to actual folder key
        project_key = project
        if project_key not in app.projects:
            # Try case-insensitive match to folder keys
            for k in app.projects.keys():
                if k.lower() == project.lower():
                    project_key = k
                    break
        project_dir = os.path.join("tests", "projects", project_key)
        os.makedirs(project_dir, exist_ok=True)
        file_path = os.path.join(project_dir, f"{flow}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(flow_obj, f, ensure_ascii=False, indent=2)

        app.builder_status_var.set(f"✅ Saved: {os.path.basename(file_path)}")
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set("")
        # Refresh flows in header ONLY if builder project matches current header project
        current_project = app.project_var.get()
        if current_project.lower() == project.lower():
            refresh_flows_for_project(app, project_key)
            # Auto-select the newly saved flow in header
            try:
                app.flow_var.set(flow)
                if hasattr(app, "flow_combo"):
                    app.flow_combo.set(flow)
                app._save_prefs()
            except Exception:
                pass
    except Exception as e:
        if hasattr(app, "builder_error_var"):
            app.builder_error_var.set(f"❌ Failed to save: {e}")
        else:
            app.builder_status_var.set(f"Failed to save: {e}")


def _shorten_selector_for_name(selector: str) -> str:
    """Create a readable short label from a CSS selector without leaving dangling characters.
    Examples:
    - '#btn-primary > span' -> '#btn-primary'
    - '.card .title' -> '.card'
    - "[data-test='submit']" -> "[data-test='submit']"
    - 'div[role=button]' -> 'div[role=button]'
    - '' or None -> ''
    """
    try:
        if not selector:
            return ""
        s = selector.strip()
        # Prefer id or class token at start
        m = re.match(r"^[#.][A-Za-z0-9_-]+", s)
        if m:
            return m.group(0)
        # Attribute selector at start: capture up to matching ]
        m = re.match(r"^\[[^\]]{1,60}\]", s)
        if m:
            return m.group(0)
        # Tag with attribute: capture like div[role=button]
        m = re.match(r"^[A-Za-z0-9_-]+\[[^\]]{1,60}\]", s)
        if m:
            return m.group(0)
        # Otherwise take first token until space, '>' or ','
        cut = re.split(r"\s|>|,", s, maxsplit=1)[0]
        return cut[:60]
    except Exception:
        return (selector or "")[:30]


def builder_on_action_change(app) -> None:
    try:
        action = app.step_action_var.get().strip()
        if action == "navigate":
            app.step_target_label.configure(text="URL")
            # Hide value field, show spacer so Add button stays visible
            try:
                app.step_value_label.grid_remove()
                app.step_value_entry.grid_remove()
                app.step_value_spacer.grid(row=0, column=4, columnspan=2, sticky="w")
            except Exception:
                pass
        elif action == "fill":
            app.step_target_label.configure(text="Selector")
            # Show value field
            try:
                app.step_value_spacer.grid_remove()
                app.step_value_label.grid(row=0, column=4, sticky="w")
                app.step_value_entry.grid(row=0, column=5, padx=(6, 12))
            except Exception:
                pass
            app.step_value_entry.configure(state=tk.NORMAL)
        else:
            app.step_target_label.configure(text="Selector")
            # Hide value field, show spacer so Add button stays visible
            try:
                app.step_value_label.grid_remove()
                app.step_value_entry.grid_remove()
                app.step_value_spacer.grid(row=0, column=4, columnspan=2, sticky="w")
            except Exception:
                pass
    except Exception:
        pass


def _validate_flow_data(flow_obj: dict):
    errors = []
    if not isinstance(flow_obj, dict):
        return ["Flow root must be an object"]
    project = (
        flow_obj.get("PROJECT_CONFIG")
        or flow_obj.get("TARGET_CONFIG")
        or flow_obj.get("BRAND_CONFIG")
    )
    if not isinstance(project, dict):
        errors.append("PROJECT_CONFIG must be an object")
    else:
        name = project.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append("PROJECT_CONFIG.name is required and must be non-empty")
    steps = flow_obj.get("TEST_STEPS")
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
            errors.append(
                f"Step {idx}: 'action' must be one of navigate/click/fill/wait/custom"
            )
            continue
        if action == "navigate" and not (
            isinstance(step.get("url"), str) and step.get("url").strip()
        ):
            errors.append(f"Step {idx}: 'url' is required for action=navigate")
        if action in {"click", "wait", "fill"} and not (
            isinstance(step.get("selector"), str) and step.get("selector").strip()
        ):
            errors.append(f"Step {idx}: 'selector' is required for action={action}")
        if action == "fill" and not isinstance(step.get("value"), str):
            errors.append(f"Step {idx}: 'value' is required for action=fill")
        timeout = step.get("timeout", 40)
        if timeout is not None:
            try:
                t = int(timeout)
                if t <= 0:
                    errors.append(f"Step {idx}: 'timeout' must be > 0")
            except Exception:
                errors.append(f"Step {idx}: 'timeout' must be a positive integer")
    return errors
