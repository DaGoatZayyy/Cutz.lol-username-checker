from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
USERNAMES_PATH = ROOT / "usernames.txt"
RESULTS_DIR = ROOT / "results"


def load_config() -> dict:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("Missing config.json")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config.json is invalid: {exc}")

    api_url = str(config.get("api_url", "")).strip()
    if not api_url or "YOUR-DOMAIN" in api_url:
        raise SystemExit("Set api_url in config.json to the documented availability endpoint.")

    parsed = urlparse(api_url)
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise SystemExit("api_url must use HTTPS (HTTP is allowed only for localhost).")
    if parsed.path.rstrip("/").lower().endswith("/api/register"):
        raise SystemExit("The registration endpoint cannot be used for availability checks.")

    if str(config.get("method", "GET")).upper() != "GET":
        raise SystemExit("Only GET availability requests are supported.")

    config["api_url"] = api_url
    config["username_param"] = str(config.get("username_param", "username"))
    config["available_field"] = str(config.get("available_field", "available"))
    config["timeout_seconds"] = max(3, int(config.get("timeout_seconds", 10)))
    config["delay_seconds"] = max(1.0, float(config.get("delay_seconds", 1.5)))
    return config


def load_usernames() -> list[str]:
    try:
        raw_lines = USERNAMES_PATH.read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        raise SystemExit("Missing usernames.txt")

    usernames: list[str] = []
    seen: set[str] = set()
    for line in raw_lines:
        username = line.strip()
        if not username or username.startswith("#"):
            continue
        key = username.casefold()
        if key not in seen:
            seen.add(key)
            usernames.append(username)
    return usernames


def check_username(session: requests.Session, config: dict, username: str) -> bool:
    response = session.get(
        config["api_url"],
        params={config["username_param"]: username},
        timeout=config["timeout_seconds"],
        headers={"Accept": "application/json", "User-Agent": "CutzUsernameChecker/1.0"},
    )

    if response.status_code == 429:
        raise RuntimeError("RATE_LIMITED")
    response.raise_for_status()

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        raise ValueError("API did not return valid JSON") from exc

    value = payload
    for part in config["available_field"].split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(
                f"Response is missing the configured field '{config['available_field']}'"
            )
        value = value[part]

    if not isinstance(value, bool):
        raise ValueError(
            f"'{config['available_field']}' must be a JSON boolean (true/false)"
        )
    return value


def main() -> None:
    config = load_config()
    usernames = load_usernames()
    if not usernames:
        raise SystemExit("No usernames found in usernames.txt")

    RESULTS_DIR.mkdir(exist_ok=True)
    available: list[str] = []
    unavailable: list[str] = []
    errors: list[str] = []

    print(f"Loaded {len(usernames)} unique username(s).\n")
    print(f"{'STATUS':<15} USERNAME")
    print("-" * 42)

    with requests.Session() as session:
        for index, username in enumerate(usernames, start=1):
            try:
                is_available = check_username(session, config, username)
                if is_available:
                    available.append(username)
                    status = "AVAILABLE"
                else:
                    unavailable.append(username)
                    status = "UNAVAILABLE"
                print(f"{status:<15} {username}")
            except RuntimeError as exc:
                if str(exc) == "RATE_LIMITED":
                    print("\nAPI returned HTTP 429. Stopping to respect the service rate limit.")
                    errors.append(f"{username}\tHTTP 429 - run stopped")
                    errors.extend(f"{name}\tNot checked - run stopped after HTTP 429"
                                  for name in usernames[index:])
                    break
                errors.append(f"{username}\t{exc}")
                print(f"{'ERROR':<15} {username} ({exc})")
            except (requests.RequestException, ValueError) as exc:
                errors.append(f"{username}\t{exc}")
                print(f"{'ERROR':<15} {username} ({exc})")

            if index < len(usernames):
                time.sleep(config["delay_seconds"])

    (RESULTS_DIR / "available.txt").write_text(
        "\n".join(available) + ("\n" if available else ""), encoding="utf-8"
    )
    (RESULTS_DIR / "unavailable.txt").write_text(
        "\n".join(unavailable) + ("\n" if unavailable else ""), encoding="utf-8"
    )
    (RESULTS_DIR / "errors.txt").write_text(
        "\n".join(errors) + ("\n" if errors else ""), encoding="utf-8"
    )

    print("\n" + "-" * 42)
    print(f"Finished | available: {len(available)} | unavailable: {len(unavailable)} | errors: {len(errors)}")
    print("Results saved in the results/ folder.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(130)
