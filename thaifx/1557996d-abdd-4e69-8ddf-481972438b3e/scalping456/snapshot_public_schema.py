"""Archive only the public profile and its observed first-party client scripts.

Does not execute client code, authenticate, guess endpoints or merge live rows
into the original snapshot. Pagination is the already observed read-only UI
action, and is requested only when its identifier remains in the public page.
"""

import argparse
import json
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from download_orders import PROFILE_ID, PROFILE_URL, SERVER_ACTION
from probe_vantage_feed import ROOT, sha, write_json


class ScriptLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.sources.append(attrs["src"])


def public_scripts(html):
    parser = ScriptLinks()
    parser.feed(html)
    links = []
    for src in parser.sources:
        url = urljoin(PROFILE_URL, src)
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc == "thaifxbook.com" and parsed.path.startswith("/_next/static/") and parsed.path.endswith(".js"):
            links.append(url)
    return sorted(set(links))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.tag):
        parser.error("Invalid snapshot tag")
    folder = ROOT / "data" / args.tag
    folder.mkdir(exist_ok=False)
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "public_url": PROFILE_URL,
              "script_sha256": sha(__file__), "files": [], "original_source_modified": False,
              "not_original_execution_history": True, "errors": []}
    response = requests.get(PROFILE_URL, timeout=30, headers={"User-Agent": "Scalping456-public-schema-research/1.0"})
    response.raise_for_status()
    raw_path = folder / "profile.html"
    with raw_path.open("xb") as stream:
        stream.write(response.content)
    report["files"].append({"file": raw_path.name, "url": response.url, "status": response.status_code,
                            "content_type": response.headers.get("Content-Type"), "sha256": sha(raw_path)})
    html = response.content.decode("utf-8")
    urls = public_scripts(html)
    if len(urls) > 50:
        raise RuntimeError("Unexpected client script count; refuse broad download")

    def fetch(pair):
        i, url = pair
        fetched = requests.get(url, timeout=30)
        fetched.raise_for_status()
        if urlparse(fetched.url).netloc != "thaifxbook.com":
            raise RuntimeError("Client script redirected outside first-party host")
        path = folder / f"client_{i:02d}.js"
        with path.open("xb") as stream:
            stream.write(fetched.content)
        return {"file": path.name, "url": url, "status": fetched.status_code, "sha256": sha(path)}, fetched.content.decode("utf-8")

    texts = [html]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for meta, text in pool.map(fetch, enumerate(urls)):
            report["files"].append(meta)
            texts.append(text)
    print("Archived public profile and client scripts", len(urls), flush=True)
    report["observed_old_pagination_action_in_client"] = any(SERVER_ACTION in text for text in texts)
    if report["observed_old_pagination_action_in_client"]:
        try:
            fetched = requests.post(PROFILE_URL, data=json.dumps([PROFILE_ID, 1]), timeout=30,
                                    headers={"Accept": "text/x-component", "Content-Type": "text/plain;charset=UTF-8",
                                             "Next-Action": SERVER_ACTION, "Origin": "https://thaifxbook.com", "Referer": PROFILE_URL})
            fetched.raise_for_status()
            path = folder / "public_page1_action.txt"
            with path.open("xb") as stream:
                stream.write(fetched.content)
            report["files"].append({"file": path.name, "url": PROFILE_URL, "action": SERVER_ACTION,
                                    "read_only_pagination": True, "status": fetched.status_code, "sha256": sha(path)})
            payload_line = next((line[2:] for line in fetched.text.splitlines() if line.startswith("1:")), None)
            payload = json.loads(payload_line) if payload_line else None
            if not isinstance(payload, dict) or not isinstance(payload.get("rows"), list):
                raise ValueError("UI pagination response does not contain rows")
            report["live_page1_payload_keys"] = sorted(payload)
            report["live_page1_rows"] = len(payload["rows"])
            report["live_page1_row_keys"] = sorted({key for row in payload["rows"] for key in row})
        except Exception as exc:
            report["errors"].append({"stage": "observed_public_pagination", "error_type": type(exc).__name__})
    else:
        report["errors"].append({"stage": "pagination_not_requested", "reason": "Previous action identifier not observed; do not guess replacement"})
    source = ROOT / "data/orders_35462.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    report["original_source_sha256"] = sha(source)
    report["original_rows"] = len(rows)
    report["original_field_population"] = dict(Counter(key for row in rows for key in row))
    report["literal_evidence_file_counts"] = {word: sum(word.lower() in text.lower() for text in texts)
                                              for word in ("magic", "position_id", "deal_id", "commission", "swap", "manual", "Journal", ".set", "Scalping456", "Expert Advisor")}
    report["literal_counts_are_not_proof_of_public_fields"] = True
    write_json(folder / "report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k not in ("files", "original_field_population")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
