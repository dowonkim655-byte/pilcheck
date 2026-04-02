from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import pandas as pd
from itertools import combinations
import re
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="필체크 - 건강기능식품 성분 상호작용 체커")

# ---------------------------------------------------------------------------
# 구글 시트 URL (상호작용 DB)
# ---------------------------------------------------------------------------
SHEETS_INTERACTION_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1mJ8XfI26J31MO11fbVptF-EHRyy6GFxvq5M3ZM42_18"
    "/export?format=csv&gid=1977112602"
)

# ---------------------------------------------------------------------------
# 성분 이름 정규화 (유사 표현 → 통일 표현)
# ---------------------------------------------------------------------------
ALIASES: dict[str, str] = {
    # 비타민류
    "비타민 d": "비타민D", "비타민d": "비타민D", "vit d": "비타민D", "vitd": "비타민D",
    "비타민 c": "비타민C", "비타민c": "비타민C", "vit c": "비타민C", "vitc": "비타민C",
    "비타민 a": "비타민A", "비타민a": "비타민A", "vit a": "비타민A",
    "비타민 k": "비타민K", "비타민k": "비타민K", "비타민 k2": "비타민K", "vit k": "비타민K",
    "비타민 b12": "비타민B12", "비타민b12": "비타민B12", "b12": "비타민B12", "cobalamin": "비타민B12",
    "비타민 b6": "비타민B6", "비타민b6": "비타민B6", "b6": "비타민B6", "pyridoxine": "비타민B6",
    "비타민 b9": "비타민B9", "비타민b9": "비타민B9", "b9": "비타민B9",
    "비타민 b1": "비타민B1", "비타민b1": "비타민B1", "b1": "비타민B1", "thiamine": "비타민B1",
    "비타민 b2": "비타민B2", "비타민b2": "비타민B2", "b2": "비타민B2", "riboflavin": "비타민B2",
    "비타민 b3": "비타민B3", "비타민b3": "비타민B3", "b3": "비타민B3", "niacin": "비타민B3",
    "비타민 b5": "비타민B5", "비타민b5": "비타민B5", "b5": "비타민B5",
    "비타민 b7": "비타민B7", "비타민b7": "비타민B7", "b7": "비타민B7", "biotin": "비타민B7",
    "비오틴": "비타민B7",
    "비타민 e": "비타민E", "비타민e": "비타민E", "vit e": "비타민E",
    # 무기질
    "오메가-3": "오메가3", "omega3": "오메가3", "omega-3": "오메가3", "dha": "오메가3", "epa": "오메가3",
    "마그": "마그네슘", "mg": "마그네슘", "magnesium": "마그네슘",
    "칼": "칼슘", "ca": "칼슘", "calcium": "칼슘",
    "철": "철분", "iron": "철분",
    "아연": "아연", "zinc": "아연", "zn": "아연",
    "구리": "구리", "copper": "구리",
    "셀레늄": "셀레늄", "selenium": "셀레늄", "se": "셀레늄",
    "요오드": "요오드", "iodine": "요오드",
    "칼륨": "칼륨", "potassium": "칼륨",
    "망간": "망간", "manganese": "망간",
    # 기능성 원료
    "엽산": "엽산", "folic": "엽산", "folate": "엽산",
    "코큐텐": "코엔자임Q10", "coq10": "코엔자임Q10", "코q10": "코엔자임Q10", "q10": "코엔자임Q10",
    "밀크 씨슬": "밀크씨슬", "milk thistle": "밀크씨슬", "실리마린": "밀크씨슬",
    "루테": "루테인", "lutein": "루테인",
    "아스타": "아스타잔틴", "astaxanthin": "아스타잔틴",
    "프로바이오": "프로바이오틱스", "유산균": "프로바이오틱스", "probiotics": "프로바이오틱스",
    "와파린": "혈액희석제", "혈전약": "혈액희석제",
    "글루코": "글루코사민", "glucosamine": "글루코사민",
    "콘드": "콘드로이틴", "chondroitin": "콘드로이틴",
    "은행잎": "은행잎추출물", "ginkgo": "은행잎추출물", "ginkgo biloba": "은행잎추출물",
    "녹차": "녹차추출물", "green tea": "녹차추출물",
    "세인트존스": "세인트존스워트", "st johns wort": "세인트존스워트",
    "홍삼": "홍삼", "red ginseng": "홍삼",
    "인삼": "인삼", "ginseng": "인삼",
    "콜라겐": "콜라겐", "collagen": "콜라겐",
    "히알루론산": "히알루론산", "hyaluronic acid": "히알루론산",
    "커큐민": "커큐민", "curcumin": "커큐민", "강황": "커큐민",
    "퀘르세틴": "퀘르세틴", "quercetin": "퀘르세틴",
    "레스베라트롤": "레스베라트롤", "resveratrol": "레스베라트롤",
    "베르베린": "베르베린", "berberine": "베르베린",
    "아쉬와간다": "아쉬와간다", "ashwagandha": "아쉬와간다",
    "카르니틴": "카르니틴", "l-carnitine": "카르니틴", "carnitine": "카르니틴",
    "엘더베리": "엘더베리", "elderberry": "엘더베리",
    "스피루리나": "스피루리나", "spirulina": "스피루리나",
    "클로렐라": "클로렐라", "chlorella": "클로렐라",
    "가르시니아": "가르시니아", "garcinia": "가르시니아",
    "쏘팔메토": "쏘팔메토", "saw palmetto": "쏘팔메토",
    "알로에": "알로에", "aloe": "알로에",
}

# 식품중분류명 → 표준 성분명 매핑
NUTRI_CATEGORY_MAP: dict[str, str] = {
    "EPA 및 DHA 함유 유지": "오메가3",
    "식물성오메가-3지방산": "오메가3",
    "필수지방산": "오메가3",
    "마그네슘": "마그네슘",
    "루테인": "루테인",
    "루테인/루테인지아잔틴": "루테인",
    "밀크씨슬 추출물": "밀크씨슬",
    "비타민 A": "비타민A",
    "비타민 B1": "비타민B1",
    "비타민 B12": "비타민B12",
    "비타민 B2": "비타민B2",
    "비타민 B6": "비타민B6",
    "비타민 C": "비타민C",
    "비타민 D": "비타민D",
    "비타민 E": "비타민E",
    "비타민K": "비타민K",
    "비오틴": "비타민B7",
    "아연": "아연",
    "인삼": "인삼",
    "철": "철분",
    "칼슘": "칼슘",
    "코엔자임Q10": "코엔자임Q10",
    "크롬": "크롬",
    "클로렐라": "클로렐라",
    "스피루리나": "스피루리나",
    "프로바이오틱스": "프로바이오틱스",
    "프로바이오틱스/복합프로바이오틱스": "프로바이오틱스",
    "홍삼": "홍삼",
    "글루코사민": "글루코사민",
    "가르시니아캄보지아 추출물": "가르시니아",
    "히알루론산": "히알루론산",
    "NAG": "글루코사민",
    "은행잎 추출물": "은행잎추출물",
    "녹차 추출물": "녹차추출물",
    "강황 추출물": "커큐민",
    "테아닌": "테아닌",
    "카르니틴": "카르니틴",
    "키토산/키토올리고당": "키토산",
}

# 영양성분 컬럼 → 표준 성분명 (복합제품에서 실제 함량 추출용)
NUTRI_COL_MAP: dict[str, str] = {
    "칼슘(mg)": "칼슘",
    "철(mg)": "철분",
    "비타민 A(μg RAE)": "비타민A",
    "티아민(mg)": "비타민B1",
    "리보플라빈(mg)": "비타민B2",
    "니아신(mg)": "비타민B3",
    "비타민 C(mg)": "비타민C",
    "비타민 D(μg)": "비타민D",
}

LEVEL_EMOJI = {
    "warning": "🔴 경고",
    "caution":  "🟡 주의",
    "positive": "🟢 긍정",
}

LEVEL_MAP: dict[str, str] = {
    "🔴경고": "warning",
    "🟡주의": "caution",
    "🟢긍정": "positive",
}


# ---------------------------------------------------------------------------
# 상호작용 DB 로드
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).parent / "interactions.csv"

def load_db() -> pd.DataFrame:
    df = None
    try:
        raw = pd.read_csv(SHEETS_INTERACTION_URL, dtype=str).fillna("")
        raw = raw.rename(columns={
            "성분A": "ingredient_a",
            "성분B": "ingredient_b",
            "설명": "description",
            "심각도": "level",
        })
        raw["level"] = raw["level"].map(LEVEL_MAP).fillna("")
        df = raw
        logger.info(f"Google Sheets에서 상호작용 DB 로드 완료: {len(df)}건")
    except Exception as e:
        logger.warning(f"Google Sheets 로드 실패, 로컬 CSV 사용: {e}")

    if df is None or df.empty:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str).fillna("")
        logger.info(f"로컬 CSV에서 상호작용 DB 로드 완료: {len(df)}건")

    df["ingredient_a"] = df["ingredient_a"].str.strip()
    df["ingredient_b"] = df["ingredient_b"].str.strip()
    df["level"] = df["level"].str.strip()
    df["description"] = df["description"].str.strip()
    return df


# ---------------------------------------------------------------------------
# 영양성분 DB 로드 (식약처 표준데이터)
# ---------------------------------------------------------------------------
NUTRITION_DB_PATH = Path(__file__).parent / "nutrition_db.csv"

def load_nutrition_db() -> pd.DataFrame | None:
    if not NUTRITION_DB_PATH.exists():
        logger.warning("nutrition_db.csv 없음 — 제품명 조회 기능 비활성화")
        return None
    try:
        df = pd.read_csv(NUTRITION_DB_PATH, encoding="utf-8-sig", dtype=str).fillna("")
        df["식품명_lower"] = df["식품명"].str.lower().str.strip()
        logger.info(f"영양성분 DB 로드 완료: {len(df)}개 제품")
        return df
    except Exception as e:
        logger.warning(f"영양성분 DB 로드 실패: {e}")
        return None


interaction_db: pd.DataFrame = load_db()
nutrition_db: pd.DataFrame | None = load_nutrition_db()


# ---------------------------------------------------------------------------
# 제품명 → 성분 추출
# ---------------------------------------------------------------------------
def _extract_from_row(row: pd.Series) -> list[str]:
    """DB 행에서 성분 목록 추출."""
    ingredients: list[str] = []

    # 1) 식품중분류명 기반
    category = row.get("식품중분류명", "").strip()
    ing = NUTRI_CATEGORY_MAP.get(category)
    if ing:
        ingredients.append(ing)

    # 2) 복합제품은 영양성분 컬럼에서도 추출
    if "복합" in category:
        for col, mapped in NUTRI_COL_MAP.items():
            try:
                val = float(row.get(col, 0) or 0)
                if val > 0 and mapped not in ingredients:
                    ingredients.append(mapped)
            except (ValueError, TypeError):
                pass

    return ingredients


def lookup_product(name: str) -> tuple[str, list[str]]:
    """
    제품명으로 성분 목록 반환.
    Returns: (matched_name, [ingredient, ...])  — 미발견 시 ('', [])
    """
    if nutrition_db is None or nutrition_db.empty:
        return "", []

    key = name.lower().strip()

    # 1) 완전 일치
    matches = nutrition_db[nutrition_db["식품명_lower"] == key]

    # 2) 부분 문자열 포함
    if matches.empty:
        matches = nutrition_db[nutrition_db["식품명_lower"].str.contains(
            re.escape(key), na=False
        )]

    if matches.empty:
        return "", []

    row = matches.iloc[0]
    matched_name = row["식품명"]
    ingredients = _extract_from_row(row)
    return matched_name, ingredients


# ---------------------------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------------------------
def normalize(name: str) -> str:
    key = name.lower().strip()
    return ALIASES.get(key, name.strip())


def parse_ingredients(text: str) -> tuple[list[str], list[str]]:
    """
    성분명 또는 제품명 분리 후 정규화.
    Returns: (ingredients, product_notes)
    - ingredients: 표준 성분명 목록
    - product_notes: '제품명 → 성분' 안내 문자열 목록
    """
    raw = re.split(r"[,，/·\n\t]+", text.strip())
    seen: set[str] = set()
    ingredients: list[str] = []
    product_notes: list[str] = []

    for token in raw:
        token = token.strip()
        if not token:
            continue

        # 1) ALIASES로 정규화 시도
        norm = normalize(token)

        # 2) 정규화 결과가 원래 값과 같으면(= 매핑 없음) 제품명 조회 시도
        if norm.lower() == token.lower():
            matched_name, prod_ings = lookup_product(token)
            if prod_ings:
                note = f"📦 {matched_name} → {', '.join(prod_ings)}"
                product_notes.append(note)
                for ing in prod_ings:
                    if ing not in seen:
                        seen.add(ing)
                        ingredients.append(ing)
                continue

        # 3) 정규화된 성분명 추가
        if norm and norm not in seen:
            seen.add(norm)
            ingredients.append(norm)

    return ingredients, product_notes


def check_interactions(ingredients: list[str]) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {"warning": [], "caution": [], "positive": []}

    # 동일 성분 중복과잉 체크
    for a in ingredients:
        mask = (interaction_db["ingredient_a"] == a) & (interaction_db["ingredient_b"] == a)
        for _, row in interaction_db[mask].iterrows():
            level = row["level"]
            if level in results:
                results[level].append({
                    "pair": f"{a} (중복과잉 주의)",
                    "description": row["description"],
                })

    # 성분 쌍 상호작용 체크
    for a, b in combinations(ingredients, 2):
        mask = (
            ((interaction_db["ingredient_a"] == a) & (interaction_db["ingredient_b"] == b))
            | ((interaction_db["ingredient_a"] == b) & (interaction_db["ingredient_b"] == a))
        )
        for _, row in interaction_db[mask].iterrows():
            level = row["level"]
            if level in results:
                results[level].append({
                    "pair": f"{a} + {b}",
                    "description": row["description"],
                })

    return results


# ---------------------------------------------------------------------------
# 카카오 응답 포맷
# ---------------------------------------------------------------------------
def build_kakao_response(
    ingredients: list[str],
    results: dict,
    product_notes: list[str] | None = None,
) -> dict:
    lines: list[str] = []

    if product_notes:
        for note in product_notes:
            lines.append(note)
        lines.append("")

    lines.append(f"🔍 분석 성분: {', '.join(ingredients)}\n")

    has_any = any(results.values())

    for level in ("warning", "caution", "positive"):
        items = results[level]
        if not items:
            continue
        lines.append(LEVEL_EMOJI[level])
        for item in items:
            lines.append(f"  • {item['pair']}")
            lines.append(f"    {item['description']}")
        lines.append("")

    if not has_any:
        lines.append("✅ 입력한 성분들 사이에 알려진 상호작용이 없습니다.")

    lines.append("⚠️ 본 정보는 참고용이며 의료 전문가와 상담을 권장합니다.")

    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": "\n".join(lines)}}]
        },
    }


def kakao_guide() -> dict:
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "basicCard": {
                        "title": "💊 필체크 사용방법",
                        "description": (
                            "복용 중인 영양제 성분명 또는 제품명을 콤마(,)로 구분해서 입력해주세요!\n\n"
                            "예1) 마그네슘, 칼슘, 비타민D, 오메가3\n"
                            "예2) 힐리 마그네슘 500, 힐리 비타민D 5000"
                        ),
                        "buttons": [
                            {
                                "action": "message",
                                "label": "성분명으로 체크해보기",
                                "messageText": "마그네슘, 칼슘, 비타민D, 오메가3",
                            }
                        ],
                    }
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# 엔드포인트
# ---------------------------------------------------------------------------
@app.post("/webhook")
async def kakao_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    utterance: str = body.get("userRequest", {}).get("utterance", "").strip()
    logger.info(f"입력: {utterance!r}")

    if not utterance:
        return JSONResponse(kakao_guide())

    ingredients, product_notes = parse_ingredients(utterance)

    if len(ingredients) < 2:
        return JSONResponse(kakao_guide())

    results = check_interactions(ingredients)
    return JSONResponse(build_kakao_response(ingredients, results, product_notes))


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "interaction_db_rows": len(interaction_db),
        "nutrition_db_rows": len(nutrition_db) if nutrition_db is not None else 0,
    }


@app.post("/reload")
def reload_db():
    global interaction_db, nutrition_db
    interaction_db = load_db()
    nutrition_db = load_nutrition_db()
    return {
        "status": "reloaded",
        "interaction_db_rows": len(interaction_db),
        "nutrition_db_rows": len(nutrition_db) if nutrition_db is not None else 0,
    }


@app.get("/check")
def check_direct(q: str):
    """
    브라우저/curl에서 바로 테스트.
    예: GET /check?q=마그네슘,칼슘,비타민D
        GET /check?q=힐리 마그네슘 500,힐리 비타민D 5000
    """
    ingredients, product_notes = parse_ingredients(q)
    if len(ingredients) < 2:
        return {"error": "성분을 2개 이상 입력하세요.", "ingredients_found": ingredients}
    results = check_interactions(ingredients)
    return {
        "product_notes": product_notes,
        "ingredients": ingredients,
        "results": results,
    }


@app.get("/search_product")
def search_product(name: str):
    """제품명으로 성분 조회. 예: GET /search_product?name=힐리 마그네슘 500"""
    matched, ings = lookup_product(name)
    if not matched:
        return {"found": False, "query": name}
    return {"found": True, "matched_name": matched, "ingredients": ings}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(port == 8000))
