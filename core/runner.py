import os
import threading
import subprocess
import json
import time
from datetime import datetime
import tkinter as tk


def start_test(app) -> None:
    """Start the test execution"""
    if app.test_running:
        return

    app.test_running = True

    # Update button states
    app.update_button_states()

    # Clear logs
    app.logs_text.delete(1.0, tk.END)

    # Start test in thread
    test_thread = threading.Thread(target=run_test_process, args=(app,), daemon=True)
    test_thread.start()
    # Ensure Logs tab is visible when starting
    try:
        app.notebook.select(0)
    except Exception:
        pass


def run_test_process(app) -> None:
    """Run the actual test process with proper artifact saving"""
    try:
        # Set environment variables
        env = os.environ.copy()
        env["HEADLESS"] = "1" if app.mode_var.get() == "headless" else "0"
        env["CONSOLE_MIN_LEVEL"] = "WARNING"

        # Get project and script details
        project_name = app.project_var.get()
        project_config = app.projects.get(project_name)

        if not project_config:
            app.add_log(
                f"❌ Project '{project_name}' not found in configuration.", "error"
            )
            app.test_running = False
            app.update_button_states()
            return

        # Determine script: either selected flow file or default script
        selected_flow = app.flow_var.get() if hasattr(app, "flow_var") else ""
        script_path = project_config["script"]
        if selected_flow:
            # Resolve label to full path via flow_map
            script_path = app.flow_map.get(project_name, {}).get(
                selected_flow, project_config["script"]
            )

        # Check if script exists
        if not os.path.exists(script_path):
            app.add_log(
                f"❌ Test script '{script_path}' not found for project '{project_name}'.",
                "error",
            )
            app.test_running = False
            app.update_button_states()
            return

        env["PROJECT"] = project_name  # Set the generic project for the test script
        # Ensure project root is on PYTHONPATH for 'tests' package imports
        try:
            project_root = os.path.abspath(os.path.dirname(__file__))
            existing_pp = env.get("PYTHONPATH", "")
            sep = ":" if os.name != "nt" else ";"
            env["PYTHONPATH"] = (
                project_root if not existing_pp else f"{project_root}{sep}{existing_pp}"
            )
        except Exception:
            pass
        # Only set non-empty values from project_config to avoid overriding real envs with blanks
        for key, value in project_config["env_vars"].items():
            if isinstance(value, str) and value.strip() == "":
                continue
            if value is None:
                continue
            env[key] = value

        # Log test start
        app.add_log(
            f"🚀 Starting {project_name} project test in {app.mode_var.get()} mode...",
            "info",
        )
        app.add_log(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "timestamp")
        app.add_log("-" * 50, "info")

        # Determine runner: json vs python
        cmd = ["python3", script_path]
        if script_path.endswith(".json"):
            cmd = ["python3", "tests/json_runner.py", script_path, project_name]

        # Run the test
        app.test_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Start log consumer thread
        app.log_thread = threading.Thread(
            target=consume_test_logs, args=(app,), daemon=True
        )
        app.log_thread.start()

    except Exception as e:
        app.add_log(f"❌ Error: {str(e)}", "error")
        app.test_running = False
        app.update_button_states()


def consume_test_logs(app) -> None:
    """Consume test output in a separate thread"""
    try:
        test_failed = False
        error_message = None

        for line in iter(app.test_process.stdout.readline, ""):
            if line:
                line_text = line.strip()

                # Detect test failures using stricter rules to avoid false positives like
                # "Network errors saved" (which is informational).
                normalized = line_text.strip()
                lower = normalized.lower()
                is_explicit_fail = (
                    normalized.startswith("✗")
                    or normalized.startswith("❌")
                    or "] ERROR" in normalized
                    or normalized.startswith("ERROR")
                    or " critical step failed" in lower
                    or "selector" in lower
                    and "not found" in lower
                    or "timeout" in lower
                    and ("failed" in lower or "selector" in lower)
                )
                if is_explicit_fail:
                    test_failed = True
                    error_message = line_text
                    app.add_log(line_text, "error")
                    # Do NOT kill the subprocess; let the test engine finish and write artifacts
                elif "warning" in line_text.lower():
                    app.add_log(line_text, "warning")
                else:
                    app.add_log(line_text, "info")

        # Wait for completion (let the engine write artifacts in finally)
        app.test_process.wait()

        # Determine final status
        if test_failed or app.test_process.returncode != 0:
            app.add_log("❌ Test failed!", "error")
            app.status_label.config(text="Failed", fg=app.colors["danger"])
            test_status = "failed"
        else:
            app.add_log("✅ Test completed successfully!", "success")
            app.status_label.config(text="Completed", fg=app.colors["success"])
            test_status = "ok"

        # Create test summary
        project_name = app.project_var.get()  # Get project name for summary
        create_test_summary(app, test_status, error_message, project_name)

        # Update UI
        app.test_running = False
        app.update_button_states()
        app.refresh_results()
        try:
            # Append clickable link to results at the end of logs, then newline
            app.logs_text.insert(tk.END, "\nClick to see results", ("link",))
            app.logs_text.insert(tk.END, "\n")
            app.logs_text.see(tk.END)
        except Exception:
            pass

    except Exception as e:
        app.add_log(f"❌ Error in log consumer: {str(e)}", "error")
        app.test_running = False
        app.update_button_states()


def create_test_summary(app, status, error_message=None, project_name=None):
    """Create a test summary file with proper artifacts"""
    try:
        # Prefer run dir printed by the test (RUN_DIR: ...)
        logs_text = app.logs_text.get(1.0, tk.END)
        log_dir = None
        for line in logs_text.split("\n"):
            if "RUN_DIR:" in line:
                candidate = line.split("RUN_DIR:")[1].strip()
                if os.path.isdir(candidate):
                    log_dir = candidate
                    break

        # Fallback to timestamped dir if RUN_DIR not found
        test_start_time = datetime.now()
        if not log_dir:
            timestamp = test_start_time.strftime("%Y%m%d-%H%M%S")
            log_dir = f"logs/{timestamp}-checkout"
            os.makedirs(log_dir, exist_ok=True)

        # Get logs from the text widget
        log_content = app.logs_text.get(1.0, tk.END).strip()

        # Calculate test duration from summary or logs
        duration = calculate_test_duration(log_content, log_dir)

        # Create summary data with error details
        summary = {
            "status": status,
            "project": project_name or app.project_var.get(),
            "mode": app.mode_var.get(),
            "headless": app.mode_var.get() == "headless",
            "durationSec": duration,
            "timestamp": test_start_time.isoformat(),
            "logLines": len(log_content.split("\n")) if log_content else 0,
            "error": error_message if error_message else None,
        }

        # Save summary.json
        summary_path = os.path.join(log_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Save raw logs
        log_path = os.path.join(log_dir, "test_log.txt")
        with open(log_path, "w") as f:
            f.write(log_content)

        # Save test artifacts if test failed
        if status == "failed" and error_message:
            # Create error details file
            error_path = os.path.join(log_dir, "error_details.txt")
            with open(error_path, "w") as f:
                f.write(f"Test failed at: {test_start_time.isoformat()}\n")
                f.write(f"Error: {error_message}\n")
                f.write(f"Project: {project_name or app.project_var.get()}\n")
                f.write(f"Mode: {app.mode_var.get()}\n")
                f.write(f"Duration: {duration:.1f} seconds\n")
                f.write("\nFull Log:\n")
                f.write("-" * 50 + "\n")
                f.write(log_content)

        app.add_log(f"📁 Test results saved to: {log_dir}", "info")

        # Auto-refresh both results and history tabs
        app.root.after(1000, app.auto_refresh_all_tabs)

    except Exception as e:
        app.add_log(f"❌ Error saving test summary: {str(e)}", "error")


def calculate_test_duration(log_content, log_dir=None):
    """Calculate test duration from summary.json or log timestamps"""
    try:
        # First try to get duration from summary.json
        if log_dir:
            summary_path = os.path.join(log_dir, "summary.json")
            if os.path.exists(summary_path):
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
                    steps = summary.get("steps", [])
                    if steps:
                        # Calculate total duration from first start to last end
                        start_times = [
                            step.get("start", 0) for step in steps if "start" in step
                        ]
                        end_times = [
                            step.get("end", 0) for step in steps if "end" in step
                        ]
                        if start_times and end_times:
                            first_start = min(start_times)
                            last_end = max(end_times)
                            if first_start and last_end:
                                return max(last_end - first_start, 1)

        # Fallback to log parsing
        lines = log_content.split("\n")
        timestamps = []

        for line in lines:
            if line.startswith("[") and "]" in line:
                time_str = line.split("]")[0][1:]  # Extract time part
                try:
                    # Parse HH:MM:SS format
                    time_parts = time_str.split(":")
                    if len(time_parts) == 3:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        seconds = int(time_parts[2])
                        total_seconds = hours * 3600 + minutes * 60 + seconds
                        timestamps.append(total_seconds)
                except:
                    continue

        if len(timestamps) >= 2:
            duration = timestamps[-1] - timestamps[0]
            # Handle day rollover (rough estimate)
            if duration < 0:
                duration += 24 * 3600
            return max(duration, 1)  # At least 1 second
        else:
            return 1  # Default duration

    except:
        return 1  # Default duration


def stop_test(app) -> None:
    """Stop the running test"""
    if app.test_process and app.test_running:
        try:
            app.test_process.terminate()
            app.add_log("🛑 Test stopped by user", "warning")
            app.status_label.config(text="Stopped", fg=app.colors["warning"])
        except:
            pass

    app.test_running = False
    app.update_button_states()


def add_log(app, message, tag="info"):
    """Add a log message to the logs text widget"""
    if not hasattr(app, "logs_text") or not app.logs_text.winfo_exists():
        return

    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"

        app.logs_text.insert(tk.END, formatted_message, tag)
        if hasattr(app, "auto_scroll_var") and app.auto_scroll_var.get():
            app.logs_text.see(tk.END)
        app.root.update_idletasks()
    except Exception as e:
        print(f"Error in add_log: {e}")  # Debug print instead of GUI log


def clear_logs(app) -> None:
    """Clear the logs text widget"""
    app.logs_text.delete(1.0, tk.END)
    app.add_log("🗑️ Logs cleared", "info")
