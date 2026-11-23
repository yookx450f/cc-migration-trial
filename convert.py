#!/usr/bin/env python3
"""賃貸申込データ 旧→新 移行プログラム（migration-spec-2026-11-23.md 準拠）

Python 標準ライブラリのみ。入力ファイルは変更しない。
"""
import csv
import datetime
import re
import sys
import unicodedata
from collections import Counter, defaultdict

INPUT = "legacy_applications.csv"
OUT_MIGRATED = "migrated.csv"
OUT_REJECTED = "rejected.csv"
OUT_REVIEW = "review.csv"
MIGRATION_DATE = datetime.date(2026, 11, 23)

NEW_COLUMNS = [
    "application_id", "last_name", "first_name", "last_name_kana", "first_name_kana", "birth_date",
    "country_code", "postal_code", "prefecture_code", "address_line", "phone",
    "property_code", "room_no", "rent_yen", "application_date", "status_new", "industry_new",
    "job_category", "channel_new",
    "emergency_name", "emergency_phone", "guarantor_name",
]

PREFECTURES = [
    "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
    "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
    "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
    "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
    "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
    "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
    "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県",
]
SPEC_CITY_TO_PREF = {"札幌市": "北海道", "仙台市": "宮城県", "福岡市": "福岡県"}

STATUS_MAP = {"1": "RECEIVED", "2": "SCREENING", "4": "APPROVED", "5": "REJECTED",
              "6": "CANCELLED", "7": "CONTRACTED"}
INDUSTRY_MAP = {"A": "MANUFACTURING", "B": "CONSTRUCTION", "C": "IT", "D": "RETAIL_SERVICE",
                "E": "MEDICAL_WELFARE", "F": "PUBLIC_EDUCATION"}

# 職種：仕様の記載順（＝優先順）
JOB_RULES = [
    ("公務員", ["市役所", "県庁", "公立", "教員", "職員"]),
    ("会社員", ["勤務", "SE", "プログラマ", "開発者", "店長", "店員", "看護師", "薬剤師",
               "介護施設の職員", "介護", "現場監督", "施工管理", "作業員", "生産技術", "製造ライン"]),
    ("自営業", ["個人事業", "自営業", "フリーランス"]),
]
# 公務員「職員」の除外条件：病院・施設の職員
JOB_STAFF_EXCLUDE = ["病院の職員", "施設の職員"]

CHANNEL_RULES = [
    ("PORTAL", ["ポータル", "SUUMO", "ホームページ"]),
    ("STORE", ["店舗", "寄った", "看板"]),
    ("REFERRAL", ["紹介"]),
    ("FLYER", ["チラシ"]),
    ("CORPORATE", ["人事", "法人"]),
]


# ---------------------------------------------------------------- helpers
def normalize_kana(s):
    """半角カナ→全角カナ（NFKC）、前後空白除去。"""
    return unicodedata.normalize("NFKC", s).strip()


# イ段（拗音を伴いうる）文字の直後の大書き ヤ/ユ/ヨ は小書きの誤りの疑い。
# どれが誤りかは辞書無しに確定できないため検出のみ行う。
SUSPECT_LARGE_KANA = re.compile(r"[キシチニヒミリギジヂビピ][ヤユヨ]")


def parse_date(s):
    """(date or None, error) を返す。error: None / 'format' / 'invalid'"""
    s = s.strip()
    patterns = [
        (r"^(\d{4})/(\d{1,2})/(\d{1,2})$", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        (r"^(\d{4})(\d{2})(\d{2})$", lambda m: (int(m[1]), int(m[2]), int(m[3]))),
        (r"^R(\d{1,2})\.(\d{1,2})\.(\d{1,2})$", lambda m: (2018 + int(m[1]), int(m[2]), int(m[3]))),
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", lambda m: (int(m[3]), int(m[1]), int(m[2]))),
    ]
    for pat, fn in patterns:
        m = re.match(pat, s)
        if m:
            y, mo, d = fn(m)
            try:
                return datetime.date(y, mo, d), None
            except ValueError:
                return None, "invalid"
    return None, "format"


def normalize_phone(s):
    """(normalized or None, review_reason or None)"""
    p = re.sub(r"[\s\-]", "", s)
    if p.startswith("+81"):
        p = "0" + p[3:]
    elif p.startswith("+"):
        return None, f"日本以外の国番号の電話番号({s})"
    if not re.fullmatch(r"0\d{9,10}", p):
        return None, f"電話番号が0始まり10〜11桁にならない({s})"
    return p, None


def classify(text, rules):
    hits = []
    for cat, kws in rules:
        for kw in kws:
            pos = text.find(kw)
            if pos >= 0:
                hits.append((cat, kw, pos))
    return hits


def classify_job(text):
    """(category or None, review_reason or None)"""
    hits = []
    for cat, kws in JOB_RULES:
        for kw in kws:
            pos = text.find(kw)
            if pos < 0:
                continue
            if cat == "公務員" and kw == "職員" and any(ex in text for ex in JOB_STAFF_EXCLUDE):
                continue
            hits.append((cat, kw, pos))
    cats = {h[0] for h in hits}
    if not cats:
        return None, f"職種キーワードに該当しない(job_text={text})"
    if len(cats) == 1:
        return cats.pop(), None
    # 複数該当：「先に書かれた方」の解釈（仕様の区分順 / 記述内の出現順）が一致する場合のみ確定
    by_spec_order = next(c for c, _ in JOB_RULES if c in cats)
    by_text_order = min(hits, key=lambda h: h[2])[0]
    if by_spec_order == by_text_order:
        return by_spec_order, None
    return None, (f"職種が複数区分に該当し優先解釈により結果が異なる"
                  f"(job_text={text}, 仕様順={by_spec_order}, 記述順={by_text_order})")


def classify_channel(text):
    cats = {h[0] for h in classify(text, CHANNEL_RULES)}
    if not cats:
        return None, f"申込経路キーワードに該当しない(channel_text={text})"
    if len(cats) > 1:
        return None, f"申込経路が複数区分に該当(channel_text={text}, 該当={sorted(cats)})"
    return cats.pop(), None


def starts_with_prefecture(addr):
    return any(addr.startswith(p) for p in PREFECTURES)


def city_of(address):
    """address 先頭の市区町村名（政令市は「○○市」、それ以外は最初の市/区/町/村まで）"""
    m = re.match(r"^(.+?[市区町村])", address)
    return m.group(1) if m else None


# ---------------------------------------------------------------- main
def main():
    with open(INPUT, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        in_columns = reader.fieldnames
        rows = list(reader)

    # データ内の市区町村→都道府県対応（prefecture が日本の都道府県名である行から）
    city_pref = defaultdict(set)
    for r in rows:
        if r["prefecture"] in PREFECTURES:
            c = city_of(r["address"])
            if c:
                city_pref[c].add(r["prefecture"])

    results = []  # (row, new_record, reject_reasons, review_reasons)
    for r in rows:
        rej, rev = [], []
        new = {}

        # 必須項目
        for col in ["application_id", "last_name", "first_name", "property_code", "application_date"]:
            if r[col].strip() == "":
                rej.append(f"必須項目が空({col})")

        new["application_id"] = r["application_id"]
        new["last_name"] = r["last_name"]
        new["first_name"] = r["first_name"]

        # カナ
        for col in ["last_name_kana", "first_name_kana"]:
            k = normalize_kana(r[col])
            new[col] = k
            if SUSPECT_LARGE_KANA.search(k):
                rev.append(f"カナに大書き拗音の疑いがあり正規形を確定できない({col}={k})")

        # 生年月日
        d, err = parse_date(r["birth_date"])
        if err == "invalid":
            rej.append(f"birth_dateが実在しない日付({r['birth_date']})")
        elif err == "format":
            rev.append(f"birth_dateが受付形式でない({r['birth_date']})")
        new["birth_date"] = d.isoformat() if d else ""

        # 申込日
        if r["application_date"].strip() != "":
            d, err = parse_date(r["application_date"])
            if err == "invalid":
                rev.append(f"application_dateが実在しない日付で扱いが仕様に無い({r['application_date']})")
            elif err == "format":
                rev.append(f"application_dateが受付形式でない({r['application_date']})")
            elif d > MIGRATION_DATE:
                rej.append(f"application_dateが移行実施日より未来({d.isoformat()})")
            new["application_date"] = d.isoformat() if d else ""
        else:
            new["application_date"] = ""

        # 都道府県
        pref = r["prefecture"].strip()
        if pref == "":
            c = city_of(r["address"])
            if c in SPEC_CITY_TO_PREF:
                pref = SPEC_CITY_TO_PREF[c]
            elif c and len(city_pref.get(c, ())) == 1:
                pref = next(iter(city_pref[c]))
            else:
                rev.append(f"prefectureが空で住所から推定できない(address={r['address']})")
                pref = ""
        elif pref not in PREFECTURES:
            rev.append(f"prefectureが日本の都道府県名でない(外国住所: {pref})")
        new["prefecture_code"] = pref
        new["address_line"] = r["address"]
        new["country_code"] = "JP"

        # 緊急連絡先・保証人住所
        for col in ["emergency_address", "guarantor_address"]:
            if not starts_with_prefecture(r[col].strip()):
                rev.append(f"{col}が日本の住所形式でない({r[col]})")

        # 郵便番号
        pc = r["postal_code"].replace("-", "").strip()
        if re.fullmatch(r"\d{6}", pc):
            pc = "0" + pc
        if not re.fullmatch(r"\d{7}", pc):
            rev.append(f"郵便番号が7桁の数字にならない({r['postal_code']})")
        new["postal_code"] = pc

        # 電話
        for src, dst in [("phone", "phone"), ("emergency_phone", "emergency_phone")]:
            p, reason = normalize_phone(r[src])
            if reason:
                rev.append(f"{src}: {reason}")
            new[dst] = p or ""

        new["property_code"] = r["property_code"]
        new["room_no"] = r["room_no"]

        # 家賃
        rent_s = unicodedata.normalize("NFKC", r["rent"]).replace(",", "").replace("円", "").strip()
        if re.fullmatch(r"\d+", rent_s):
            rent = int(rent_s)
            if not 10000 <= rent <= 1000000:
                rej.append(f"rentが範囲外({r['rent']})")
            new["rent_yen"] = str(rent)
        else:
            rev.append(f"rentを整数化できない({r['rent']})")
            new["rent_yen"] = ""

        # ステータス
        s = r["status_old"].strip()
        if s == "3":
            rev.append("status_old=3はSCREENING/DOC_WAITを判別できない")
            new["status_new"] = ""
        elif s in STATUS_MAP:
            new["status_new"] = STATUS_MAP[s]
        else:
            rev.append(f"status_oldが対応表に無い({s})")
            new["status_new"] = ""

        # 業種
        ind = r["industry_old"].strip()
        if ind == "G":
            rev.append("industry_old=Gは新区分を判別できない")
            new["industry_new"] = ""
        elif ind in INDUSTRY_MAP:
            new["industry_new"] = INDUSTRY_MAP[ind]
        else:
            rev.append(f"industry_oldが対応表に無い({ind})")
            new["industry_new"] = ""

        # 職種・経路
        cat, reason = classify_job(r["job_text"])
        if reason:
            rev.append(reason)
        new["job_category"] = cat or ""
        cat, reason = classify_channel(r["channel_text"])
        if reason:
            rev.append(reason)
        new["channel_new"] = cat or ""

        new["emergency_name"] = r["emergency_name"]
        new["guarantor_name"] = r["guarantor_name"]

        results.append([r, new, rej, rev])

    # 重複（変換後キー）
    groups = defaultdict(list)
    for item in results:
        n = item[1]
        groups[(n["last_name_kana"], n["first_name_kana"], n["birth_date"], n["property_code"])].append(item)
    for key, items in groups.items():
        if len(items) > 1:
            ids = ",".join(i[1]["application_id"] for i in items)
            for i in items:
                i[3].append(f"変換後キー重複(カナ姓+カナ名+生年月日+物件={'/'.join(key)}; 対象={ids})")

    migrated, rejected, review = [], [], []
    for r, new, rej, rev in results:
        if rev:
            reason = "; ".join(rev + [f"[リジェクト条件にも該当] {x}" for x in rej])
            review.append({**r, "review_reason": reason})
        elif rej:
            rejected.append({**r, "reject_reason": "; ".join(rej)})
        else:
            migrated.append(new)

    def write(path, cols, data):
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(data)

    write(OUT_MIGRATED, NEW_COLUMNS, migrated)
    write(OUT_REJECTED, in_columns + ["reject_reason"], rejected)
    write(OUT_REVIEW, in_columns + ["review_reason"], review)

    # 照合
    total = len(migrated) + len(rejected) + len(review)
    in_ids = [r["application_id"] for r in rows]
    out_ids = ([m["application_id"] for m in migrated] + [x["application_id"] for x in rejected]
               + [x["application_id"] for x in review])
    print(f"input={len(rows)} migrated={len(migrated)} rejected={len(rejected)} review={len(review)} sum={total}")
    print("count check:", "OK" if total == len(rows) else "NG")
    print("id check:", "OK" if Counter(in_ids) == Counter(out_ids) else "NG")
    return 0 if total == len(rows) and Counter(in_ids) == Counter(out_ids) else 1


if __name__ == "__main__":
    sys.exit(main())
