# How to Create Tests (No Python Required)

You can add tests by dropping a JSON file; no coding needed. Advanced users can still write Python.

## Folder Structure

```
tests/
├── base_test_engine.py          # Shared test engine
├── projects/                    # Generic project-specific tests
│   ├── google/
│   │   ├── GOOGLE_HOMEPAGE.json         # Google homepage test
│   │   └── GOOGLE_SEARCH.json           # Google search test (future)
│   ├── example/
│   │   ├── EXAMPLE_SMOKE.json           # Example.com smoke test
│   │   └── EXAMPLE_BROWSE.json          # Example.com browse test (future)
│   ├── newproject/
│   │   └── NEWPROJECT_CHECKOUT.json     # New project example
│   └── newproject/               # New project example
│       ├── checkout.py         # Checkout test
│       ├── search.py           # Search test
│       └── login.py            # Login test
```

## Test Types & Flows

Tests can cover different user journeys:

- **Guest Flow**: User without account (like Example.com)
- **Logged-in Flow**: User with existing account (like Google)
- **Mixed Flow**: Starts guest, converts to logged-in
- **Functional Tests**: Search, browse, filter, etc.
- **Performance Tests**: Load time, responsiveness
- **Integration Tests**: Payment, shipping, etc.

## Option A: JSON Flows (Recommended for non‑developers)

Place a JSON file under `tests/projects/<PROJECT>/<FLOW>.json`:

```json
{
  "PROJECT_CONFIG": { "name": "MY_SHOP", "url": "https://shop.example" },
  "TEST_STEPS": [
    { "name": "Go", "action": "navigate", "url": "https://google.com" },
    {
      "name": "Wait tile",
      "action": "wait",
      "selector": "#tile-image-0 a",
      "timeout": 40
    },
    { "name": "Open PDP", "action": "click", "selector": "#tile-image-0 a" },
    {
      "name": "Email",
      "action": "fill",
      "selector": "#email",
      "value": "$EMAIL"
    },
    {
      "name": "Password",
      "action": "fill",
      "selector": "#password",
      "value": "$PASSWORD"
    },
    { "name": "Submit", "action": "click", "selector": "#submit-button" },
    {
      "name": "Wait payment",
      "action": "wait",
      "selector": "#cardNumber",
      "timeout": 40,
      "critical": true
    }
  ]
}
```

Notes:

- `$EMAIL` and `$PASSWORD` are auto‑replaced from your `.env` using project prefix rules below.
- Supported actions: `navigate`, `click`, `fill`, `wait`.
- Optional keys: `timeout` (default 40), `critical` (default true), `artifact_tag`.

Env var naming:

- Project folder name becomes the prefix: `MY_SHOP` → `MY_SHOP_EMAIL`, `MY_SHOP_PASSWORD`, `MY_SHOP_USER_AGENT`.
- Dashes/spaces are converted to underscores.

Run it from the GUI: Project is auto‑discovered, Flow shows your JSON file.

## Option B: Python (Advanced)

Each test defines a `TEST_STEPS: list[dict]`. Supported actions:

Each test defines a `TEST_STEPS: list[dict]`. Supported actions:

### Basic Actions

- **`navigate`**: Go to URL

  ```python
  {
      "name": "Navigate to homepage",
      "action": "navigate",
      "url": BRAND_CONFIG["url"]
  }
  ```

- **`click`**: Click element

  ```python
  {
      "name": "Click add to cart",
      "action": "click",
      "selector": ".add-to-cart-btn",
      "timeout": 40,
      "artifact_tag": "add-to-cart"
  }
  ```

- **`fill`**: Fill input field

  ```python
  {
      "name": "Enter email",
      "action": "fill",
      "selector": "#email",
      "value": PROJECT_CONFIG["email"],
      "timeout": 10
  }
  ```

- **`wait`**: Wait for element

  ```python
  {
      "name": "Wait for payment form",
      "action": "wait",
      "selector": "#cardNumber",
      "timeout": 40,
      "critical": True,
      "artifact_tag": "payment-form"
  }
  ```

- **`custom`**: Execute custom function
  ```python
  {
      "name": "Custom validation",
      "action": "custom",
      "function": "validate_page_state"
  }
  ```

### Step Properties

- `name`: Human-readable step description
- `action`: Action type (navigate, click, fill, wait, custom)
- `selector`: CSS selector for element (except navigate)
- `timeout`: Maximum wait time in seconds (default: 40)
- `critical`: Stop test on failure (default: True)
- `artifact_tag`: Name for screenshots/logs on failure
- `url`: Target URL (navigate action only)
- `value`: Input value (fill action only)

## Project Configuration

Each test includes a `PROJECT_CONFIG` dict (backwards compatible with `TARGET_CONFIG`/`BRAND_CONFIG`):

```python
PROJECT_CONFIG = {
    "name": "PROJECT_NAME",
"url": "https://project.example.com/path",
"email": os.getenv("PROJECT_EMAIL", ""),
"password": os.getenv("PROJECT_PASSWORD", ""),
"user_agent": os.getenv("PROJECT_USER_AGENT", "Mozilla/5.0 ... Chrome/126 Safari/537.36"),
}
```

**Important**: Environment variables are loaded from `.env` via python-dotenv. Never hardcode credentials!

## Creating a New Test

### 1. Choose Test Type

- **Checkout**: Complete purchase flow
- **Search**: Product discovery
- **Login**: Authentication
- **Browse**: Product navigation
- **Custom**: Specific functionality

### 2. Create Folder Structure

```bash
mkdir -p tests/projects/<projectname>/<testtype>
```

### 3. Create Test File (Python option)

```python
#!/usr/bin/env python3
"""
<Project> <Test Type> Test
Description of what this test covers
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from tests.base_test_engine import BaseTestEngine

# Project configuration
PROJECT_CONFIG = {
"name": "PROJECT_NAME",
"url": "https://project.example.com/",
"email": os.getenv("PROJECT_EMAIL", ""),
"password": os.getenv("PROJECT_PASSWORD", ""),
"user_agent": os.getenv("PROJECT_USER_AGENT", "Mozilla/5.0 ... Chrome/126 Safari/537.36")
}

# Test steps configuration
TEST_STEPS = [
    {
        "name": "Navigate to start page",
        "action": "navigate",
        "url": PROJECT_CONFIG["url"]
    },
    {
        "name": "Perform first action",
        "action": "click",
        "selector": "#first-button",
        "timeout": 40,
        "artifact_tag": "first-action"
    }
    # ... more steps
]

def main():
    """Execute the test"""
    engine = BaseTestEngine(PROJECT_CONFIG)
    engine.run_test(TEST_STEPS)

if __name__ == "__main__":
    main()
```

### 4. GUI Discovery (no changes needed)

Just place your file; the GUI auto‑discovers projects and flows.

## Best Practices

### Naming Conventions

- **Files**: `PROJECT_TESTTYPE.py` (e.g., `SHOP_CHECKOUT.py`, `SHOP_SEARCH.py`)
- **Steps**: Clear, action-oriented names
- **Tags**: Descriptive artifact tags for debugging

### Error Handling

- Use `critical: True` for essential steps
- Add meaningful `artifact_tag` for failure points
- Consider fallback steps for flaky elements

### Headless Mode

- Payment inputs may render inside iframes (engine auto-searches)
- Screenshots are robust with CDP fallback
- Use meaningful `artifact_tag` per critical step

### Environment Variables

- Always use `.env` for credentials
- Provide sensible defaults for non-sensitive data
- Document required variables in README

## Test Execution

### Via GUI

1. Launch: `python run_gui.py`
2. Select project and test type
3. Choose mode (normal/headless)
4. Click "Start Test"

### Via Command Line (advanced)

```bash
cd tests/projects/<project>/<testtype>/
python <testfile>.py
```

### Environment Setup

```bash
# Copy template
cp env.example .env

# Edit with real values
nano .env

# Required variables
PROJECT_EMAIL=your_email@example.com
PROJECT_PASSWORD=your_password
PROJECT_USER_AGENT=Mozilla/5.0 ... Chrome/126 Safari/537.36
```

## Troubleshooting

### Common Issues

- **Element not found**: Check selector, timing, iframes
- **Headless failures**: Verify window size, scale factor
- **Screenshot issues**: Check file permissions, disk space
- **Import errors**: Verify `sys.path.append` and `__init__.py` files

### Debug Mode

Enable detailed logging:

```bash
export LOG_LEVEL=DEBUG
export CONSOLE_MIN_LEVEL=INFO
```

### Artifacts

Test results are saved in `logs/<timestamp>-<testtype>/`:

- `summary.json`: Test execution summary
- `*.png`: Screenshots at failure points
- `*-page-analysis.json`: Page state analysis
- `*-console.json`: Console error logs
- `*-network-summary.json`: Network request summary

---

**Happy Testing! 🎉**
