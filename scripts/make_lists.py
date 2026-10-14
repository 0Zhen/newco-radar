"""依每位報名者的縣市＋產業，從 fetch_week.py 的快取篩出名單。

用法：python3 scripts/make_lists.py data/week.json data/responses.csv out/
responses.csv = Google 表單回覆試算表匯出的 CSV。同一 Email 填多次以最新一筆為準。
每人產出兩個檔：
  NN_<email>.csv   完整名單（附件，UTF-8 BOM，Excel 直接開）
  NN_<email>.html  信件草稿（瀏覽器開啟→全選複製→貼進 Gmail，表格格式會保留）
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


def write_html(path, p, hits, period, attach):
    e = html.escape
    td = 'style="padding:6px 8px;border-bottom:1px solid #ddd;vertical-align:top"'
    th = 'style="padding:6px 8px;border-bottom:2px solid #333;text-align:left;white-space:nowrap"'
    by_county = "、".join(f"{k} {v}" for k, v in Counter(c["縣市"] for c in hits).most_common())
    rows = "".join(
        f"<tr><td {td}>{e(c['公司名稱'])}</td><td {td}>{e(c['縣市'])}</td>"
        f"<td {td} align=right>{money(c['資本額'])}</td><td {td}>{roc(c['核准設立日期'])[5:]}</td>"
        f"<td {td}>{e(items_short(c))}</td></tr>"
        for c in sorted(hits, key=lambda c: -c["資本額"])[:HIGHLIGHTS])
    tip = TIPS.get(p["行業"], DEFAULT_TIP)
    body = f"""<!doctype html><meta charset="utf-8"><title>{e(p['email'])}</title>
<div style="font-family:'Noto Sans TC','PingFang TC','Microsoft JhengHei',sans-serif;font-size:15px;line-height:1.7;color:#222;max-width:720px">
<p style="color:#888;font-size:13px">收件人：{e(p['email'])}<br>主旨：【開業雷達】你的第一份新設公司名單（{period}）<br>附件：{e(attach)}</p>
<hr>
<p>你好，</p>
<p>我是開業雷達的 Chris。謝謝你 {p['first']} 留下 Email，讓你久等了，說好的第一份名單在這裡。</p>
<p>依你填的條件：<br>
・縣市：{e(p['縣市顯示'])}<br>
・產業：{e(p['產業顯示'])}<br>
篩出 <b>{period}</b> 經濟部核准設立的新公司，共 <b>{len(hits)} 家</b>（{by_county}）。</p>
<p>{e(tip)}以下先列 {min(HIGHLIGHTS, len(hits))} 家，<b>完整 {len(hits)} 家在附件</b>（Excel 可直接開，含統編、完整地址、代表人、全部營業項目）。</p>
<table style="border-collapse:collapse;font-size:14px;width:100%">
<tr><th {th}>公司名稱</th><th {th}>縣市</th><th {th}>資本額</th><th {th}>設立</th><th {th}>主要營業項目</th></tr>
{rows}
</table>
<p>想請你花一分鐘，<b>直接回覆這封信</b>：</p>
<ol>
<li>這份名單對你的業務開發有沒有用？哪個欄位最有用，還缺什麼？</li>
<li>條件要不要調整？（縣市或產業太寬、太窄）</li>
<li>如果每週一早上固定寄一份，正式上線預計 NT$299/月，你會考慮訂閱嗎？或是你認為合理的價格是多少？</li>
</ol>
<p>你的回覆會直接決定這個服務要不要做下去、要怎麼做。謝謝！</p>
<p>開業雷達　Chris<br>newcoradar@gmail.com</p>
<p style="font-size:12px;color:#888">資料來源：經濟部商工行政資料開放平臺，依政府資料開放授權條款利用。本服務與經濟部無隸屬或背書關係。</p>
</div>"""
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
        write_html(base + ".html", p, hits, period, attach)
        print(f"{n:02d} {p['email']}: {len(hits)} 家｜縣市={'不限' if cs is None else len(cs)}｜產業={sorted(inds)}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
