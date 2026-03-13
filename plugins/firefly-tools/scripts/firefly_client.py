#!/usr/bin/env python3
"""Synchronous HTTP client for Firefly III and Data Importer APIs.

This is the shared foundation for all Cowork scripts. It handles:
- Authentication via .env file
- Retry logic with exponential backoff
- Pagination helpers
- Consistent error formatting as JSON to stdout

Usage as a library:
    from firefly_client import get_client
    client = get_client()
    data = client.get("/transactions", params={"page": 1})

Usage standalone (connection test):
    python firefly_client.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests


def _find_env_file() -> Path:
    """Locate the .env file, checking multiple standard locations."""
    # 1. CLAUDE_PLUGIN_ROOT environment variable (set by Claude Code)
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        env_path = Path(plugin_root) / ".env"
        if env_path.exists():
            return env_path

    # 2. Relative to this script (scripts/ is inside the plugin directory)
    script_dir = Path(__file__).resolve().parent
    env_path = script_dir.parent / ".env"
    if env_path.exists():
        return env_path

    # 3. Current working directory
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        return env_path

    raise FileNotFoundError(
        "Could not find .env file. Checked:\n"
        f"  - $CLAUDE_PLUGIN_ROOT/.env\n"
        f"  - {script_dir.parent / '.env'}\n"
        f"  - {Path.cwd() / '.env'}\n"
        "Run /firefly-tools:setup to create it."
    )


def _load_env(env_path: Path) -> dict[str, str]:
    """Parse a .env file into a dict. Ignores comments and blank lines."""
    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


class FireflyClient:
    """Synchronous HTTP client for Firefly III."""

    def __init__(
        self,
        firefly_url: str,
        token: str,
        importer_url: str = "",
        importer_secret: str = "",
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = firefly_url.rstrip("/") + "/api/v1"
        self.importer_url = importer_url.rstrip("/") if importer_url else ""
        self.importer_secret = importer_secret
        self.max_retries = max_retries
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, params: dict | None = None) -> dict | list:
        """GET request with retry logic."""
        return self._request("GET", path, params=params)

    def post(self, path: str, json_data: dict | None = None) -> dict:
        """POST request with retry logic."""
        return self._request("POST", path, json_data=json_data)

    def put(self, path: str, json_data: dict | None = None) -> dict:
        """PUT request with retry logic."""
        return self._request("PUT", path, json_data=json_data)

    def delete(self, path: str) -> None:
        """DELETE request with retry logic."""
        self._request("DELETE", path)

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_data: dict | None = None,
    ) -> dict | list | None:
        """Execute an HTTP request with exponential backoff retry."""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                if resp.status_code == 204 or not resp.content:
                    return None
                return resp.json()
            except requests.exceptions.ConnectionError as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except requests.exceptions.HTTPError as e:
                # Don't retry client errors (4xx)
                if resp.status_code < 500:
                    raise
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def get_all_pages(self, path: str, params: dict | None = None) -> list[dict]:
        """Fetch all pages from a paginated endpoint."""
        params = dict(params or {})
        params["page"] = 1
        all_data: list[dict] = []

        while True:
            data = self.get(path, params=params)
            all_data.extend(data.get("data", []))

            total_pages = (
                data.get("meta", {}).get("pagination", {}).get("total_pages", 1)
            )
            if params["page"] >= total_pages:
                break
            params["page"] += 1

        return all_data

    def upload_csv(self, csv_bytes: bytes, config_json: str) -> str:
        """Upload a CSV + config to the Data Importer."""
        if not self.importer_url:
            raise ValueError("FIREFLY_IMPORTER_URL is not configured")

        url = f"{self.importer_url}/autoupload"
        # Don't use the session's Content-Type header for multipart
        headers = {
            "Authorization": self.session.headers["Authorization"],
            "Accept": "application/json",
        }
        resp = requests.post(
            url,
            params={"secret": self.importer_secret},
            files={
                "importable": ("import.csv", csv_bytes, "text/csv"),
                "json": ("config.json", config_json.encode(), "application/json"),
            },
            headers=headers,
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.text


def get_client() -> FireflyClient:
    """Create a FireflyClient from the .env file."""
    env_path = _find_env_file()
    env = _load_env(env_path)

    required = ["FIREFLY_URL", "FIREFLY_TOKEN"]
    missing = [k for k in required if not env.get(k) or "REPLACE_WITH" in env.get(k, "")]
    if missing:
        raise ValueError(
            f"Missing or placeholder values for: {', '.join(missing)}. "
            "Run /firefly-tools:setup to configure."
        )

    return FireflyClient(
        firefly_url=env["FIREFLY_URL"],
        token=env["FIREFLY_TOKEN"],
        importer_url=env.get("FIREFLY_IMPORTER_URL", ""),
        importer_secret=env.get("FIREFLY_IMPORTER_SECRET", ""),
    )


def output_json(data: dict | list) -> None:
    """Print JSON to stdout for script consumers."""
    print(json.dumps(data, indent=2, default=str))


def output_error(message: str, code: int = 1) -> None:
    """Print an error as JSON to stdout and exit."""
    print(json.dumps({"error": message}))
    sys.exit(code)


if __name__ == "__main__":
    try:
        client = get_client()
        # Quick connection test
        data = client.get("/about")
        output_json({
            "status": "connected",
            "version": data.get("data", {}).get("version", "unknown"),
            "api_version": data.get("data", {}).get("api_version", "unknown"),
        })
    except FileNotFoundError as e:
        output_error(str(e))
    except ValueError as e:
        output_error(str(e))
    except requests.exceptions.ConnectionError:
        output_error("Connection failed. Check FIREFLY_URL and ensure Firefly III is running.")
    except requests.exceptions.HTTPError as e:
        output_error(f"HTTP error: {e}")
