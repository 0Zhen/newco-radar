"""把 make_lists.py 產出的信件（含 CSV 附件）存成 newcoradar 的 Gmail 草稿，或直接寄出。

用法：
  python3 scripts/send.py auth                       第一次授權：印出網址（只需一次）
  python3 scripts/send.py auth '<跳轉後的網址>'       貼回網址完成授權
  python3 scripts/send.py draft out/1007-1013/       每人建一封草稿（預設，不會寄出）
  python3 scripts/send.py draft out/1007-1013/ --only someone@gmail.com
  python3 scripts/send.py send  out/1007-1013/       直接寄出（會先列出收件人並要求輸入 yes）

憑證放在 repo 外（~/.config/newco-radar/，權限 600），不進 public repo：
  client_secret.json  Google Cloud 建的 OAuth 用戶端（類型「電腦版應用程式」）
  token.json          auth 之後產生的 refresh token
只用標準函式庫，不必裝 google-api-python-client。
"""
import base64
import hashlib
import html
import json
import os
import re
import secrets
import sys
import urllib.parse
import urllib.request
from email.headerregistry import Address
from email.message import EmailMessage

CONF = os.path.expanduser("~/.config/newco-radar")
CLIENT = os.path.join(CONF, "client_secret.json")
TOKEN = os.path.join(CONF, "token.json")
SCOPE = "https://www.googleapis.com/auth/gmail.compose"   # 建草稿＋寄信，不能讀信
REDIRECT = "http://localhost:8765/"
SENDER = Address("開業雷達", "newcoradar", "gmail.com")
API = "https://gmail.googleapis.com/gmail/v1/users/me/"


def client():
    c = json.load(open(CLIENT))
    return c.get("installed") or c["web"]


def post(url, data=None, token=None, body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif data is not None:
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()}")


def auth(back=None):
    """伺服器沒有瀏覽器，分兩段：
    auth          印出網址→在自己的瀏覽器用 newcoradar 登入同意→瀏覽器會跳到 localhost:8765
                  並顯示無法連線，這是正常的
    auth '<網址>'  把網址列整串貼回來，換成 refresh token"""
    c = client()
    pending = os.path.join(CONF, "pending.json")
    if back is None:
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = c["auth_uri"] + "?" + urllib.parse.urlencode({
            "client_id": c["client_id"], "redirect_uri": REDIRECT, "response_type": "code",
            "scope": SCOPE, "access_type": "offline", "prompt": "consent",
            "login_hint": str(SENDER.addr_spec),
            "code_challenge": challenge, "code_challenge_method": "S256"})
        write_private(pending, {"verifier": verifier})
        print("用登入 newcoradar@gmail.com 的瀏覽器開這個網址並同意：\n\n" + url + "\n")
        print("瀏覽器最後會顯示「無法連上 localhost」，複製網址列整串，執行：\n"
              "  python3 scripts/send.py auth '<貼上網址>'")
        return
    code = urllib.parse.parse_qs(urllib.parse.urlparse(back).query).get("code", [back])[0]
    tok = post(c["token_uri"], {
        "code": code, "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
        "code_verifier": json.load(open(pending))["verifier"]})
    if "refresh_token" not in tok:
        sys.exit(f"沒有拿到 refresh token：{tok}")
    write_private(TOKEN, {"refresh_token": tok["refresh_token"]})
    os.remove(pending)
    print(f"完成，已存到 {TOKEN}")


def write_private(path, obj):
    os.makedirs(CONF, mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)


def access_token():
    c = client()
    return post(c["token_uri"], {
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": json.load(open(TOKEN))["refresh_token"],
        "grant_type": "refresh_token"})["access_token"]


def html_to_text(s):
    s = re.sub(r"(?is)<(head|style|title).*?</\1>", "", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h\d)>|<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</t[dh]>", "\t", s)
    s = re.sub(r"(?i)<li[^>]*>", "・", s)
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n\s*\n+", "\n\n", "\n".join(line.strip() for line in s.splitlines())).strip()


def build(m):
    body = open(m["html"], encoding="utf-8").read()
    msg = EmailMessage()
    msg["From"] = SENDER
    msg["To"] = m["to"]
    msg["Subject"] = m["subject"]
    msg.set_content(html_to_text(body))
    msg.add_alternative(body, subtype="html")
    msg.add_attachment(open(m["attachment"], "rb").read(), maintype="text", subtype="csv",
                       filename=m["attachment_name"])
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def run(mode, outdir, only=None):
    manifest = json.load(open(os.path.join(outdir, "manifest.json"), encoding="utf-8"))
    if only:
        manifest = [m for m in manifest if m["to"] in only]
    if not manifest:
        sys.exit("manifest 裡沒有符合的收件人")
    for m in manifest:
        print(f"  {m['to']}：{m['count']} 家，附件 {os.path.getsize(m['attachment']) / 1024:.0f} KB")
    if mode == "send" and input(f"確定直接寄出這 {len(manifest)} 封？輸入 yes：").strip() != "yes":
        sys.exit("已取消")
    token = access_token()
    for m in manifest:
        raw = build(m)
        if mode == "send":
            r = post(API + "messages/send", token=token, body={"raw": raw})
            print(f"已寄出 {m['to']}（{r['id']}）")
        else:
            r = post(API + "drafts", token=token, body={"message": {"raw": raw}})
            print(f"已建草稿 {m['to']}（{r['id']}）")


if __name__ == "__main__":
    args = sys.argv[1:]
    only = None
    if "--only" in args:
        i = args.index("--only")
        only = {a.lower() for a in args[i + 1:]}
        args = args[:i]
    if args[:1] == ["auth"]:
        auth(args[1] if len(args) > 1 else None)
    elif len(args) == 2 and args[0] in ("draft", "send"):
        run(args[0], args[1], only)
    else:
        sys.exit(__doc__)
