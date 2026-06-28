#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_data.py
בונה את קובץ data.json שהאתר (מאגר רופאים בהסדר) קורא ממנו.

מקור הנתונים:
  • מנורה  — מתוך קובץ ה-CSV הציבורי שמורד מאתר מנורה (מתעדכן שבועית).
  • שאר 4 החברות (איילון/כלל/מגדל/פניקס) — נשלפות מתוך ה-PAYLOAD המוטמע ב-index.html
    (תמונת מצב "קפואה" עד שנחבר גם להן מקור עדכון משלהן).

הרצה:
  python build_data.py --menora menora.csv --html index.html --out data.json

בדיקות שפיות: אם מספר רשומות מנורה יוצא נמוך/גבוה מהצפוי, הסקריפט נכשל בכוונה
(exit code 1) ולא דורס את data.json — כדי שקובץ שבור/ריק לא ימחק את הרשימה.
"""

import argparse, csv, json, re, sys
from datetime import datetime

# ---- גבולות שפיות לרשומות מנורה (להגנה מפני קובץ שבור) ----
MENORA_MIN = 1500
MENORA_MAX = 6000

MENORA = "מנורה"


def extract_payload(html_path):
    """שולף את אובייקט ה-PAYLOAD (JSON) מתוך index.html ע""י איזון סוגריים."""
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"const\s+PAYLOAD\s*=\s*", html)
    if not m:
        sys.exit("ERROR: לא נמצא PAYLOAD בקובץ ה-HTML")
    i = html.index("{", m.end())
    depth, j, in_str, esc = 0, i, False, False
    while j < len(html):
        ch = html[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(html[i:j + 1])
        j += 1
    sys.exit("ERROR: PAYLOAD לא תקין (סוגריים לא מאוזנים)")


def decode_payload(p):
    """מפענח את PAYLOAD לרשומות בדיוק במבנה ש-decode() ב-JS מייצר."""
    comp, tit, spec, subs, cities, rows = (
        p["companies"], p["titles"], p["specialties"], p["subs"], p["cities"], p["rows"]
    )
    out = []
    for i, r in enumerate(rows):
        out.append({
            "id": "doc_" + str(i),
            "company": comp[r[0]],
            "name": r[1] or "—",
            "lic": r[2] or "",
            "title": tit[r[3]] or "",
            "specialty": spec[r[4]] or "",
            "sub": subs[r[5]] or "",
            "s3": r[6], "s1": r[7],
            "cities": [cities[ci] for ci in (r[8] or [])],
            "hospital": r[9] or "",
            "start": r[10] or "", "end": r[11] or "",
            "expired": bool(r[12]),
            "lkey": r[13] or "",
        })
    return out


def yn(v):
    """כן/לא -> 1/0"""
    return 1 if str(v).strip() == "כן" else 0


def is_expired(end):
    """תאריך 'עד' שעבר => פג תוקף. ריק או עתידי => פעיל."""
    end = (end or "").strip()
    if not end:
        return False
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(end, fmt).date() < datetime.now().date()
        except ValueError:
            continue
    return False  # תאריך לא מזוהה — לא מסמנים כפג תוקף


def parse_menora(csv_path):
    """קורא את CSV של מנורה ומחזיר רשומות במבנה האחיד."""
    recs = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # מדלגים על שורת הכותרות
        for n, row in enumerate(reader):
            if not row or len(row) < 14:
                continue
            (first, last, lic, title, spec, sub,
             s3, s1, c1, c2, c3, c4, start, end) = [c.strip() for c in row[:14]]
            name = (first + " " + last).strip() or "—"
            cities = [c for c in (c1, c2, c3, c4) if c]
            lkey = re.sub(r"\D", "", lic)
            recs.append({
                "id": "menora_" + str(n),
                "company": MENORA,
                "name": name,
                "lic": lic,
                "title": title,
                "specialty": spec,
                "sub": sub,
                "s3": yn(s3), "s1": yn(s1),
                "cities": cities,
                "hospital": "",          # ה-CSV הציבורי לא כולל בית חולים, רק עיר
                "start": start, "end": end,
                "expired": is_expired(end),
                "lkey": lkey,
            })
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--menora", required=True, help="נתיב לקובץ ה-CSV של מנורה")
    ap.add_argument("--html", required=True, help="נתיב ל-index.html (מקור 4 החברות האחרות)")
    ap.add_argument("--out", required=True, help="נתיב לקובץ הפלט data.json")
    args = ap.parse_args()

    # 4 החברות האחרות מתוך ה-PAYLOAD
    payload = extract_payload(args.html)
    all_decoded = decode_payload(payload)
    others = [d for d in all_decoded if d["company"] != MENORA]

    # מנורה — מהקובץ הטרי
    menora = parse_menora(args.menora)

    # --- בדיקת שפיות ---
    if not (MENORA_MIN <= len(menora) <= MENORA_MAX):
        sys.exit(
            f"ERROR: מספר רשומות מנורה ({len(menora)}) מחוץ לטווח הצפוי "
            f"[{MENORA_MIN}-{MENORA_MAX}] — לא כותב data.json. בדוק את קובץ המקור."
        )

    data = others + menora
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    # סיכום
    by_comp = {}
    for d in data:
        by_comp[d["company"]] = by_comp.get(d["company"], 0) + 1
    active = sum(1 for d in menora if not d["expired"])
    print(f"OK  data.json נכתב: {len(data)} רשומות סה""כ")
    for c, n in sorted(by_comp.items(), key=lambda x: -x[1]):
        print(f"     {c}: {n}")
    print(f"     מתוך מנורה — פעילים: {active} | פג תוקף: {len(menora) - active}")


if __name__ == "__main__":
    main()
