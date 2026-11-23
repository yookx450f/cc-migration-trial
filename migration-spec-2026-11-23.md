# 移行仕様書（賃貸申込データ 旧→新）

この仕様だけを根拠に変換プログラムを作成する。仕様に書かれていない判断は、変換プログラム側で勝手に決めず「要確認」に回すこと。

## 1. 入出力
- 入力：`legacy_applications.csv`（UTF-8、ヘッダあり）
- 出力は3ファイル。全ての入力行は、いずれか1つだけに振り分けられること：
  - `migrated.csv`：移行成功（新形式）
  - `rejected.csv`：リジェクト（元の行＋ `reject_reason` 列）
  - `review.csv`：要確認（元の行＋ `review_reason` 列）
- 件数照合：入力件数 ＝ migrated ＋ rejected ＋ review であること

## 2. 移行先の形式（migrated.csv の列）
application_id, last_name, first_name, last_name_kana, first_name_kana, birth_date,
country_code, postal_code, prefecture_code, address_line, phone,
property_code, room_no, rent_yen, application_date, status_new, industry_new,
job_category, channel_new,
emergency_name, emergency_phone, guarantor_name

- birth_date / application_date：ISO形式（yyyy-mm-dd）
- postal_code：7桁の文字列
- prefecture_code：都道府県名（例：東京都）※コード表は持たないため名称で保持する
- phone：ハイフンなし数字。日本の番号は先頭0始まり
- rent_yen：円単位の整数
- country_code：日本の住所は JP

## 3. 項目別の変換ルール

### 氏名・カナ
- 氏名（漢字等）はそのまま保持する
- カナは半角カナを全角カナに変換し、前後の空白を取り除く
- カナの拗音・促音の大書き表記（ャュョッヶの大文字形）は、正規の小書きに戻す

### 日付（birth_date / application_date）
次の形式を受け付ける：
- yyyy/mm/dd、yyyy-mm-dd
- 8桁数字 yyyymmdd
- 和暦「R○.○.○」（R＝令和。令和○年＝2018＋○年）
- mm/dd/yyyy（月／日／年の順）
検証：実在する日付であること。application_date が移行実施日（2026-11-23）より未来の場合はリジェクト。birth_date が実在しない日付の場合はリジェクト。

### 郵便番号
- ハイフンを取り除く
- 6桁の場合は先頭に 0 を補って7桁にする（先行ゼロ欠落の復元）
- 7桁の数字にならない場合は要確認

### 住所・都道府県
- prefecture が空の場合、address の先頭の市区町村名から推定する（札幌市→北海道、仙台市→宮城県、福岡市→福岡県、その他はデータ内の市区町村と都道府県の対応から）。推定できない場合は要確認
- prefecture が日本の都道府県名でない場合、その行は要確認（外国住所。取り込みは人が判断する）
- 緊急連絡先・保証人の住所が日本の住所形式でない（都道府県名を含まない英字住所等）場合も、その行は要確認

### 電話番号
- ハイフンと空白を取り除く
- 先頭が +81 の場合は 0 に置き換える（日本の番号として正規化）
- それ以外の国番号（+61 等）で始まる番号を含む行は要確認
- 正規化後に 0 で始まる10〜11桁でない場合は要確認

### 家賃（rent → rent_yen）
- カンマと「円」を取り除き、全角数字は半角に変換して整数化する
- 10,000〜1,000,000 の範囲外はリジェクト

### ステータス（status_old → status_new）
| 旧 | 新 |
|---|---|
| 1 | RECEIVED |
| 2 | SCREENING |
| 3 | （変換しない。要確認：新の SCREENING か DOC_WAIT かを旧データから判別できないため） |
| 4 | APPROVED |
| 5 | REJECTED |
| 6 | CANCELLED |
| 7 | CONTRACTED |

### 業種（industry_old → industry_new）
| 旧 | 新 |
|---|---|
| A | MANUFACTURING |
| B | CONSTRUCTION |
| C | IT |
| D | RETAIL_SERVICE |
| E | MEDICAL_WELFARE |
| F | PUBLIC_EDUCATION |
| G | （変換しない。要確認：新では複数区分に分かれ判別できないため） |

### 職種区分（job_text → job_category）
自由記述を次のキーワードで分類する。複数に該当する場合は先に書かれた方を優先する。どれにも該当しない場合は要確認。
- 公務員：市役所、県庁、公立、教員、職員（ただし病院・施設の職員は除く）
- 会社員：勤務、SE、プログラマ、開発者、店長、店員、看護師、薬剤師、介護施設の職員、介護、現場監督、施工管理、作業員、生産技術、製造ライン
- 自営業：個人事業、自営業、フリーランス
（その他の区分＝会社役員／契約・派遣／パート・アルバイト／学生／年金受給 は、今回のデータではキーワードを定義しない。該当しそうな記述があっても、キーワードが無ければ要確認にする）

### 申込経路（channel_text → channel_new）
自由記述を次のキーワードで分類する。どれにも該当しない場合は要確認。
- PORTAL：ポータル、SUUMO、ホームページ
- STORE：店舗、寄った、看板
- REFERRAL：紹介
- FLYER：チラシ
- CORPORATE：人事、法人

### 必須項目
- application_id、last_name、first_name、property_code、application_date が空の行はリジェクト

### 重複
- 変換後のキー（last_name_kana＋first_name_kana＋birth_date＋property_code）が重複する行は、自動で削除せず、全て要確認に回す

## 4. 実装条件
- Python 標準ライブラリのみで実装する
- 入力ファイルを変更しない
- 振り分けの理由は rejected.csv / review.csv の理由列に1行ずつ記録する
