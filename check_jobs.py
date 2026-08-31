#!/usr/bin/env python3
"""Ping a Discord channel when new PM / Data / ML internships appear."""
import json, os, sys, time, urllib.request

FEED = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
SEEN_FILE = "seen.json"

CATEGORIES = {"AI/ML/Data", "Product", "Data Science, AI & Machine Learning", "Product Management"}
TERMS = {"Summer 2027"}                      # set to None to ignore term filtering
TITLE_BLOCK = {"phd", "masters required"}    # crude noise filter
MAX_PER_RUN = 10                             # Discord rate-limit safety

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "job-alert-bot"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())

def matches(job):
    if not job.get("active") or not job.get("is_visible"):
        return False
    if job.get("category") not in CATEGORIES:
        return False
    if TERMS and not (set(job.get("terms") or []) & TERMS):
        return False
    title = (job.get("title") or "").lower()
    return not any(b in title for b in TITLE_BLOCK)

def post(job):
    loc = ", ".join(job.get("locations") or ["N/A"])[:200]
    payload = {"embeds": [{
        "title": f"{job['company_name']} — {job['title']}"[:250],
        "url": job.get("url"),
        "color": 0x5865F2 if job.get("category") == "Product" else 0x2ECC71,
        "fields": [
            {"name": "Category", "value": job.get("category", "?"), "inline": True},
            {"name": "Location", "value": loc, "inline": True},
            {"name": "Term", "value": ", ".join(job.get("terms") or ["?"]), "inline": True},
        ],
        "footer": {"text": f"Sponsorship: {job.get('sponsorship','?')}"},
    }]}
    req = urllib.request.Request(
        WEBHOOK, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30)
    time.sleep(1)

def main():
    dry = "--dry-run" in sys.argv
    jobs = fetch(FEED)
    hits = [j for j in jobs if matches(j)]

    try:
        seen = set(json.load(open(SEEN_FILE)))
    except Exception:
        seen = set()

    new = [j for j in hits if j["id"] not in seen]
    # First run: record everything, announce nothing.
    first_run = not seen

    print(f"{len(jobs)} listings | {len(hits)} match filters | {len(new)} new")
    if dry:
        for j in new[:15]:
            print(f"  [{j['category']:12}] {j['company_name']}: {j['title']}")
        return

    if not first_run:
        for j in new[:MAX_PER_RUN]:
            post(j)
        if len(new) > MAX_PER_RUN:
            print(f"deferred {len(new)-MAX_PER_RUN} to next run")
            new = new[:MAX_PER_RUN]

    json.dump(sorted(seen | {j["id"] for j in new}), open(SEEN_FILE, "w"))

if __name__ == "__main__":
    main()
