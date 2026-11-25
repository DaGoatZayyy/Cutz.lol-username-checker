# Cutz.lol Username Checker

A small Python CLI that checks usernames from `usernames.txt` using an **authorized username-availability API endpoint**.

## Setup

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Add one username per line to `usernames.txt`.
4. Edit `config.json` and set `api_url` to the service's documented availability endpoint.
5. Run:

   ```bash
   python main.py
   ```

Results are saved in `results/available.txt`, `results/unavailable.txt`, and `results/errors.txt`.

## API configuration

The checker sends one GET request per username. By default it appends the username as the query parameter configured by `username_param`, and reads the boolean field configured by `available_field`.

Expected response example:

```json
{ "available": true }
```

If the service uses a different response shape, update `available_field` to the correct boolean field.

**Important:** Use only an endpoint the service documents or explicitly authorizes for availability checks. Do not use the account registration endpoint, CAPTCHA tokens, or proxy rotation for bulk checking. HTTP 429 stops the run to respect rate limits.

## Files

- `config.json` — API URL, request settings, and response field.
- `usernames.txt` — usernames to check.
- `results/` — generated result files.
