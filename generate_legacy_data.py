#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データ移行検証：旧データ（賃貸申込CSV）と正解リスト（ground_truth.csv）を生成する。
全てダミーデータ。乱数シード固定で再現可能。
使い方: python3 generate_legacy_data.py
出力: legacy_applications.csv / ground_truth.csv （同じフォルダ）
"""
import csv
import random
import unicodedata

rng = random.Random(20261123)

LAST = [("田中", "タナカ"), ("佐藤", "サトウ"), ("鈴木", "スズキ"), ("高橋", "タカハシ"),
        ("渡辺", "ワタナベ"), ("伊藤", "イトウ"), ("山本", "ヤマモト"), ("中村", "ナカムラ"),
        ("小林", "コバヤシ"), ("加藤", "カトウ"), ("吉田", "ヨシダ"), ("山田", "ヤマダ"),
        ("佐々木", "ササキ"), ("山口", "ヤマグチ"), ("松本", "マツモト"), ("井上", "イノウエ"),
        ("木村", "キムラ"), ("林", "ハヤシ"), ("斎藤", "サイトウ"), ("清水", "シミズ")]
FIRST = [("健太", "ケンタ"), ("翔太", "ショウタ"), ("大輔", "ダイスケ"), ("直樹", "ナオキ"),
         ("和也", "カズヤ"), ("拓也", "タクヤ"), ("美咲", "ミサキ"), ("愛", "アイ"),
         ("結衣", "ユイ"), ("葵", "アオイ"), ("陽菜", "ヒナ"), ("さくら", "サクラ"),
         ("蓮", "レン"), ("悠真", "ユウマ"), ("颯太", "ソウタ"), ("優子", "ユウコ")]
# (都道府県, 郵便番号の先頭3桁, [(市区町村, 番地の町名)])
PREFS = [("東京都", "160", [("新宿区西新宿", "2丁目"), ("渋谷区恵比寿", "1丁目"), ("世田谷区三軒茶屋", "2丁目")]),
         ("神奈川県", "220", [("横浜市西区みなとみらい", "3丁目"), ("川崎市中原区小杉町", "1丁目")]),
         ("大阪府", "530", [("大阪市北区梅田", "1丁目"), ("大阪市天王寺区上本町", "6丁目")]),
         ("愛知県", "460", [("名古屋市中区栄", "3丁目"), ("名古屋市千種区今池", "1丁目")]),
         ("福岡県", "810", [("福岡市中央区天神", "2丁目"), ("福岡市博多区博多駅前", "3丁目")]),
         ("北海道", "060", [("札幌市中央区北一条西", "3丁目"), ("札幌市北区北二十四条西", "5丁目")]),
         ("宮城県", "980", [("仙台市青葉区中央", "2丁目"), ("仙台市宮城野区榴岡", "4丁目")]),
         ("広島県", "730", [("広島市中区紙屋町", "1丁目"), ("広島市西区横川町", "2丁目")])]
PROPS = [("P-101", "パークハイツ青山"), ("P-102", "サンリバー中目黒"), ("P-103", "グランドメゾン栄"),
         ("P-104", "シティコート梅田"), ("P-105", "リバーサイド天神"), ("P-106", "ノースゲート札幌"),
         ("P-107", "ガーデンテラス仙台"), ("P-108", "ベイビュー横浜"), ("P-109", "サンシャイン今池"),
         ("P-110", "アーバンライフ博多")]
# 旧ステータス: 1受付 2審査中 4承認 5却下 6取消 7契約済 （3保留は欠陥としてのみ植える）
STATUSES = [1, 2, 2, 4, 4, 4, 5, 6, 7, 7]
# 旧業種: A製造 B建設 C IT D小売・サービス E医療・福祉 F公務・教育 （Gその他は欠陥としてのみ植える）
INDUSTRIES = ["A", "B", "C", "C", "D", "D", "E", "F"]
JOB_TEXT = {
    "A": ["自動車部品メーカー勤務", "食品工場の製造ライン", "電機メーカーの生産技術"],
    "B": ["建設会社の現場監督", "ゼネコンの施工管理", "土木作業員"],
    "C": ["IT企業のSE", "Webサービスの開発者", "SIerでプログラマ"],
    "D": ["小売店の店長", "飲食店勤務", "コンビニの店員"],
    "E": ["病院の看護師", "介護施設の職員", "薬局の薬剤師"],
    "F": ["市役所の職員", "公立学校の教員", "県庁勤務"],
}
CHANNEL_TEXT = ["SUUMOで見ました", "不動産ポータルで検索", "駅前の店舗に寄った", "知人の紹介です",
                "チラシを見て", "会社の人事経由", "御社のホームページから", "通りがかりに看板を見て"]

FIELDS = ["application_id", "last_name", "first_name", "last_name_kana", "first_name_kana",
          "birth_date", "postal_code", "prefecture", "address", "phone",
          "property_code", "property_name", "room_no", "rent", "application_date",
          "status_old", "industry_old", "job_text", "channel_text",
          "emergency_name", "emergency_phone", "emergency_address",
          "guarantor_name", "guarantor_address"]

def rand_date(y0, y1):
    y = rng.randint(y0, y1)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    return y, m, d

def fmt_slash(y, m, d):
    return f"{y}/{m:02d}/{d:02d}"

def base_row(i):
    ln, lnk = rng.choice(LAST)
    fn, fnk = rng.choice(FIRST)
    by, bm, bd = rand_date(1965, 2005)
    pref, zip3, cities = rng.choice(PREFS)
    city, chome = rng.choice(cities)
    postal = f"{zip3}{rng.randint(0, 9999):04d}"
    address = f"{city}{chome}{rng.randint(1, 30)}-{rng.randint(1, 20)}"
    phone = f"090-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    pcode, pname = rng.choice(PROPS)
    # 申込日はデータ抽出日（2026-11-20）以前に限る。抽出日より未来の申込日は実在しないため
    from datetime import date, timedelta
    ay, am, ad = (date(2024, 1, 1) + timedelta(
        days=rng.randint(0, (date(2026, 11, 20) - date(2024, 1, 1)).days))).timetuple()[:3]
    ind = rng.choice(INDUSTRIES)
    gln, _ = rng.choice(LAST)
    return {
        "application_id": f"A-{i:05d}",
        "last_name": ln, "first_name": fn,
        "last_name_kana": lnk, "first_name_kana": fnk,
        "birth_date": fmt_slash(by, bm, bd),
        "postal_code": postal,
        "prefecture": pref,
        "address": address,
        "phone": phone,
        "property_code": pcode, "property_name": pname,
        "room_no": str(rng.randint(101, 1205)),
        "rent": str(rng.randrange(45000, 180001, 1000)),
        "application_date": fmt_slash(ay, am, ad),
        "status_old": str(rng.choice(STATUSES)),
        "industry_old": ind,
        "job_text": rng.choice(JOB_TEXT[ind]),
        "channel_text": rng.choice(CHANNEL_TEXT),
        "emergency_name": f"{gln} 花子",
        "emergency_phone": f"080-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}",
        "emergency_address": f"{pref}{address}",
        "guarantor_name": f"{gln} 一郎",
        "guarantor_address": f"{pref}{address}",
    }

rows = [base_row(i) for i in range(1, 2001)]
by_id = {r["application_id"]: r for r in rows}
truth = []  # (application_id, defect_type, field, expected, detail)

def pick(n, used):
    out = []
    ids = list(by_id.keys())
    rng.shuffle(ids)
    for aid in ids:
        if aid not in used:
            used.add(aid)
            out.append(aid)
            if len(out) == n:
                break
    return out

used = set()

# 1. 日付形式の混在 (8) -> convert
for aid in pick(8, used):
    r = by_id[aid]
    y, m, d = map(int, r["application_date"].split("/"))
    kind = rng.choice(["yyyymmdd", "wareki", "mdy"])
    if kind == "yyyymmdd":
        r["application_date"] = f"{y}{m:02d}{d:02d}"
    elif kind == "wareki":
        r["application_date"] = f"R{y - 2018}.{m}.{d}"
    else:
        r["application_date"] = f"{m:02d}/{d:02d}/{y}"
    truth.append((aid, "date_format", "application_date", "convert", kind))

# 2. 全角・半角の混在 (5) -> convert
for aid in pick(5, used):
    r = by_id[aid]
    r["first_name_kana"] = unicodedata.normalize("NFKC", r["first_name_kana"])  # 半角カナ化
    truth.append((aid, "width_mix", "first_name_kana", "convert", "halfwidth_kana"))

# 3. 氏名カナの表記ゆれ (5) -> convert
KANA_VAR = [("ョ", "ヨ"), ("ャ", "ヤ"), ("ュ", "ユ"), ("ッ", "ツ"), ("ヶ", "ケ")]
for aid in pick(5, used):
    r = by_id[aid]
    k = r["last_name_kana"]
    for a, b in KANA_VAR:
        if a in k:
            r["last_name_kana"] = k.replace(a, b)
            break
    else:
        r["last_name_kana"] = k + " "
    truth.append((aid, "kana_variant", "last_name_kana", "convert", "small_kana_or_space"))

# 4. 郵便番号の形式 (5) -> convert
for aid in pick(5, used):
    r = by_id[aid]
    z = r["postal_code"]
    if z.startswith("0"):
        r["postal_code"] = z[1:]  # 先行ゼロ欠落
        detail = "leading_zero_lost"
    else:
        r["postal_code"] = z[:3] + "-" + z[3:]
        detail = "hyphen"
    truth.append((aid, "postal_format", "postal_code", "convert", detail))

# 5. 電話番号の形式 (4) -> convert
for aid in pick(4, used):
    r = by_id[aid]
    if rng.random() < 0.5:
        r["phone"] = "+81-" + r["phone"][1:]
        detail = "plus81"
    else:
        r["phone"] = r["phone"].replace("-", " ")
        detail = "space_separator"
    truth.append((aid, "phone_format", "phone", "convert", detail))

# 6. 必須の欠損 (4) -> reject
for aid, field in zip(pick(4, used), ["application_date", "application_date", "property_code", "property_code"]):
    by_id[aid][field] = ""
    truth.append((aid, "missing_required", field, "reject", "empty"))

# 7. 重複登録 (3組) -> review（複製行を追加）
dup_sources = pick(3, used)
for j, aid in enumerate(dup_sources):
    src = by_id[aid]
    new_id = f"A-{2001 + j:05d}"
    dup = dict(src)
    dup["application_id"] = new_id
    dup["application_date"] = src["application_date"]
    rows.append(dup)
    by_id[new_id] = dup
    truth.append((f"{aid}+{new_id}", "duplicate", "application_id", "review", "same_person_same_property"))

# 8. ステータス保留で判別不能 (4) -> review
for aid in pick(4, used):
    by_id[aid]["status_old"] = "3"
    truth.append((aid, "status_hold", "status_old", "review", "old3_maps_to_screening_or_doc_wait"))

# 9. 業種「その他」で判別不能 (3) -> review
for aid in pick(3, used):
    by_id[aid]["industry_old"] = "G"
    by_id[aid]["job_text"] = rng.choice(["いろいろやってます", "フリーランス", "個人事業"])
    truth.append((aid, "industry_other", "industry_old", "review", "old_G_unclassifiable"))

# 10. 自由記述の分類不能・曖昧 (4) -> review
for aid, field, val in zip(pick(4, used),
                           ["channel_text", "channel_text", "job_text", "job_text"],
                           ["なんとなく", "通りがかりに", "仕事してます", "会社員のようなもの"]):
    by_id[aid][field] = val
    truth.append((aid, "freetext_ambiguous", field, "review", "unclassifiable_text"))

# 11. 金額の表記 (3) -> convert
for aid in pick(3, used):
    r = by_id[aid]
    if rng.random() < 0.5:
        r["rent"] = f"{int(r['rent']):,}"
        detail = "comma"
    else:
        r["rent"] = unicodedata.normalize("NFKC", str(r["rent"])) if False else "".join(
            chr(0xFF10 + int(c)) if c.isdigit() else c for c in r["rent"])
        detail = "fullwidth_digits"
    truth.append((aid, "rent_format", "rent", "convert", detail))

# 12. 住所の表記：都道府県の省略 (3) -> convert（市区町村から補完可能なもの）
OMIT = {"札幌市": "北海道", "仙台市": "宮城県", "福岡市": "福岡県"}
candidates = [r["application_id"] for r in rows
              if r["application_id"] not in used and any(r["address"].startswith(c) for c in OMIT)]
rng.shuffle(candidates)
for aid in candidates[:3]:
    used.add(aid)
    r = by_id[aid]
    r["prefecture"] = ""
    truth.append((aid, "prefecture_omitted", "prefecture", "convert", "infer_from_city"))

# 13. 不正値 (3) -> reject
inv = pick(3, used)
by_id[inv[0]]["birth_date"] = "1985/02/30"
truth.append((inv[0], "invalid_value", "birth_date", "reject", "feb30"))
by_id[inv[1]]["application_date"] = "2027/01/15"
truth.append((inv[1], "invalid_value", "application_date", "reject", "future_date"))
by_id[inv[2]]["rent"] = "3000"
truth.append((inv[2], "invalid_value", "rent", "reject", "rent_out_of_range"))

# 14. 外国語の氏名・住所 (5) -> review
fr = pick(5, used)
r = by_id[fr[0]]
r["prefecture"] = "California"
r["address"] = "123 Main St, Los Angeles, CA 90012"
r["postal_code"] = "90012"
truth.append((fr[0], "foreign_address", "address", "review", "applicant_address_USA"))
r = by_id[fr[1]]
r["last_name"], r["first_name"] = "SMITH", "John"
r["last_name_kana"], r["first_name_kana"] = "スミス", "ジョン"
r["prefecture"] = "Ontario"
r["address"] = "55 King St, Toronto, ON M5H 1J9"
r["postal_code"] = "M5H1J9"
truth.append((fr[1], "foreign_address", "address", "review", "applicant_name_and_address_Canada"))
r = by_id[fr[2]]
r["emergency_address"] = "10 George St, Sydney NSW 2000, Australia"
r["emergency_phone"] = "+61-2-0000-0000"
truth.append((fr[2], "foreign_address", "emergency_address", "review", "emergency_contact_Australia"))
r = by_id[fr[3]]
r["guarantor_name"] = "LEE Minjun"
r["guarantor_address"] = "77 Sejong-daero, Jongno-gu, Seoul, South Korea"
truth.append((fr[3], "foreign_address", "guarantor_address", "review", "guarantor_Korea"))
r = by_id[fr[4]]
r["guarantor_name"] = "Emma Wilson"
r["guarantor_address"] = "221B Baker Street, London NW1 6XE, United Kingdom"
truth.append((fr[4], "foreign_address", "guarantor_address", "review", "guarantor_UK"))

with open("legacy_applications.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

with open("ground_truth.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["application_id", "defect_type", "field", "expected", "detail"])
    w.writerows(truth)

from collections import Counter
print(f"rows: {len(rows)}")
print(f"ground_truth entries: {len(truth)}")
for k, v in sorted(Counter(t[1] for t in truth).items()):
    print(f"  {k}: {v}")
for k, v in sorted(Counter(t[3] for t in truth).items()):
    print(f"expected {k}: {v}")
