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
# 성분 이름 정규화 (유사 표현 → 통일 표현)
# ---------------------------------------------------------------------------
ALIASES: dict[str, str] = {
    "비타민 d": "비타민D", "비타민d": "비타민D", "vit d": "비타민D", "vitd": "비타민D",
    "비타민 c": "비타민C", "비타민c": "비타민C", "vit c": "비타민C", "vitc": "비타민C",
    "비타민 a": "비타민A", "비타민a": "비타민A",
    "비타민 k": "비타민K", "비타민k": "비타민K", "비타민 k2": "비타민K",
    "비타민 b12": "비타민B12", "비타민b12": "비타민B12",
    "오메가-3": "오메가3", "omega3": "오메가3", "omega-3": "오메가3", "dha": "오메가3", "epa": "오메가3",
    "마그": "마그네슘", "mg": "마그네슘",
    "칼": "칼슘", "ca": "칼슘", "calcium": "칼슘",
    "철": "철분", "iron": "철분",
    "아연": "아연", "zinc": "아연", "zn": "아연",
    "구리": "구리", "copper": "구리",
    "엽산": "엽산", "folic": "엽산", "folate": "엽산",
    "코큐텐": "코엔자임Q10", "coq10": "코엔자임Q10", "코q10": "코엔자임Q10",
    "밀크 씨슬": "밀크씨슬", "milk thistle": "밀크씨슬",
    "루테": "루테인", "lutein": "루테인",
    "아스타": "아스타잔틴", "astaxanthin": "아스타잔틴",
    "프로바이오": "프로바이오틱스", "유산균": "프로바이오틱스",
    "와파린": "혈액희석제", "혈전약": "혈액희석제",
    "글루코": "글루코사민",
    "은행잎": "은행잎추출물", "ginkgo": "은행잎추출물",
    "녹차": "녹차추출물", "green tea": "녹차추출물",
    "세인트존스": "세인트존스워트", "st johns wort": "세인트존스워트",
}

LEVEL_EMOJI = {
    "warning": "🔴 경고",
    "caution":  "🟡 주의",
    "positive": "🟢 긍정",
}


# ---------------------------------------------------------------------------
# 상호작용 DB 로드
# ---------------------------------------------------------------------------
CSV_PATH = Path(__file__).parent / "interactions.csv"

def load_db() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str).fillna("")
    df["ingredient_a"] = df["ingredient_a"].str.strip()
    df["ingredient_b"] = df["ingredient_b"].str.strip()
    df["level"] = df["level"].str.strip()
    df["description"] = df["description"].str.strip()
    logger.info(f"상호작용 DB 로드 완료: {len(df)}건")
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
        return JSONResponse(kakao_simple("성분명을 입력해주세요.\n예시: 마그네슘, 칼슘, 비타민D"))

    ingredients = parse_ingredients(utterance)

    if len(ingredients) < 2:
        msg = (
            f"'{ingredients[0]}' 성분을 인식했습니다.\n"
            "상호작용 확인을 위해 성분을 2개 이상 입력해주세요.\n"
            "예시: 마그네슘, 칼슘, 비타민D"
        ) if ingredients else "성분을 인식하지 못했습니다. 다시 입력해주세요."
        return JSONResponse(kakao_simple(msg))

    results = check_interactions(ingredients)
    return JSONResponse(build_kakao_response(ingredients, results))


@app.get("/health")
def health_check():
    return {"status": "ok", "db_rows": len(interaction_db)}


@app.post("/reload")
def reload_db():
    """CSV 수정 후 재로드 (서버 재시작 없이)."""
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
