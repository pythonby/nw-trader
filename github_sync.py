"""
github_sync.py
----------------
NW Band Scanner ke liye auto-sync helper.
Jab bhi app me alerts add/edit/delete hote hain, ye function
GitHub repo ka ALERTS_JSON secret automatically update kar deta hai
(GitHub Actions ke liye), taki manually secret update na karna pade.

Requirements:
    pip install pynacl requests

Aapke GitHub PAT (Personal Access Token) me ye permission chahiye:
    - Fine-grained token: repo -> "Secrets" -> Read and write
    - Ya Classic token: "repo" scope (full control of private repos)
"""

import base64
import json
import requests
from nacl import encoding, public


def _encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """GitHub ki public key se secret value ko encrypt karta hai (libsodium sealed box)."""
    public_key_obj = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key_obj)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def sync_alerts_to_github(
    alerts_data,
    github_token: str,
    repo_owner: str = "pythonby",
    repo_name: str = "nw-trader",
    secret_name: str = "ALERTS_JSON",
) -> dict:
    """
    alerts_data ko JSON me convert karke GitHub repo secret me update karta hai.

    Returns: {"success": bool, "message": str}
    """
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github+json",
    }

    try:
        # Step 1: Repo ki public key lo (encryption ke liye zaroori)
        key_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/public-key"
        key_resp = requests.get(key_url, headers=headers, timeout=15)
        key_resp.raise_for_status()
        key_data = key_resp.json()

        # Step 2: Alerts ko JSON string bana ke encrypt karo
        if isinstance(alerts_data, (dict, list)):
            secret_value = json.dumps(alerts_data)
        else:
            secret_value = str(alerts_data)

        encrypted_value = _encrypt_secret(key_data["key"], secret_value)

        # Step 3: Secret update karo
        secret_url = (
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/actions/secrets/{secret_name}"
        )
        payload = {"encrypted_value": encrypted_value, "key_id": key_data["key_id"]}
        put_resp = requests.put(secret_url, headers=headers, json=payload, timeout=15)

        if put_resp.status_code in (201, 204):
            return {"success": True, "message": f"{secret_name} GitHub par sync ho gaya ✅"}
        else:
            return {
                "success": False,
                "message": f"GitHub API error {put_resp.status_code}: {put_resp.text}",
            }

    except requests.exceptions.RequestException as e:
        return {"success": False, "message": f"Network/API error: {e}"}
    except Exception as e:
        return {"success": False, "message": f"Unexpected error: {e}"}
