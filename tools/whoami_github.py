"""Which account does the stored credential actually belong to?

Prints only the login and the OAuth scopes - never the token. Pushing with the
wrong account is the kind of mistake that is invisible until a third party sees
it, so the identity is checked rather than assumed from the remote URL.
"""
import json
import subprocess
import sys
import urllib.request

HOST = "github.com"


def credential():
    p = subprocess.run(["git", "credential", "fill"],
                       input="protocol=https\nhost=%s\n\n" % HOST,
                       capture_output=True, text=True)
    kv = {}
    for line in (p.stdout or "").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            kv[k] = v
    return kv


def main():
    kv = credential()
    user = kv.get("username")
    secret = kv.get("password")
    if not secret:
        print("no credential stored for %s" % HOST)
        return 2
    print("credential_stored=yes  username_field=%r  token_len=%d  kind=%s"
          % (user, len(secret),
             "github_pat" if secret.startswith("github_pat_") else
             ("ghp" if secret.startswith("ghp_") else "other")))
    req = urllib.request.Request("https://api.github.com/user", headers={
        "Authorization": "Bearer " + secret,
        "Accept": "application/vnd.github+json",
        "User-Agent": "identity-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            body = json.loads(r.read().decode("utf-8"))
            print("login=%s  name=%r  scopes=%r"
                  % (body.get("login"), body.get("name"),
                     r.headers.get("X-OAuth-Scopes")))
    except Exception as exc:
        print("api_error=%s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
