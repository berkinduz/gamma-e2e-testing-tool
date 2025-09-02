import os
import time
import logging
import json
import pathlib
import traceback
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from datetime import datetime
import sys


class BaseTestEngine:
    def __init__(self, project_config):
        self.project_config = project_config
        self.project_name = project_config.get("name", "Unknown")
        self.headless = os.getenv("HEADLESS", "0") == "1"
        self.console_min_level = os.getenv("CONSOLE_MIN_LEVEL", "WARNING")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, self.log_level, logging.INFO),
            format="%(asctime)s %(levelname)s %(message)s",
        )

        self.driver = None
        self.run_dir = None
        self.steps = []
        self.failure_occurred = False
        self.aborted_by_user = False

    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        chrome_opts = Options()
        if self.headless:
            chrome_opts.add_argument("--headless=new")
            chrome_opts.add_argument("--window-size=1400,1000")
            chrome_opts.add_argument("--force-device-scale-factor=1")
            chrome_opts.add_argument("--remote-debugging-port=0")
            chrome_opts.add_argument("--enable-logging")
            chrome_opts.add_argument("--v=1")

        chrome_opts.add_argument("--disable-gpu")
        chrome_opts.add_argument("--no-sandbox")
        chrome_opts.add_argument("--disable-dev-shm-usage")
        chrome_opts.add_argument("--disable-blink-features=AutomationControlled")

        if not self.headless:
            try:
                chrome_opts.add_experimental_option("detach", True)
            except Exception:
                pass

        chrome_opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_opts.add_experimental_option("useAutomationExtension", False)
        # Set user agent from project config or use default
        user_agent = self.project_config.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        chrome_opts.add_argument(f"--user-agent={user_agent}")

        # If normal mode, allow custom window size and devtools
        if not self.headless:
            try:
                bw = int(os.getenv("BROWSER_WIDTH", "1400"))
                bh = int(os.getenv("BROWSER_HEIGHT", "1000"))
                if bw > 200 and bh > 200:
                    chrome_opts.add_argument(f"--window-size={bw},{bh}")
            except Exception:
                pass
            if os.getenv("DEVTOOLS_OPEN", "0") == "1":
                chrome_opts.add_argument("--auto-open-devtools-for-tabs")

        try:
            chrome_opts.set_capability(
                "goog:loggingPrefs",
                {"browser": "ALL", "performance": "ALL", "driver": "ALL"},
            )
        except Exception:
            pass

        self.driver = webdriver.Chrome(options=chrome_opts)
        self.driver.set_page_load_timeout(120)

        # Enable CDP where possible (both modes)
        try:
            try:
                self.driver.execute_cdp_cmd("Network.enable", {})
                self.driver.execute_cdp_cmd("Performance.enable", {})
                logging.info("CDP Network and Performance monitoring enabled")
            except Exception as e:
                logging.warning(f"CDP commands failed: {e}")
        except Exception as e:
            logging.warning(f"Performance logging setup failed: {e}")

    def wait_element(self, selector, timeout=40, clickable=False):
        """Wait for element with a strict overall timeout, searching default and iframes."""
        deadline = time.monotonic() + timeout
        condition_fn = (
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            if clickable
            else EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )

        # First try in default content with the full remaining budget
        try:
            self.driver.switch_to.default_content()
            remaining = max(0.5, deadline - time.monotonic())
            wait = WebDriverWait(self.driver, remaining)
            return wait.until(condition_fn)
        except Exception:
            pass

        # Try within each iframe with a small slice of the remaining budget per frame
        try:
            self.driver.switch_to.default_content()
            frames = self.driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
            for frame in frames:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    self.driver.switch_to.frame(frame)
                    per_frame = max(0.5, min(3.0, remaining))
                    wait = WebDriverWait(self.driver, per_frame)
                    element = wait.until(condition_fn)
                    return element
                except Exception:
                    self.driver.switch_to.default_content()
                    continue
        except Exception:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

        element_type = "clickable element" if clickable else "element"
        raise TimeoutException(
            f"Selector '{selector}' not found within {timeout}s timeout. Expected: {element_type}"
        )

    def click_element(self, selector, timeout=40, scroll_first=True):
        """Click element reliably with retries within the timeout budget."""
        end_time = time.monotonic() + timeout
        last_err = None
        while time.monotonic() < end_time:
            try:
                remaining = max(0.5, end_time - time.monotonic())
                per_attempt = max(1, int(min(2, remaining)))
                element = self.wait_element(selector, per_attempt, clickable=True)
                if scroll_first:
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", element
                        )
                    except Exception:
                        pass
                    time.sleep(0.2)
                try:
                    element.click()
                except (
                    StaleElementReferenceException,
                    ElementClickInterceptedException,
                ):
                    # Re-find and try JS click as fallback
                    remaining = max(0.5, end_time - time.monotonic())
                    per_attempt = max(1, int(min(2, remaining)))
                    element = self.wait_element(selector, per_attempt, clickable=True)
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                    except Exception as e:
                        last_err = e
                        time.sleep(0.2)
                        continue
                return element
            except (
                StaleElementReferenceException,
                ElementClickInterceptedException,
                TimeoutException,
            ) as e:
                last_err = e
                time.sleep(0.2)
                continue
            except Exception as e:
                last_err = e
                time.sleep(0.2)
                continue
        # Exhausted timeout
        if isinstance(last_err, TimeoutException):
            raise TimeoutException(
                f"Selector '{selector}' not clickable within {timeout}s timeout. Expected: clickable element"
            )
        raise Exception(f"Failed to click selector '{selector}': {str(last_err)}")

    def fill_field(self, selector, value, timeout=40):
        """Fill input field"""
        element = self.wait_element(selector, timeout)
        element.clear()
        element.send_keys(value)
        return element

    def save_artifacts(self, tag):
        """Save debugging artifacts"""
        if not self.run_dir or self.driver is None:
            logging.warning(
                f"Cannot save artifacts: run_dir={self.run_dir}, driver={self.driver is not None}"
            )
            return

        # If the driver session is gone (e.g., browser closed), skip artifact capture quietly
        try:
            _ = getattr(self.driver, "session_id", None)
            # Accessing something trivial to trigger potential invalid session
            _ = self.driver.title if _ else None
        except Exception:
            logging.info("Skip artifacts: WebDriver session is not available (probably closed)")
            return

        pathlib.Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        base = os.path.join(self.run_dir, tag)

        logging.info(f"Saving artifacts with tag: {tag}")

        # Screenshot
        try:
            # Ensure we're on default content and the page had a moment to paint
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            # Small delay to allow headless compositor to paint
            time.sleep(0.25)
            # Best-effort readyState wait (short)
            try:
                for _ in range(5):
                    state = self.driver.execute_script(
                        "return document.readyState || 'interactive'"
                    )
                    if str(state).lower() == "complete":
                        break
                    time.sleep(0.1)
            except Exception:
                pass

            ok = self.driver.save_screenshot(f"{base}.png")
            if not ok:
                raise Exception("native screenshot returned False")
            logging.info(f"Screenshot saved: {base}.png")
        except Exception as e:
            logging.warning(f"Native screenshot failed: {e}. Trying CDP fallback...")
            # Fallback: CDP captureScreenshot (Chrome only)
            try:
                png_b64 = self.driver.execute_cdp_cmd(
                    "Page.captureScreenshot", {"format": "png", "fromSurface": True}
                ).get("data")
                if png_b64:
                    import base64

                    with open(f"{base}.png", "wb") as f:
                        f.write(base64.b64decode(png_b64))
                    logging.info(f"Screenshot saved via CDP: {base}.png")
                else:
                    logging.error("CDP captureScreenshot returned no data")
            except Exception as e2:
                logging.error(f"Failed to save screenshot via CDP: {e2}")

        # Page analysis (without saving full HTML)
        try:
            page_source = self.driver.page_source
            if page_source:
                # Simple page analysis without saving full HTML
                debug_info = {
                    "title": self.driver.title,
                    "current_url": self.driver.current_url,
                    "page_length": len(page_source),
                    "has_payment_fields": "cardNumber" in page_source
                    or "payment" in page_source.lower(),
                    "has_checkout_elements": "checkout" in page_source.lower(),
                    "has_cart_elements": "cart" in page_source.lower(),
                    "has_login_elements": "login" in page_source.lower()
                    or "email" in page_source.lower(),
                    "has_error_messages": any(
                        err in page_source.lower()
                        for err in ["error", "failed", "invalid", "not found"]
                    ),
                }

                with open(f"{base}-page-analysis.json", "w", encoding="utf-8") as f:
                    json.dump(debug_info, f, ensure_ascii=False, indent=2)
                logging.info(f"Page analysis saved: {base}-page-analysis.json")
        except Exception as e:
            logging.error(f"Failed to save page analysis: {e}")

        # Console logs (errors only) – always emit file, even if empty
        try:
            try:
                logs = self.driver.get_log("browser") or []
            except Exception:
                logs = []
            severe_logs = [
                entry
                for entry in logs
                if str(entry.get("level", "")).upper() in {"SEVERE", "ERROR"}
            ]
            with open(f"{base}-console.json", "w", encoding="utf-8") as f:
                json.dump(severe_logs, f, ensure_ascii=False, indent=2)
            logging.info(f"Console logs saved: {base}-console.json")
        except Exception as e:
            logging.error(f"Failed to save console logs: {e}")

        # Network errors only – always emit file (may be empty)
        try:
            try:
                perf_logs = self.driver.get_log("performance") or []
            except Exception:
                perf_logs = []
            errors = []
            for entry in perf_logs:
                try:
                    msg = json.loads(entry.get("message", "{}")).get("message", {})
                    method = msg.get("method")
                    params = msg.get("params", {})
                    if method == "Network.responseReceived":
                        response = params.get("response", {})
                        status = int(response.get("status", 0))
                        if status >= 400:
                            errors.append(
                                {
                                    "url": response.get("url"),
                                    "status": status,
                                    "statusText": response.get("statusText"),
                                    "mimeType": response.get("mimeType"),
                                }
                            )
                except Exception:
                    continue
            with open(f"{base}-network-errors.json", "w", encoding="utf-8") as f:
                json.dump(errors, f, ensure_ascii=False, indent=2)
            logging.info(f"Network errors saved: {base}-network-errors.json")
        except Exception as e:
            logging.error(f"Failed to save network errors: {e}")

        logging.info(f"Artifacts saved for tag: {tag}")

    def create_run_dir(self, test_type="checkout"):
        """Create timestamped run directory"""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = f"logs/{timestamp}-{test_type}"
        pathlib.Path(self.run_dir).mkdir(parents=True, exist_ok=True)
        return self.run_dir

    def execute_step(self, step_config):
        """Execute a single test step"""
        step_name = step_config.get("name", "Unknown Step")
        action = step_config.get("action")

        step_data = {"name": step_name, "action": action, "start": time.time()}

        try:
            logging.info(f"[{len(self.steps) + 1}] {step_name}")

            if action == "navigate":
                self.driver.get(step_config["url"])

            elif action == "click":
                selector = step_config["selector"]
                self.click_element(selector, step_config.get("timeout", 40))

            elif action == "fill":
                selector = step_config["selector"]
                value = step_config["value"]
                self.fill_field(selector, value, step_config.get("timeout", 40))

            elif action == "wait":
                selector = step_config["selector"]
                self.wait_element(selector, step_config.get("timeout", 40))

            elif action == "custom":
                # Execute custom function
                custom_func = step_config.get("function")
                if custom_func:
                    custom_func(self.driver, step_config)

            step_data.update({"end": time.time(), "status": "pass"})
            logging.info(f"✓ {step_name} completed")

        except Exception as e:
            step_data.update(
                {
                    "end": time.time(),
                    "status": "fail",
                    "error": getattr(e, "msg", str(e).split("Stacktrace:")[0].strip()),
                }
            )
            logging.error(f"✗ {step_name} failed: {step_data['error']}")

            # Detect user-aborted scenarios (closed window / invalid session)
            err_text = str(e).lower()
            if any(k in err_text for k in ["invalid session id", "chrome not reachable", "no such window"]):
                self.aborted_by_user = True
                # Do not attempt artifacts on abort
                self.steps.append(step_data)
                raise Exception("Aborted: browser closed by user")

            # Save artifacts on failure
            if self.driver:
                try:
                    tag = step_config.get(
                        "artifact_tag", step_name.lower().replace(" ", "-")
                    )
                    self.save_artifacts(f"{tag}-failed")
                except Exception as artifact_error:
                    logging.error(f"Failed to save step artifacts: {artifact_error}")
            self.failure_occurred = True

            # Check if this is a critical failure
            if step_config.get("critical", True):
                raise Exception(
                    f"Critical step failed: {step_name} - {step_data['error']}"
                )

        self.steps.append(step_data)
        return step_data

    def run_test(self, test_steps):
        """Run complete test with given steps"""
        overall_error_message = None

        try:
            # Setup
            self.create_run_dir()
            logging.info(f"RUN_DIR: {self.run_dir}")
            self.setup_driver()

            # Execute steps
            for step_config in test_steps:
                self.execute_step(step_config)

            logging.info("✅ All test steps completed successfully")

        except Exception as e:
            overall_error_message = getattr(
                e, "msg", str(e).split("Stacktrace:")[0].strip()
            )
            logging.error(f"❌ Test failed: {overall_error_message}")
            # Persist full traceback for debugging without spamming logs
            try:
                full_tb = traceback.format_exc()
                if self.run_dir:
                    with open(
                        os.path.join(self.run_dir, "error_details.txt"),
                        "a",
                        encoding="utf-8",
                    ) as f:
                        f.write("\n\n==== TRACEBACK ====\n")
                        f.write(full_tb)
            except Exception:
                pass

        finally:
            # Save test summary
            self.save_test_summary(overall_error_message)

            # Produce a final-failed set ONLY if no step-level artifacts were saved
            # (avoids duplicate screenshot/logs for the same failure).
            if (
                self.driver is not None
                and overall_error_message
                and not self.failure_occurred
                and not self.aborted_by_user
            ):
                try:
                    self.save_artifacts("final-failed")
                except Exception as artifact_error:
                    logging.error(f"Failed to save failure artifacts: {artifact_error}")

            # Save final artifacts only on full success (avoid duplicates)
            if (
                self.driver is not None
                and not self.failure_occurred
                and not overall_error_message
            ):
                try:
                    self.save_artifacts("final-success")
                except Exception as artifact_error:
                    logging.error(f"Failed to save final artifacts: {artifact_error}")

            # Cleanup
            if self.driver:
                try:
                    if self.headless or overall_error_message is None:
                        self.driver.quit()
                except Exception:
                    pass

    def save_test_summary(self, error_message=None):
        """Save test execution summary"""
        if not self.run_dir:
            return

        status = "aborted" if self.aborted_by_user else ("failed" if error_message else "passed")
        summary = {
            "project": self.project_name,
            "mode": "headless" if self.headless else "normal",
            "status": status,
            "error": None if self.aborted_by_user else error_message,
            "timestamp": datetime.now().isoformat(),
            "steps": self.steps,
            "total_steps": len(self.steps),
            "passed_steps": len([s for s in self.steps if s.get("status") == "pass"]),
            "failed_steps": len([s for s in self.steps if s.get("status") == "fail"]),
        }

        with open(
            os.path.join(self.run_dir, "summary.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        if error_message and not self.aborted_by_user:
            # Append basic error header; traceback (if any) appended earlier
            with open(
                os.path.join(self.run_dir, "error_details.txt"), "a", encoding="utf-8"
            ) as f:
                f.write(f"Test failed at: {datetime.now().isoformat()}\n")
                f.write(f"Project: {self.project_name}\n")
                f.write(f"Mode: {'headless' if self.headless else 'normal'}\n")
                f.write(f"Error: {error_message}\n")

        logging.info(f"📁 Test results saved to: {self.run_dir}")

        # Prune old runs to keep only the most recent N runs (default: 10)
        try:
            self.prune_old_runs(max_runs=int(os.getenv("LOGS_MAX_RUNS", "10")))
        except Exception as e:
            logging.warning(f"Log retention pruning failed: {e}")

    def prune_old_runs(self, max_runs: int = 10):
        """Keep only the latest max_runs directories in logs/; delete older ones."""
        logs_root = os.path.join(os.getcwd(), "logs")
        if not os.path.isdir(logs_root) or max_runs <= 0:
            return
        # Collect run directories
        entries = []
        for name in os.listdir(logs_root):
            full = os.path.join(logs_root, name)
            if os.path.isdir(full):
                try:
                    mtime = os.path.getmtime(full)
                    entries.append((mtime, full))
                except Exception:
                    continue
        # Sort newest first
        entries.sort(key=lambda x: x[0], reverse=True)
        # Delete older beyond max_runs
        for _, dir_path in entries[max_runs:]:
            try:
                shutil.rmtree(dir_path, ignore_errors=True)
                logging.info(f"🧹 Pruned old log directory: {dir_path}")
            except Exception as e:
                logging.warning(f"Failed to prune {dir_path}: {e}")
