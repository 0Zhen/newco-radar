"""抓指定日期區間的新設公司，補地址／資本額／代表人與營業項目，存成 JSON 快取。

用法：python3 scripts/fetch_week.py 1151007 1151013 data/week.json
日期為民國年 YYYMMDD（含頭尾）。可重跑：已抓過的統編會沿用快取。
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

BASE = "https://data.gcis.nat.gov.tw/od/data/api/"
BY_DATE = "467E8A3A-72C6-4663-9557-D9D74C597E14"
APP1 = "5F64D864-61CB-4D0D-8AD9-492047CC1EA6"   # 地址、資本額、代表人
APP3 = "236EE382-4942-41A9-BD03-CA0709025E7C"   # 營業項目
DELAY = 0.4      # 每條執行緒每次呼叫後的間隔
WORKERS = 4      # 單次查詢約 1–3 秒，循序跑一週要一小時以上

# GCIS 憑證缺 Subject Key Identifier，Python 3.13 起預設的嚴格檢查會拒絕；
# 仍驗證憑證鏈與主機名稱，只關掉 strict 旗標。
SSL_CTX = ssl.create_default_context()
SSL_CTX.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)


def get(api, flt, top=1000, skip=0):
    q = urllib.parse.urlencode({"$format": "json", "$filter": flt, "$skip": skip, "$top": top})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(BASE + api + "?" + q, timeout=30, context=SSL_CTX) as r:
                body = r.read().decode("utf-8-sig").strip()
            time.sleep(DELAY)
            return json.loads(body) if body else []
        except Exception as e:
            print(f"  retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"failed: {api} {flt}")


def roc_range(start, end):
    def to_date(s):
        return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:7]))
    d, e = to_date(start), to_date(end)
    while d <= e:
        yield f"{d.year - 1911:03d}{d.month:02d}{d.day:02d}"
        d += timedelta(days=1)


def enrich(no, name, day):
    a1 = (get(APP1, f"Business_Accounting_NO eq {no}") or [{}])[0]
    a3 = (get(APP3, f"Business_Accounting_NO eq {no}") or [{}])[0]
    return {
        "統編": no,
        "公司名稱": name,
        "核准設立日期": day,
        "地址": a1.get("Company_Location", ""),
        "資本額": a1.get("Capital_Stock_Amount", 0),
        "代表人": a1.get("Responsible_Name", ""),
        "營業項目": [f'{b["Business_Item"]} {b["Business_Item_Desc"]}'
                  for b in a3.get("Cmp_Business") or []],
    }


def save(cache, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out + ".part"
    json.dump(list(cache.values()), open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, out)


def main(start, end, out):
    cache = {}
    if os.path.exists(out):
        cache = {c["統編"]: c for c in json.load(open(out, encoding="utf-8"))}
    for day in roc_range(start, end):
        rows, skip = [], 0
        while True:
            page = get(BY_DATE, f"Company_Setup_Date eq {day}", skip=skip)
            rows += page
            if len(page) < 1000:
                break
            skip += 1000
        todo = [r for r in rows if r["Business_Accounting_NO"] not in cache]
        print(f"{day}: {len(rows)} 家，待補 {len(todo)}", file=sys.stderr, flush=True)
        with ThreadPoolExecutor(WORKERS) as ex:
            futs = [ex.submit(enrich, r["Business_Accounting_NO"], r["Company_Name"], day) for r in todo]
            for n, fut in enumerate(as_completed(futs), 1):
                c = fut.result()
                cache[c["統編"]] = c
                if n % 20 == 0:
                    save(cache, out)
                if n % 50 == 0:
                    print(f"  {day} {n}/{len(todo)}", file=sys.stderr, flush=True)
        save(cache, out)
    print(f"完成，共 {len(cache)} 家", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:4])
