# cSpell:ignore dotenv genai lastrowid
import json
import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from google import genai
from pydantic import BaseModel, Field

# ==================================================
#  設定
# ==================================================
BASE_DIR = Path(__file__).resolve().parent   # main.py があるフォルダ
DB_PATH = BASE_DIR / "data" / "recipes.db"   # SQLiteのファイル（公開される static/ の外に置く）

# .env ファイルからAPIキーを読み込む（.env は .gitignore に書いてあるのでGitHubに上がらない）
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY が設定されていません。.env.example をコピーして .env を作り、APIキーを書いてください。"
    )

# Gemini APIの初期化
client = genai.Client(api_key=API_KEY)

app = FastAPI()

CANDIDATE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-4-hydrogen",
    "gemma-4-26b-a4b-it",
]


# ==================================================
#  データの形
# ==================================================
class RecipeRequest(BaseModel):
    """ブラウザから送られてくる条件"""
    ingredients: list[str] = []             # 使う食材（空ならおすすめレシピ）
    exclude: list[str] = []                 # 使わない食材
    conditions: list[str] = []              # 条件（時短、ホームパーティーなど）
    servings: int = Field(4, ge=1, le=20)   # 人数
    minutes: int = Field(30, ge=5, le=200)  # 調理時間（分）
    count: int = Field(1, ge=1, le=5)       # レシピ数


# ※ この """説明""" と description は AI にもそのまま渡されるので、AIへの指示として書く
class Nutrition(BaseModel):
    """1人分の栄養素の目安"""
    calories: float = Field(description="カロリー（kcal）")
    fat: float = Field(description="脂質（g）")
    net_carbs: float = Field(description="糖質（g）。炭水化物から食物繊維を引いた量")
    carbs: float = Field(description="炭水化物（g）")
    protein: float = Field(description="タンパク質（g）")
    salt: float = Field(description="塩分（食塩相当量・g）")


class Recipe(BaseModel):
    """レシピ1つ分（AIの出力にも、お気に入りの保存にも使う）"""
    title: str              # 料理名
    description: str        # 紹介文
    time: str               # 調理時間（例: 15分）
    servings: str           # 人数（例: 4人前）
    nutrition: Nutrition    # 1人分の栄養素
    ingredients: list[str]  # 材料
    steps: list[str]        # 作り方
    points: list[str]       # コツ・ポイント


class RecipeList(BaseModel):
    recipes: list[Recipe]


# ==================================================
#  データベース（SQLite）
# ==================================================
def init_db():
    """最初の起動時に data フォルダと favorites テーブルを作る"""
    DB_PATH.parent.mkdir(exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                recipe     TEXT NOT NULL,  -- レシピ全体をJSON文字列で保存
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)
        conn.commit()


init_db()


# ==================================================
#  API：レシピ作成
# ==================================================
def join_items(items: list[str], empty: str) -> str:
    """["キャベツ", "豚肉"] → "キャベツ、豚肉"（空なら empty を返す）"""
    return "、".join(s.strip() for s in items if s.strip()) or empty


@app.post("/api/generate")
def generate_recipe(req: RecipeRequest):
    ingredients = join_items(req.ingredients, "")

    if ingredients:
        # 食材が入力されたとき：その食材を使ったレシピ
        task = f"以下の条件で、家庭で簡単に作れる美味しいレシピを{req.count}つ提案してください。"
        ingredients_line = f"【使いたい食材】{ingredients}"
    else:
        # 食材が空のとき：今の季節に合ったおすすめレシピ
        task = (
            f"今は{datetime.now().month}月です。旬の食材を使った、"
            f"家庭で簡単に作れるおすすめのレシピを{req.count}つ提案してください。"
        )
        ingredients_line = "【使いたい食材】指定なし（旬の食材や、家庭によくある食材から選んでください）"

    try:
        prompt = f"""
        あなたはプロの料理研究家です。{task}

        {ingredients_line}
        【使わない食材】{join_items(req.exclude, "なし")}
        【その他の条件】{join_items(req.conditions, "特になし")}
        【人数】{req.servings}人前
        【調理時間】{req.minutes}分以内

        ルール:
        - 「使わない食材」は材料に入れないでください。
        - 材料の分量は{req.servings}人前で書いてください。
        - 複数のレシピを提案するときは、それぞれ別の料理にしてください。
        - title: 食べたくなるような料理名
        - description: 料理の魅力が伝わる2〜3文の紹介文
        - time: 調理時間（例: 15分）
        - servings: 人数（例: {req.servings}人前）
        - nutrition: 1人分の栄養素の目安を数字だけで（単位は書かない）。
          糖質は炭水化物から食物繊維を引いた量なので、炭水化物より大きくしないでください。
        - ingredients: 材料と分量（例: キャベツ（1/4個））
        - steps: 作り方の手順
        - points: コツ・ポイント（1〜3個）
        """

        response_text = ""

        # 混雑（503など）対策として、最大3回まで再試行するループ
        for attempt in range(3):
            for model_name in CANDIDATE_MODELS:
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_schema": RecipeList,  # この形のJSONで返すようにAIに指定する
                        },
                    )
                    response_text = response.text
                    break
                except Exception as e:
                    print(f"試行 {attempt+1}回目 - モデル {model_name} でエラー: {e}")
                    continue

            if response_text:
                break

            # すべてのモデルがダメだった場合、2秒待ってからリトライ
            print("混雑しているため、2秒後に再試行します...")
            time.sleep(2)

        if not response_text:
            raise RuntimeError("サーバーが混雑しています。少し時間を置いてからもう一度お試しください。")

        # AIの返事が正しい形かチェックしてから返す
        recipes = RecipeList.model_validate_json(response_text).recipes
        return {"recipes": recipes[:req.count]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==================================================
#  API：お気に入り
# ==================================================
@app.get("/api/favorites")
def list_favorites():
    """お気に入り一覧（新しい順）"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        rows = conn.execute("SELECT id, recipe FROM favorites ORDER BY id DESC").fetchall()
    return [{"id": row_id, **json.loads(recipe)} for row_id, recipe in rows]


@app.post("/api/favorites")
def add_favorite(recipe: Recipe):
    """お気に入りに保存"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        # 値は ? で渡す（文字列を直接SQLに埋め込むとSQLインジェクションの危険があるため）
        cursor = conn.execute(
            "INSERT INTO favorites (title, recipe) VALUES (?, ?)",
            (recipe.title, json.dumps(recipe.model_dump(), ensure_ascii=False)),
        )
        conn.commit()
    return {"id": cursor.lastrowid}


@app.delete("/api/favorites/{favorite_id}")
def delete_favorite(favorite_id: int):
    """お気に入りから削除"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.execute("DELETE FROM favorites WHERE id = ?", (favorite_id,))
        conn.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="そのお気に入りは見つかりません。")
    return {"ok": True}


# 静的ファイルのホストはAPIルートより「後」に書く
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")