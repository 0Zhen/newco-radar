"""依每位報名者的縣市＋產業，從 fetch_week.py 的快取篩出名單。

用法：python3 scripts/make_lists.py data/week.json data/responses.csv out/
responses.csv = Google 表單回覆試算表匯出的 CSV。同一 Email 填多次以最新一筆為準。
每人產出兩個檔：
  NN_<email>.csv   完整名單（附件，UTF-8 BOM，Excel 直接開）
  NN_<email>.html  信件本文（瀏覽器開啟可預覽）
  manifest.json    收件人、主旨、本文與附件路徑，給 send.py 用
"""
import csv
import html
import json
import os
import re
import sys
from collections import Counter, OrderedDict

COUNTIES = ["臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "嘉義市",
            "新竹縣", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "屏東縣", "宜蘭縣", "花蓮縣",
            "臺東縣", "澎湖縣", "金門縣", "連江縣"]

# 表單產業選項 → 營業項目代碼前綴（經濟部營業項目代碼表）
INDUSTRIES = {
    "批發零售": ("F1", "F2", "F3", "F4"),
    "餐飲": ("F501",),
    "營建工程": ("E",),
    "資訊科技": ("I301", "F118", "F218", "F113050", "F213030", "E605010"),
    "專業服務": ("I1", "I401", "I501", "IZ"),
    "醫療保健": ("F10802", "F10803", "F20802", "F20803", "CF01011"),
    "教育": (),   # 補習班、教育服務沒有專屬公司代碼，靠名稱與項目說明
    "運輸物流": ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"),
    "製造業": ("C",),
}
NAME_HINTS = {"教育": ("文教", "教育", "補習", "學苑", "書院"), "餐飲": ("餐飲", "餐廳", "咖啡")}
TOP_ITEMS = 3     # 只看排在前面的營業項目，避免「什麼都登記」的公司每類都中
HIGHLIGHTS = 15   # 信件本文精選筆數

TIPS = {
    "辦公設備與傢俱": "表格依資本額由高到低排；規模較大、營業項目有實體營運的公司，通常會需要辦公空間與設備，可以先從這些看起。",
    "印刷": "新公司開業常需要名片、DM、招牌與包裝，附件有完整地址，可以先挑離你近的。",
    "商業保險": "表格依資本額由高到低排；有存貨、倉儲或店面的公司，產險與團保需求通常比較明確。",
}
DEFAULT_TIP = "表格依資本額由高到低排，可以先從規模較大的開始看。"


def norm(s):
    return s.replace("台", "臺").strip()


def split(s):
    return [t for t in (norm(x) for x in re.split(r"[,，、;；]+", s or "")) if t]


def county_of(addr):
    addr = norm(addr)
    return next((c for c in COUNTIES if addr.startswith(c)), "")


def industry_of(choice):
    """表單選項（可能有錯字，如「發零售」）→ INDUSTRIES 的 key"""
    choice = re.sub(r"（.*?）|\(.*?\)", "", choice)
    return max(INDUSTRIES, key=lambda k: len(set(k) & set(choice)))


def tags(c):
    items = [i for i in c["營業項目"] if not i.startswith("ZZ")][:TOP_ITEMS]
    codes = [i.split(" ", 1)[0] for i in items]
    text = c["公司名稱"] + "".join(items)
    out = {k for k, pre in INDUSTRIES.items() if pre and any(code.startswith(pre) for code in codes)}
    out |= {k for k, hints in NAME_HINTS.items() if any(h in text for h in hints)}
    return out


def roc(d):
    return f"{int(d[:3]) + 1911}-{d[3:5]}-{d[5:]}"


def money(n):
    if n >= 100_000_000:
        return f"{n / 100_000_000:,.1f} 億".replace(".0 億", " 億")
    return f"{n / 10000:,.0f} 萬" if n >= 10000 else f"{n:,} 元"


def items_short(c, n=3):
    items = [i.split(" ", 1)[1] for i in c["營業項目"] if not i.startswith("ZZ")]
    return "、".join(items[:n]) + ("等" if len(items) > n else "") or "—"


def write_csv(path, hits):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["統編", "公司名稱", "縣市", "地址", "代表人", "資本額", "核准設立日期", "營業項目"])
        for c in hits:
            w.writerow([c["統編"], c["公司名稱"], c["縣市"], c["地址"], c["代表人"], c["資本額"],
                        roc(c["核准設立日期"]), "；".join(x.split(" ", 1)[-1] for x in c["營業項目"])])


# 配色沿用 landing page（index.html 的 :root 變數）；email 客戶端常忽略 <style>，一律 inline
ACCENT, ACCENT_SOFT, BG_ALT, BORDER, HEAD_BG = "#0f6b4c", "#e4f3ec", "#f4f5f7", "#dfe3e8", "#eef1f4"
TEXT, MUTED = "#1a1d23", "#545b66"
SANS = "'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif"
SERIF = "'Noto Serif TC','Songti TC',serif"


def subject_of(period):
    return f"【開業雷達】你的第一份新設公司名單（{period}）"


def write_html(path, p, hits, period):
    """信件本文（完整 HTML，send.py 直接當 Gmail 本文；瀏覽器開啟即預覽）"""
    e = html.escape
    td = f'style="padding:10px 12px;border-bottom:1px solid {BORDER};vertical-align:top"'
    th = f'style="padding:10px 12px;background:{HEAD_BG};border-bottom:1px solid {BORDER};text-align:left;white-space:nowrap"'
    by_county = "、".join(f"{k} {v}" for k, v in Counter(c["縣市"] for c in hits).most_common())
    rows = "".join(
        f"<tr><td {td}><b>{e(c['公司名稱'])}</b></td><td {td}>{e(c['縣市'])}</td>"
        f"<td {td} align=right>{money(c['資本額'])}</td><td {td}>{roc(c['核准設立日期'])[5:]}</td>"
        f"<td {td}><span style=\"color:{MUTED}\">{e(items_short(c))}</span></td></tr>"
        for c in sorted(hits, key=lambda c: -c["資本額"])[:HIGHLIGHTS])
    tip = TIPS.get(p["行業"], DEFAULT_TIP)
    body = f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(subject_of(period))}</title></head>
<body style="margin:0;padding:0;background:{BG_ALT}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG_ALT};padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:720px;background:#ffffff;border:1px solid {BORDER};border-radius:12px;overflow:hidden;font-family:{SANS};font-size:15px;line-height:1.7;color:{TEXT}">
<tr><td style="background:{ACCENT};padding:24px 28px;color:#ffffff">
<div style="font-family:{SERIF};font-size:22px;font-weight:700">開業雷達</div>
<div style="font-size:14px;opacity:0.9">{period} 新設公司名單</div>
</td></tr>
<tr><td style="padding:24px 28px 8px">
<p style="margin:0 0 12px">你好，</p>
<p style="margin:0 0 16px">我是開業雷達的 Chris。謝謝你 {p['first']} 留下 Email，讓你久等了，說好的第一份名單在這裡。</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{ACCENT_SOFT};border-left:4px solid {ACCENT};border-radius:8px">
<tr><td style="padding:16px 20px">
<div style="font-size:13px;color:{MUTED}">你的條件</div>
<div>縣市：{e(p['縣市顯示'])}</div>
<div>產業：{e(p['產業顯示'])}</div>
<div style="margin-top:10px;font-size:13px;color:{MUTED}">{period} 經濟部核准設立</div>
<div><span style="font-family:{SERIF};font-size:30px;font-weight:700;color:{ACCENT}">{len(hits)}</span> 家新公司</div>
<div style="font-size:13px;color:{MUTED}">{e(by_county)}</div>
</td></tr></table>
<p style="margin:20px 0 12px">{e(tip)}以下先列 {min(HIGHLIGHTS, len(hits))} 家，<b>完整 {len(hits)} 家在附件</b>（Excel 可直接開，含統編、完整地址、代表人、全部營業項目）。</p>
</td></tr>
<tr><td style="padding:0 28px">
<table cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:0;width:100%;font-size:14px;border:1px solid {BORDER};border-radius:12px;overflow:hidden">
<tr><th {th}>公司名稱</th><th {th}>縣市</th><th {th}>資本額</th><th {th}>設立</th><th {th}>主要營業項目</th></tr>
{rows}
</table>
</td></tr>
<tr><td style="padding:24px 28px 8px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG_ALT};border-radius:12px">
<tr><td style="padding:18px 22px">
<div style="font-family:{SERIF};font-size:17px;font-weight:700;color:{ACCENT};margin-bottom:6px">想請你花一分鐘，直接回覆這封信</div>
<ol style="margin:0;padding-left:20px">
<li>這份名單對你的業務開發有沒有用？哪個欄位最有用，還缺什麼？</li>
<li>條件要不要調整？（縣市或產業太寬、太窄）</li>
<li>如果每週一早上固定寄一份，正式上線預計 NT$299/月，你會考慮訂閱嗎？或是你認為合理的價格是多少？</li>
</ol>
</td></tr></table>
<p style="margin:16px 0">你的回覆會直接決定這個服務要不要做下去、要怎麼做。謝謝！</p>
<p style="margin:0 0 20px">開業雷達　Chris<br><a href="mailto:newcoradar@gmail.com" style="color:{ACCENT}">newcoradar@gmail.com</a></p>
</td></tr>
<tr><td style="padding:14px 28px;border-top:1px solid {BORDER};font-size:12px;color:{MUTED}">
資料來源：經濟部商工行政資料開放平臺，依政府資料開放授權條款利用。本服務與經濟部無隸屬或背書關係。
</td></tr>
</table>
</td></tr></table>
</body></html>"""
    open(path, "w", encoding="utf-8").write(body)


def main(week, responses, outdir, period=""):
    companies = json.load(open(week, encoding="utf-8"))
    for c in companies:
        c["縣市"], c["tags"] = county_of(c["地址"]), tags(c)
    days = sorted({c["核准設立日期"] for c in companies})
    period = period or f"{roc(days[0])[5:].replace('-', '/')}–{roc(days[-1])[5:].replace('-', '/')}"

    rows = list(csv.DictReader(open(responses, encoding="utf-8-sig")))
    people = OrderedDict()
    for r in rows:  # 試算表依時間排序，後面的覆蓋前面的
        email = r["Email"].strip().lower()
        first = people[email]["first"] if email in people else r["時間戳記"].split(" ")[0]
        people[email] = {"email": email, "first": first, "縣市": r["想收哪個縣市"],
                         "產業": r["想收哪類產業"], "行業": r["你的行業"]}

    os.makedirs(outdir, exist_ok=True)
    manifest = []
    print(f"{len(companies)} 家公司，{len(rows)} 筆回覆，{len(people)} 位不重複報名者，期間 {period}")
    for n, p in enumerate(people.values(), 1):
        cs = {norm(x) for x in split(p["縣市"])}
        cs = None if any("不限" in x for x in cs) else cs
        inds = {industry_of(x) for x in split(p["產業"])}
        p["縣市顯示"] = "不限（全國）" if cs is None else "、".join(c for c in COUNTIES if c in cs)
        p["產業顯示"] = "、".join(k for k in INDUSTRIES if k in inds)
        hits = [c for c in companies if (cs is None or c["縣市"] in cs) and c["tags"] & inds]
        hits.sort(key=lambda c: -c["資本額"])
        base = os.path.join(outdir, f"{n:02d}_{re.sub(r'[^A-Za-z0-9._-]', '_', p['email'])}")
        attach = f"開業雷達_{period.replace('/', '').replace('–', '-')}.csv"
        write_csv(base + ".csv", hits)
        write_html(base + ".html", p, hits, period)
        manifest.append({"to": p["email"], "subject": subject_of(period), "html": base + ".html",
                         "attachment": base + ".csv", "attachment_name": attach, "count": len(hits)})
        print(f"{n:02d} {p['email']}: {len(hits)} 家｜縣市={'不限' if cs is None else len(cs)}｜產業={sorted(inds)}")


    json.dump(manifest, open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
