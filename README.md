# Recitopia

冷蔵庫にある食材を入力すると、Gemini API がレシピを提案してくれる Web アプリです。

## 主な機能

- 使う食材・使わない食材・条件・人数・調理時間・レシピ数を指定してレシピを作成
- 使う食材が空欄のときは、季節に合ったおすすめレシピを提案
- 1人分の栄養素（カロリー・脂質・糖質・炭水化物・タンパク質・塩分）を表示
- 気に入ったレシピをお気に入りに保存・削除

## 使用技術

| 種類 | 使ったもの |
| --- | --- |
| フロントエンド | HTML / CSS / JavaScript |
| バックエンド | Python（FastAPI） |
| AI | Gemini API（google-genai） |
| データベース | SQLite |

## 必要なもの

- Python 3.11 以上
- Gemini API キー（[Google AI Studio](https://aistudio.google.com/app/apikey) で作成できます）

## セットアップ（最初の1回だけ）

### 1. Python をインストールする

[Python 公式サイト](https://www.python.org/downloads/) からダウンロードしてインストールします。

インストール画面に次の項目が表示されたら、2つともチェックを入れてください。

- [x] Use admin privileges when installing py.exe
- [x] Add python.exe to PATH

ターミナルで次のコマンドを打ち、`Python 3.11` 以上のバージョンが表示されれば OK です。

```bash
python --version
```

### 2. このリポジトリをダウンロードする

```bash
git clone https://github.com/ユーザー名/Recitopia.git
cd Recitopia
```

Git を使わない場合は、GitHub の「Code」→「Download ZIP」でダウンロードして展開し、ターミナルでそのフォルダに移動します。

### 3. ライブラリをインストールする

```bash
python -m pip install -r requirements.txt
```

### 4. API キーを設定する

`.env.example` をコピーして `.env` という名前のファイルを作ります。

```bash
# Windows
copy .env.example .env

# Mac
cp .env.example .env
```

`.env` を開いて、自分の API キーを書きます。

```
GEMINI_API_KEY=ここにAPIキー
```

> [!WARNING]
> `.env` は GitHub に上げないでください。`.gitignore` で除外しています。

## 起動方法

このフォルダでターミナルを開き、次のコマンドを打ちます。

```bash
python -m uvicorn main:app --reload
```

ブラウザで [http://127.0.0.1:8000](http://127.0.0.1:8000) を開きます。止めるときはターミナルで `Ctrl + C` を押します。

## フォルダ構成

```
Recitopia/
├── main.py            # サーバー（API・データベース）
├── requirements.txt   # 必要なライブラリの一覧
├── .env.example       # APIキーの見本
├── .gitignore         # GitHubに上げないファイルの一覧
├── data/              # SQLiteのデータベース（初めて起動したときに自動で作成）
└── static/
    ├── index.html     # 画面
    └── style.css      # デザイン
```

## 注意

- 栄養素は AI が計算した目安です。
- レシピは AI が毎回考えるため、内容は毎回変わります。アレルギーがある場合は、材料を必ず自分で確認してください。