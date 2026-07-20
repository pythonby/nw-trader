# ─────────────────────────────────────────────────────────────────
# PERSISTENT STORAGE — GitHub repo file based (SURVIVES app sleep/restart)
# /tmp ki jagah ab GitHub repo me data/nw_scanner_data.json me save hoga.
# Local /tmp ko sirf FAST CACHE ki tarah use karte hain (same session ke liye),
# GitHub hi source-of-truth hai jo restarts ke baad bhi bacha rahega.
# ─────────────────────────────────────────────────────────────────

import base64

STORAGE_FILE = "/tmp/nw_scanner_data.json"

GITHUB_TOKEN      = get_secret("GITHUB_PAT")
GITHUB_REPO_OWNER = "pythonby"
GITHUB_REPO_NAME  = "nw-trader"
GITHUB_DATA_PATH  = "data/nw_scanner_data.json"
_GH_API           = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{GITHUB_DATA_PATH}"


def _gh_headers():
    return {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}


def _load_storage():
    """Load persistent data — pehle GitHub se try karo, fail ho to local /tmp fallback."""
    if GITHUB_TOKEN:
        try:
            r = requests.get(_GH_API, headers=_gh_headers(), timeout=10)
            if r.status_code == 200:
                content = r.json()
                decoded = json.loads(base64.b64decode(content["content"]).decode("utf-8"))
                st.session_state["_gh_sha"] = content["sha"]
                # local /tmp me bhi cache kar lo (fast repeated reads ke liye)
                try:
                    with open(STORAGE_FILE, "w") as f:
                        json.dump(decoded, f, default=str)
                except: pass
                return decoded
            elif r.status_code == 404:
                st.session_state["_gh_sha"] = None
                return {}
        except Exception:
            pass  # network issue -> neeche /tmp fallback try hoga

    # Fallback: local /tmp (agar GITHUB_PAT set nahi hai ya GitHub unreachable hai)
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, "r") as f:
                return json.load(f)
    except: pass
    return {}


def _save_storage(data: dict):
    """Save persistent data — GitHub repo file me commit karo (permanent), + local /tmp cache."""
    ok = False

    # 1) Local /tmp me turant save karo (fast, current session ke liye)
    try:
        with open(STORAGE_FILE, "w") as f:
            json.dump(data, f, indent=2, default=str)
        ok = True
    except: pass

    # 2) GitHub repo file me bhi commit karo (permanent — restart ke baad bhi rahega)
    if GITHUB_TOKEN:
        try:
            content_str = json.dumps(data, indent=2, default=str)
            encoded = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

            sha = st.session_state.get("_gh_sha")
            if sha is None:
                r_get = requests.get(_GH_API, headers=_gh_headers(), timeout=10)
                if r_get.status_code == 200:
                    sha = r_get.json().get("sha")

            payload = {"message": "Auto-update nw_scanner_data.json", "content": encoded}
            if sha:
                payload["sha"] = sha

            r_put = requests.put(_GH_API, headers=_gh_headers(), json=payload, timeout=15)
            if r_put.status_code in (200, 201):
                st.session_state["_gh_sha"] = r_put.json()["content"]["sha"]
                ok = True
        except Exception:
            pass  # GitHub save fail hua to bhi local /tmp save to ho hi chuka hai

    return ok
