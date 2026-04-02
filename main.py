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
# 구글 시트 URL (공개 공유 설정 필요)
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
    "비타민 b7": "비타민B7", "비타민b7": "비타민B7", "b7": "비타민B7", "biotin": "비타민B7", "비오틴": "비타민B7",
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

LEVEL_EMOJI = {
    "warning": "🔴 경고",
    "caution":  "🟡 주의",
    "positive": "🟢 긍정",
}

# 구글 시트 심각도 → 내부 레벨 매핑
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

    # 1) 구글 시트에서 로드 시도
    try:
        raw = pd.read_csv(SHEETS_INTERACTION_URL, dtype=str).fillna("")
        # Sheet 2 컬럼: 성분A, 성분B, 상호작용유형, 설명, 심각도, 출처
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

    # 2) 폴백: 로컬 CSV
    if df is None or df.empty:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str).fillna("")
        logger.info(f"로컬 CSV에서 상호작용 DB 로드 완료: {len(df)}건")

    df["ingredient_a"] = df["ingredient_a"].str.strip()
    df["ingredient_b"] = df["ingredient_b"].str.strip()
    df["level"] = df["level"].str.strip()
    df["description"] = df["description"].str.strip()
    return df


interaction_db: pd.DataFrame = load_db()


# ---------------------------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------------------------
def normalize(name: str) -> str:
    """소문자 변환 후 별칭 딕셔너리에서 표준 이름으로 변환."""
    key = name.lower().strip()
    return ALIASES.get(key, name.strip())


def parse_ingredients(text: str) -> list[str]:
    """콤마·공백·슬래시 등 구분자로 성분 분리 후 정규화."""
    raw = re.split(r"[,，/·\n\t]+", text.strip())
    seen = set()
    result = []
    for token in raw:
        token = token.strip()
        if not token:
            continue
        norm = normalize(token)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return result


def check_interactions(ingredients: list[str]) -> dict[str, list[dict]]:
    results: dict[str, list[dict]] = {"warning": [], "caution": [], "positive": []}

    # 1) 동일 성분 중복과잉 체크 (성분A == 성분B인 행)
    for a in ingredients:
        mask = (interaction_db["ingredient_a"] == a) & (interaction_db["ingredient_b"] == a)
        for _, row in interaction_db[mask].iterrows():
            level = row["level"]
            if level in results:
                results[level].append({
                    "pair": f"{a} (중복과잉 주의)",
                    "description": row["description"],
                })

    # 2) 성분 쌍 상호작용 체크
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
def build_kakao_response(ingredients: list[str], results: dict) -> dict:
    lines: list[str] = []
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
        lines.append("")  # 빈 줄 구분

    if not has_any:
        lines.append("✅ 입력한 성분들 사이에 알려진 상호작용이 없습니다.")

    lines.append("⚠️ 본 정보는 참고용이며 의료 전문가와 상담을 권장합니다.")

    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": "\n".join(lines)}}
            ]
        },
    }


def kakao_simple(text: str) -> dict:
    return {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": text}}]},
    }


def kakao_guide() -> dict:
    """성분 미입력 또는 1개 입력 시 안내 + 버튼 응답."""
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "basicCard": {
                        "title": "💊 필체크 사용방법",
                        "description": "복용 중인 영양제 성분을 콤마(,)로 구분해서 입력해주세요!\n\n예) 마그네슘, 칼슘, 비타민D, 오메가3",
                        "buttons": [
                            {
                                "action": "message",
                                "label": "예시로 체크해보기",
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
    """카카오 오픈빌더 웹훅 엔드포인트."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    utterance: str = body.get("userRequest", {}).get("utterance", "").strip()
    logger.info(f"입력: {utterance!r}")

    if not utterance:
        return JSONResponse(kakao_guide())

    ingredients = parse_ingredients(utterance)

    if len(ingredients) < 2:
        return JSONResponse(kakao_guide())

    results = check_interactions(ingredients)
    return JSONResponse(build_kakao_response(ingredients, results))


@app.get("/health")
def health_check():
    return {"status": "ok", "db_rows": len(interaction_db), "source": "google_sheets" if len(interaction_db) > 31 else "local_csv"}


@app.post("/reload")
def reload_db():
    """CSV/시트 수정 후 재로드 (서버 재시작 없이)."""
    global interaction_db
    interaction_db = load_db()
    return {"status": "reloaded", "db_rows": len(interaction_db)}


# ---------------------------------------------------------------------------
# 로컬 테스트용 직접 호출 엔드포인트
# ---------------------------------------------------------------------------
@app.get("/check")
def check_direct(q: str):
    """
    브라우저/curl에서 바로 테스트 가능.
    예: GET /check?q=마그네슘,칼슘,비타민D
    """
    ingredients = parse_ingredients(q)
    if len(ingredients) < 2:
        return {"error": "성분을 2개 이상 입력하세요."}
    results = check_interactions(ingredients)
    return {
        "ingredients": ingredients,
        "results": results,
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=(port == 8000))
