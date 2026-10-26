import json
import os
import re
import urllib.request
import urllib.error

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "apps.json")

def get_headers():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def fetch_github_release_app(target):
    owner = target["owner"]
    repo = target["repo"]
    pattern = re.compile(target.get("ipa_pattern", r".*\.ipa"), re.IGNORECASE)
    max_versions = target.get("max_versions", 5)

    api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    print(f"Fetching GitHub releases for {owner}/{repo}...")

    req = urllib.request.Request(api_url, headers=get_headers())
    try:
        with urllib.request.urlopen(req) as resp:
            releases = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error fetching {owner}/{repo}: {e}")
        return None

    versions = []
    for r in releases:
        tag = r.get("tag_name", "")
        if "nightly" in tag.lower():
            continue

        clean_version = tag.lstrip("v")
        ipa_asset = None
        for asset in r.get("assets", []):
            name = asset.get("name", "")
            if pattern.search(name):
                ipa_asset = asset
                break

        if ipa_asset:
            body = r.get("body", "")
            # Truncate description if too long
            desc = body[:300].strip() if body else f"{target['name']} {clean_version}"
            versions.append({
                "version": clean_version,
                "date": r.get("published_at", "")[:10],
                "size": ipa_asset.get("size", 0),
                "downloadURL": ipa_asset.get("browser_download_url", ""),
                "localizedDescription": desc
            })
            if len(versions) >= max_versions:
                break

    if not versions:
        print(f"No valid IPA releases found for {owner}/{repo}")
        return None

    return {
        "name": target["name"],
        "bundleIdentifier": target["bundleIdentifier"],
        "developerName": target.get("developerName", owner),
        "subtitle": target.get("subtitle", ""),
        "localizedDescription": target.get("localizedDescription", ""),
        "iconURL": target.get("iconURL", ""),
        "tintColor": target.get("tintColor", "#000000"),
        "versions": versions
    }

def fetch_upstream_source(source_url):
    print(f"Fetching upstream source: {source_url}...")
    req = urllib.request.Request(source_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            return data.get("apps", [])
    except Exception as e:
        print(f"Error fetching source {source_url}: {e}")
        return []

def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"Config file not found: {CONFIG_PATH}")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    all_apps = []
    seen_identifiers = set()

    # 1. Scrape direct GitHub releases (e.g. Fladder)
    for target in config.get("github_releases", []):
        app = fetch_github_release_app(target)
        if app:
            all_apps.append(app)
            seen_identifiers.add(app["bundleIdentifier"])

    # 2. Fetch and merge upstream sources (e.g. dvntm / Dan's Workshop)
    for source_url in config.get("upstream_sources", []):
        apps = fetch_upstream_source(source_url)
        for app in apps:
            bundle_id = app.get("bundleIdentifier")
            # If not already present or uniquely identified
            if bundle_id and bundle_id not in seen_identifiers:
                all_apps.append(app)
                seen_identifiers.add(bundle_id)
            elif not bundle_id:
                # Add apps without bundleIdentifier if unique by name
                if app.get("name") not in seen_identifiers:
                    all_apps.append(app)
                    seen_identifiers.add(app.get("name"))

    repo_output = {
        "name": config.get("name", "Personal Store"),
        "identifier": config.get("identifier", "com.custom.personalstore"),
        "subtitle": config.get("subtitle", "Custom AltStore Repository"),
        "apps": all_apps,
        "news": []
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(repo_output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Successfully generated {OUTPUT_PATH} with {len(all_apps)} apps:")
    for app in all_apps:
        ver = app.get("versions", [{}])[0].get("version", "?") if app.get("versions") else "?"
        print(f" - {app.get('name')} (v{ver})")

if __name__ == "__main__":
    main()
