"""India pilot, story IN-1.2: fetch district-wise Kharif area, production and yield from the
Directorate of Economics and Statistics (DES), Ministry of Agriculture & Farmers Welfare.

Source: https://data.desagri.gov.in/website/crops-apy-report-web  (public, no key)
Runs on a laptop, not on Databricks: the portal serves an incomplete TLS certificate chain that
Python's certifi bundle rejects, while Windows curl (schannel) completes it. Output is uploaded
to the india_climate Volume and loaded by notebook 17.

Usage:  python scripts/fetch_des_yields.py  [--start 1997] [--end 2022] [--out data/india/des_kharif_apy.csv]
"""
import argparse, csv, os, re, subprocess, sys, tempfile, time

BASE = "https://data.desagri.gov.in"
PAGE = f"{BASE}/website/crops-apy-report-web"
POST = f"{BASE}/report/crop/horizontal_crop_vertical_year"
CROPS = {"1": "Rice", "4": "Bajra", "5": "Maize", "15": "Groundnut", "24": "Soyabean", "26": "Cotton(lint)"}


def curl(args, out):
    cmd = ["curl", "-s", "--max-time", "300", "-o", out, "-w", "%{http_code}"] + args
    code = subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
    return code


def session(jar):
    page = os.path.join(os.path.dirname(jar), "page.html")
    assert curl(["-c", jar, "-b", jar, PAGE], page) == "200"
    t = open(page, encoding="utf-8").read()
    tok = re.search(r'id="hdnrltoken"[^>]*value="([^"]+)"', t) or re.search(r'value="([^"]+)"[^>]*id="hdnrltoken"', t)
    i = t.find('name="fltrstates[]"')
    seg = t[i:t.find("</select>", i)]
    states = [(v, n.strip()) for v, n in re.findall(r'<option[^>]*value="(\d+)"[^>]*>\s*([^<]*)', seg)]
    return tok.group(1), states


def parse(html, crop):
    rows, state, district = [], None, None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if len(cells) < 4 or not re.fullmatch(r"\d{4} - \d{4}", cells[-4]):
            continue
        lead = cells[:-4]
        if len(lead) >= 2:
            state, district = lead[-2], lead[-1]
        elif len(lead) == 1:
            district = lead[0]
        clean = lambda s: re.sub(r"^\d+\.\s*", "", s)
        num = lambda s: None if s in ("", "-", "NA") else float(s.replace(",", ""))
        rows.append({"state": clean(state), "district": clean(district), "crop": crop, "season": "Kharif",
                     "year": int(cells[-4][:4]), "area_ha": num(cells[-3]), "production_t": num(cells[-2]),
                     "yield_t_per_ha": num(cells[-1])})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1997)
    ap.add_argument("--end", type=int, default=2022)
    ap.add_argument("--out", default="data/india/des_kharif_apy.csv")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    tmp = tempfile.mkdtemp()
    jar = os.path.join(tmp, "jar.txt")
    token, states = session(jar)
    print(f"{len(states)} states, {len(CROPS)} crops, {a.start}-{a.end}")
    allrows, empty = [], []
    for sid, sname in states:
        for cid, cname in CROPS.items():
            out = os.path.join(tmp, "r.html")
            args = ["-b", jar, "-c", jar, "-X", "POST", POST, "-H", "X-Requested-With: XMLHttpRequest", "-H", f"Referer: {PAGE}"]
            for k, v in [("reportformat", "horizontal_crop_vertical_year"), ("fltrstates[]", sid), ("fltrcrops[]", cid),
                         ("fltrseason[]", "K"), ("fltrstartyear", str(a.start)), ("fltrendyear", str(a.end)),
                         ("fltrrptformat", "exl"), ("_token", token)]:
                args += ["--data-urlencode", f"{k}={v}"]
            code = curl(args, out)
            if code == "419":  # session expired: get a fresh token and retry once
                token, _ = session(jar)
                code = curl(args[:-1] + [f"_token={token}"], out)
            rows = parse(open(out, encoding="utf-8", errors="replace").read(), cname) if code == "200" else []
            (allrows.extend(rows) if rows else empty.append((sname, cname, code)))
            print(f"{sname:<30} {cname:<13} http {code} rows {len(rows)}", flush=True)
            time.sleep(1)  # be polite to a government server
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0]))
        w.writeheader(); w.writerows(allrows)
    print(f"wrote {len(allrows)} rows to {a.out}; {len(empty)} state-crops returned nothing")


if __name__ == "__main__":
    sys.exit(main())
