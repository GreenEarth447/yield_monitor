from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import List, Literal, Optional, Tuple
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func
from sqlalchemy.orm import Session

from database import ManualTest, get_db, init_db

ALLOWED_PART_NUMBERS = ("001PN001", "002PN002", "003PN003")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Yield Monitor", lifespan=lifespan)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class TestIn(BaseModel):
    serial_number: str = Field(..., min_length=1)
    part_number: Literal["001PN001", "002PN002", "003PN003"]
    status: bool = False


class TestOut(BaseModel):
    id: int
    serial_number: str
    part_number: str
    timestamp: datetime
    status: bool

    class Config:
        from_attributes = True


class StatRow(BaseModel):
    part_number: str
    tested: int
    passed: int
    failed: int
    yield_pct: float


class DailyRow(BaseModel):
    date: str
    count: int


def _resolve_range(
    from_: Optional[date], to_: Optional[date]
) -> Tuple[Optional[datetime], Optional[datetime]]:

    if from_ and to_ and from_ > to_:
        raise HTTPException(status_code=400, detail="`from` must be on or before `to`")
    start = datetime.combine(from_, datetime.min.time()) if from_ else None
    end_exclusive = (
        datetime.combine(to_ + timedelta(days=1), datetime.min.time()) if to_ else None
    )
    return start, end_exclusive


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/script", response_class=PlainTextResponse)
def script() -> str:
    return (BASE_DIR / "test_yield.py").read_text(encoding="utf-8")


@app.post("/tests", response_model=TestOut)
def create_test(payload: TestIn, db: Session = Depends(get_db)) -> TestOut:
    record = ManualTest(
        serial_number=payload.serial_number.strip(),
        part_number=payload.part_number,
        status=payload.status,
        timestamp=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return TestOut.model_validate(record)


@app.get("/tests", response_model=List[TestOut])
def list_tests(db: Session = Depends(get_db)) -> List[TestOut]:
    rows = db.query(ManualTest).order_by(ManualTest.timestamp.desc()).all()
    return [TestOut.model_validate(r) for r in rows]


@app.get("/stats", response_model=List[StatRow])
def stats(
    from_: Optional[date] = Query(default=None, alias="from"),
    to_: Optional[date] = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> List[StatRow]:
    start, end_exclusive = _resolve_range(from_, to_)
    q = db.query(
        ManualTest.part_number,
        func.count(ManualTest.id).label("tested"),
        func.sum(func.cast(ManualTest.status, Integer)).label("passed"),
    )
    if start is not None:
        q = q.filter(ManualTest.timestamp >= start)
    if end_exclusive is not None:
        q = q.filter(ManualTest.timestamp < end_exclusive)
    rows = q.group_by(ManualTest.part_number).all()

    by_part = {pn: {"tested": 0, "passed": 0} for pn in ALLOWED_PART_NUMBERS}
    for part_number, tested, passed in rows:
        passed = int(passed or 0)
        by_part[part_number] = {"tested": int(tested), "passed": passed}

    out: List[StatRow] = []
    for pn in ALLOWED_PART_NUMBERS:
        tested = by_part[pn]["tested"]
        passed = by_part[pn]["passed"]
        failed = tested - passed
        yield_pct = round((passed / tested) * 100.0, 1) if tested else 0.0
        out.append(
            StatRow(
                part_number=pn,
                tested=tested,
                passed=passed,
                failed=failed,
                yield_pct=yield_pct,
            )
        )
    return out


MAX_DAILY_RANGE_DAYS = 90


@app.get("/daily", response_model=List[DailyRow])
def daily(
    from_: Optional[date] = Query(default=None, alias="from"),
    to_: Optional[date] = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
) -> List[DailyRow]:
    # Default window: trailing 7 days ending today (UTC).
    today = datetime.utcnow().date()
    if from_ is None and to_ is None:
        start_date = today - timedelta(days=6)
        end_date = today
    elif from_ is not None and to_ is not None:
        if from_ > to_:
            raise HTTPException(status_code=400, detail="`from` must be on or before `to`")
        start_date, end_date = from_, to_
    elif from_ is not None:
        start_date = from_
        end_date = max(from_ + timedelta(days=6), today)
    else:  # only `to` provided
        end_date = to_
        start_date = end_date - timedelta(days=6)

    span = (end_date - start_date).days + 1
    if span > MAX_DAILY_RANGE_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"Range too large ({span} days). Max {MAX_DAILY_RANGE_DAYS}.",
        )

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_exclusive = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

    rows = (
        db.query(
            func.date(ManualTest.timestamp).label("d"),
            func.count(ManualTest.id).label("c"),
        )
        .filter(ManualTest.timestamp >= start_dt, ManualTest.timestamp < end_exclusive)
        .group_by(func.date(ManualTest.timestamp))
        .all()
    )
    counts = {str(d): int(c) for d, c in rows}

    out: List[DailyRow] = []
    for i in range(span):
        day = start_date + timedelta(days=i)
        out.append(DailyRow(date=day.isoformat(), count=counts.get(str(day), 0)))
    return out


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "1") == "1",
    )


