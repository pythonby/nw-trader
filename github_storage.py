"""
github_storage.py
------------------
NW Band Scanner ke liye PERMANENT alert storage.
/tmp/nw_scanner_data.json ki jagah ye alerts ko GitHub repo me
ek file (data/alerts.json) me save karta hai using GitHub Contents API.

Fayda: Streamlit Cloud app restart/sleep/redeploy hone par bhi
alerts delete nahi honge, kyunki wo GitHub repo me commit ho jate hain.

Requirements:
    pip install requests
"""

import base64
import json
import requests

FILE_PATH = "data/alerts.json"  # repo ke andar ka path


def load_alerts_from_github(github_token: str, repo_owner: str, repo_name: str):
    """GitHub repo se alerts.json read karta hai. File na mile to empty list return karta hai."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.get(url, headers=headers, timeout=15)

    if resp.status_code == 200:
        content = resp.json()
        decoded = base64.b64decode(content["content"]).decode("utf-8")
        return json.loads(decoded), content["sha"]  # sha update ke liye chahiye
    elif resp.status_code == 404:
        return [], None  # file abhi tak exist nahi karti
    else:
        raise Exception(f"GitHub read error {resp.status_code}: {resp.text}")


def save_alerts_to_github(alerts_data, github_token: str, repo_owner: str, repo_name: str) -> dict:
    """Alerts ko GitHub repo me commit karta hai (create ya update)."""
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{FILE_PATH}"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        # Pehle existing file ka sha lo (update ke liye zaroori, warna conflict error aayega)
        get_resp = requests.get(url, headers=headers, timeout=15)
        sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None

        content_str = json.dumps(alerts_data, indent=2)
        encoded_content = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

        payload = {
            "message": "Update alerts.json via app",
            "content": encoded_content,
        }
        if sha:
            payload["sha"] = sha  # existing file update karne ke liye

        put_resp = requests.put(url, headers=headers, json=payload, timeout=15)

        if put_resp.status_code in (200, 201):
            return {"success": True, "message": "Alerts GitHub par permanently save ho gaye ✅"}
        else:
            return {"success": False, "message": f"GitHub write error {put_resp.status_code}: {put_resp.text}"}

    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Network/API error: {e}"}
