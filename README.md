# 🛡️ cf-solver

**High-performance, stealthy Cloudflare challenge solver built on `zendriver`.**

[![PyPI version](https://badge.fury.io/py/cf-solver.svg)](https://badge.fury.io/py/cf-solver)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`cf-solver` is a professional Python library designed to automate the resolution of Cloudflare's interactive (Turnstile) and non-interactive (JS-based) challenges. It uses `zendriver` for advanced browser automation, providing a high-performance and lightweight alternative to Selenium-based solvers.

---

## ✨ Features

- 🏎️ **Fast & Lightweight**: Built on `zendriver`'s asynchronous CDP core.
- 🕵️ **Stealthy**: Deep User-Agent and CDP metadata overrides to bypass detection.
- 🛠️ **Modular**: Use as a context manager or standalone solver.
- 🍪 **Easy Integration**: Helpers to format cookies for `httpx`, `requests`, and JSON.
- 🔄 **Smart Refresh**: Force new sessions manually with `force_refresh=True`.

---

## 🚀 Installation

Install via pip:

```bash
pip install cf-solver
```

*Note: Ensure you have a Chrome-based browser installed on your system.*

---

## 📖 Usage Examples

### 1. Basic Solving (Immediate Use)

```python
import asyncio
from cf_solver import CloudflareSolver

async def main():
    target_url = "https://protected-site.com"
    
    async with CloudflareSolver(headless=True) as solver:
        cookies, user_agent = await solver.solve(target_url)
        print(f"Solved! Found {len(cookies)} cookies.")
        # Access clearance directly
        clearance = solver.extract_clearance_cookie(cookies)
        print(f"Target CF Token: {clearance['value']}")

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Integration with `httpx` or `requests`

```python
import httpx
from cf_solver import CloudflareSolver

async def scrape_protected_api():
    async with CloudflareSolver() as solver:
        cookies, ua = await solver.solve("https://api.site.com")
        
        # Convert to standard dict and use in your favorite library
        async with httpx.AsyncClient(
            cookies=CloudflareSolver.to_cookie_dict(cookies),
            headers={"User-Agent": ua}
        ) as client:
            res = await client.get("https://api.site.com/data")
            print(res.json())
```

### 3. Session Persistence (JSON)

Save a session to avoid re-solving for every run:

```python
# Save session
CloudflareSolver.save_to_json("my_session.json", cookies, user_agent)

# Load later
cookies, user_agent = CloudflareSolver.load_from_json("my_session.json")
```

---

## 🧩 API Reference

### `CloudflareSolver`

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `user_agent` | `str` | `None` | Custom User-Agent. Defaults to a random Chrome UA. |
| `timeout` | `float` | `30` | Max seconds to wait for challenge resolution. |
| `headless` | `bool` | `True` | Run browser without a GUI. |

#### Methods

- `await solve(url, force_refresh=False)`: Main entry point. Returns `(cookies: List[Dict], user_agent: str)`.
- `to_cookie_dict(cookies)`: Formats cookies for `httpx`/`requests`.
- `to_cookie_string(cookies)`: Formats cookies for raw `Cookie` headers.
- `save_to_json(path, cookies, user_agent)` / `load_from_json(path)`: Session management.

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Ensure you comply with the Terms of Service of any website you interact with.
