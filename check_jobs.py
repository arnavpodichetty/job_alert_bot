#!/usr/bin/env python3
"""Ping a Discord channel when new PM / Data / ML internships appear."""
import json, os, sys, time, urllib.request, urllib.error

FEED = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
SEEN_FILE = "seen.json"
UA = "job-alert-bot (https://github.com, 1.0)"

# ---- filters -------------------------------------------------------------
CATEGORIES = {"AI/ML/Data", "Product", "Data Science, AI & Machine Learning",
              "Product Management"}
TERMS = {"Summer 2027"}          # None to ignore term filtering
REQUIRE_BACHELORS = True         # drop Master's/PhD-only roles
TITLE_BLOCK = {"phd"}            # substrings that suppress a listing
DEDUPE_BY_TITLE = True           # collapse the same role posted twice
MAX_PER_RUN = 10                 # Discord rate-limit safety
MENTION = ""                     # e.g. "<@123456789012345678>" to ping yourself

COLORS = {"Product": 0x5865F2, "Product Management": 0x5865F2}
DEFAULT_COLOR = 0x2ECC71


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def matches(job):
    if not job.get("active") or not job.get("is_visible"):
        return False
    if job.get("category") not in CATEGORIES:
        return False
    if TERMS and not (set(job.get("terms") or []) & TERMS):
        return False
    degrees = job.get("degrees") or []
    if REQUIRE_BACHELORS and degrees and "Bachelor's" not in degrees:
        return False
    title = (job.get("title") or "").lower()
    return not any(b in title for b in TITLE_BLOCK)


def build_embed(job):
    posted = job.get("date_posted")
    fields = [
        {"name": "Category", "value": job.get("category", "?"), "inline": True},
        {"name": "Location",
         "value": ", ".join(job.get("locations") or ["Not listed"])[:1000],
         "inline": True},
        {"name": "Term", "value": ", ".join(job.get("terms") or ["?"]), "inline": True},
        {"name": "Degrees",
         "value": ", ".join(job.get("degrees") or ["Not listed"]),
         "inline": True},
    ]
    if posted:
        # Discord renders these live: absolute date + "3 days ago"
        fields.append({"name": "Posted",
                       "value": f"<t:{posted}:d> (<t:{posted}:R>)",
                       "inline": True})
    if job.get("date_updated") and job["date_updated"] != posted:
        fields.append({"name": "Updated",
                       "value": f"<t:{job['date_updated']}:R>", "inline": True})
    sponsorship = job.get("sponsorship")
    if sponsorship and sponsorship != "Other":
        fields.append({"name": "Sponsorship", "value": sponsorship, "inline": True})

    embed = {
        "title": f"{job['company_name']} — {job['title']}"[:250],
        "url": job.get("url"),
        "color": COLORS.get(job.get("category"), DEFAULT_COLOR),
        "fields": fields,
        "footer": {"text": f"via {job.get('source', 'Simplify')}"},
    }
    if posted:
        embed["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(posted))
    if job.get("company_url"):
        embed["description"] = f"[All {job['company_name']} roles]({job['company_url']})"
    return embed


def post(job):
    payload = {"embeds": [build_embed(job)]}
    if MENTION:
        payload["content"] = MENTION
    req = urllib.request.Request(
        WEBHOOK, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as e:
        print(f"  POST failed {e.code}: {e.read().decode()[:300]}")
        raise
    time.sleep(1)


def main():
    dry = "--dry-run" in sys.argv
    jobs = fetch(FEED)
    hits = [j for j in jobs if matches(j)]

    try:
        seen = set(json.load(open(SEEN_FILE)))
    except Exception:
        seen = set()
    first_run = not seen

    new = [j for j in hits if j["id"] not in seen]
    new.sort(key=lambda j: j.get("date_posted") or 0)

    if DEDUPE_BY_TITLE:
        keep, seen_titles = [], set()
        for j in new:
            key = (j["company_name"].lower(), (j.get("title") or "").lower())
            if key in seen_titles:
                continue
            seen_titles.add(key)
            keep.append(j)
        new = keep

    print(f"{len(jobs)} listings | {len(hits)} match filters | {len(new)} new")
    if dry:
        for j in new[:15]:
            d = ",".join(j.get("degrees") or ["-"])
            print(f"  [{j['category']:12}] {j['company_name']}: {j['title']}  ({d})")
        return

    if not first_run:
        for j in new[:MAX_PER_RUN]:
            post(j)
        if len(new) > MAX_PER_RUN:
            print(f"deferred {len(new) - MAX_PER_RUN} to next run")
            new = new[:MAX_PER_RUN]

    json.dump(sorted(seen | {j["id"] for j in new}), open(SEEN_FILE, "w"))


if __name__ == "__main__":
    main()
