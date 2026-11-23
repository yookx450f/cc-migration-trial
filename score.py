#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データ移行検証：採点スクリプト。
ground_truth.csv（正解リスト）と変換結果3ファイル（migrated/rejected/review）を突合し、
欠陥の種類ごとに「正しく処理できた／すり抜けた／誤検出」を数える。
あわせて migrated.csv の全行に形式チェック（突合チェック）をかける。
使い方: python3 score.py
"""
import csv
import re
from collections import defaultdict

def load_ids(path):
    with open(path, encoding="utf-8") as f:
        return [r["application_id"] for r in csv.DictReader(f)]

def load_rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

truth = load_rows("ground_truth.csv")
migrated = load_rows("migrated.csv")
migrated_ids = {r["application_id"] for r in migrated}
rejected_ids = set(load_ids("rejected.csv"))
review_ids = set(load_ids("review.csv"))

actual = {}
for aid in migrated_ids:
    actual[aid] = "convert"
for aid in rejected_ids:
    actual[aid] = "reject"
for aid in review_ids:
    actual[aid] = "review"

per_type = defaultdict(lambda: {"ok": 0, "ng": 0, "ng_list": []})
for t in truth:
    expected = t["expected"]
    ids = t["application_id"].split("+")  # 重複は "A-xxxxx+A-0200x" 形式
    got = [actual.get(i, "missing") for i in ids]
    if all(g == expected for g in got):
        per_type[t["defect_type"]]["ok"] += 1
    else:
        per_type[t["defect_type"]]["ng"] += 1
        per_type[t["defect_type"]]["ng_list"].append(
            f'{t["application_id"]} expected={expected} got={got}')

# 誤検出：正解リストに無いのに rejected / review に入った行
truth_ids = set()
for t in truth:
    truth_ids.update(t["application_id"].split("+"))
false_positives = sorted((rejected_ids | review_ids) - truth_ids)

print("=== 欠陥の種類ごとの採点（正解リストとの突合）===")
total_ok = total_ng = 0
for dtype in sorted(per_type):
    s = per_type[dtype]
    total_ok += s["ok"]
    total_ng += s["ng"]
    mark = "OK " if s["ng"] == 0 else "NG "
    print(f'{mark}{dtype}: 正しく処理 {s["ok"]} / すり抜け等 {s["ng"]}')
    for line in s["ng_list"]:
        print(f'    {line}')
print(f'合計: {total_ok + total_ng}件中 {total_ok}件 正しく処理')
print()
print(f'=== 誤検出（欠陥でないのに止めた行）: {len(false_positives)}件 ===')
for aid in false_positives:
    print(f'  {aid} -> {actual[aid]}')
print()
print("=== migrated.csv の形式チェック（全行）===")
problems = []
STATUS = {"RECEIVED", "SCREENING", "APPROVED", "REJECTED", "CANCELLED", "CONTRACTED"}
INDUSTRY = {"MANUFACTURING", "CONSTRUCTION", "IT", "RETAIL_SERVICE", "MEDICAL_WELFARE", "PUBLIC_EDUCATION"}
JOB = {"公務員", "会社員", "自営業"}
CHANNEL = {"PORTAL", "STORE", "REFERRAL", "FLYER", "CORPORATE"}
for r in migrated:
    aid = r["application_id"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["birth_date"] or ""):
        problems.append(f'{aid}: birth_date not ISO: {r["birth_date"]}')
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["application_date"] or ""):
        problems.append(f'{aid}: application_date not ISO: {r["application_date"]}')
    if not re.fullmatch(r"\d{7}", r["postal_code"] or ""):
        problems.append(f'{aid}: postal_code not 7 digits: {r["postal_code"]}')
    if not re.fullmatch(r"0\d{9,10}", r["phone"] or ""):
        problems.append(f'{aid}: phone not normalized: {r["phone"]}')
    try:
        rent = int(r["rent_yen"])
        if not (10000 <= rent <= 1000000):
            problems.append(f'{aid}: rent out of range: {rent}')
    except Exception:
        problems.append(f'{aid}: rent_yen not integer: {r["rent_yen"]}')
    if r["status_new"] not in STATUS:
        problems.append(f'{aid}: status_new invalid: {r["status_new"]}')
    if r["industry_new"] not in INDUSTRY:
        problems.append(f'{aid}: industry_new invalid: {r["industry_new"]}')
    if r["job_category"] not in JOB:
        problems.append(f'{aid}: job_category invalid: {r["job_category"]}')
    if r["channel_new"] not in CHANNEL:
        problems.append(f'{aid}: channel_new invalid: {r["channel_new"]}')
    if r["country_code"] != "JP":
        problems.append(f'{aid}: country_code not JP: {r["country_code"]}')
print(f'対象 {len(migrated)}行 / 形式の問題 {len(problems)}件')
for p in problems[:30]:
    print(f'  {p}')
