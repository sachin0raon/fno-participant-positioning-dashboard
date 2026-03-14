"""
F&O Participant Positioning API Server
FastAPI backend serving Futures & Options positioning data
Data source: National Stock Exchange of India (NSE)
"""

import hashlib
import random
import logging
import requests
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from nselib import derivatives
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import os


# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title="F&O Dashboard API",
    description="NSE India Futures & Options Participant Positioning Data",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Data Models ────────────────────────────────────────────────────
@dataclass
class ParticipantData:
    """Represents F&O data for a single participant category"""
    category: str  # FII, DII, PRO, CLIENT (Retail)
    futures_long: int
    futures_short: int
    calls_bought: int
    calls_sold: int
    puts_bought: int
    puts_sold: int

    @property
    def futures_net(self) -> int:
        return self.futures_long - self.futures_short

    @property
    def ce_net(self) -> int:
        return self.calls_bought - self.calls_sold

    @property
    def pe_net(self) -> int:
        return self.puts_bought - self.puts_sold


# ─── Response Models ───────────────────────────────────────────────
class InstrumentAnalysis(BaseModel):
    net: int
    activity: str
    trend: str
    sentiment: str


class FuturesAnalysis(InstrumentAnalysis):
    long: int
    short: int


class OptionsAnalysis(InstrumentAnalysis):
    bought: int
    sold: int


class ParticipantAnalysis(BaseModel):
    category: str
    symbol: str
    futures: FuturesAnalysis
    calls: OptionsAnalysis
    puts: OptionsAnalysis
    overall_sentiment: str
    sentiment_score: int


class MarketSummary(BaseModel):
    bullish_count: int
    bearish_count: int
    neutral_count: int
    overall_sentiment: str
    most_bullish: str
    most_bearish: str
    fii_sentiment: str
    dii_sentiment: str


class DashboardResponse(BaseModel):
    date: str
    participants: List[ParticipantAnalysis]
    market_summary: MarketSummary
    is_mock_data: bool


class DateOption(BaseModel):
    value: str
    label: str


# ─── NSE Data Fetcher ──────────────────────────────────────────────
class NSEFNODataFetcher:
    """Fetches F&O participant data from NSE India"""

    BASE_URL = "https://www.nseindia.com"

    def __init__(self):
        # nselib handles its own session/cookies
        pass

    def get_previous_trading_day(self, date_str: str) -> str:
        """Helper to find the previous weekday (simplified trading day logic)"""
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        # Go back at least 1 day
        prev = dt - timedelta(days=1)
        # Skip weekends
        while prev.weekday() >= 5:
            prev -= timedelta(days=1)
        return prev.strftime("%d-%m-%Y")

    def get_participant_oi_data(self, date: str) -> Optional[List[ParticipantData]]:
        """
        Fetch participant-wise Open Interest change for a given date.
        Calculates Change = (Today's OI - Yesterday's OI)
        """
        try:
            logger.info(f"Fetching NSE data for {date} and its previous trading day")
            
            # 1. Fetch Today's Data
            df_curr = derivatives.participant_wise_open_interest(date)
            if df_curr is None or df_curr.empty:
                return None
            
            # 2. Fetch Yesterday's Data
            prev_date = self.get_previous_trading_day(date)
            df_prev = derivatives.participant_wise_open_interest(prev_date)
            
            # If yesterday's data is missing, we can't show "Change", 
            # but for this specific request, we'll try to fallback or return raw
            if df_prev is None or df_prev.empty:
                logger.warning(f"Previous day data ({prev_date}) not found. Returning raw positioning.")
                return self._parse_dataframe(df_curr)

            # 3. Calculate Change
            return self._calculate_change(df_curr, df_prev)

        except Exception as e:
            logger.error(f"nselib Fetch Error: {e}")
            return None

    def _parse_dataframe(self, df) -> List[ParticipantData]:
        """Helper to parse raw NSE dataframe into ParticipantData list"""
        df.columns = df.columns.str.strip()
        data_list = []
        for _, row in df.iterrows():
            raw_cat = str(row['Client Type']).strip().upper()
            if "TOTAL" in raw_cat: continue
            
            symbol = None
            if "CLIENT" in raw_cat: symbol = "CLIENT"
            elif "DII" in raw_cat: symbol = "DII"
            elif "FII" in raw_cat: symbol = "FII"
            elif "PRO" in raw_cat: symbol = "PRO"
            
            if symbol:
                data_list.append(ParticipantData(
                    category=symbol,
                    futures_long=int(row['Future Index Long']),
                    futures_short=int(row['Future Index Short']),
                    calls_bought=int(row['Option Index Call Long']),
                    calls_sold=int(row['Option Index Call Short']),
                    puts_bought=int(row['Option Index Put Long']),
                    puts_sold=int(row['Option Index Put Short'])
                ))
        return data_list

    def _calculate_change(self, df_curr, df_prev) -> List[ParticipantData]:
        """Calculates Today - Yesterday for all fields"""
        curr_map = {p.category: p for p in self._parse_dataframe(df_curr)}
        prev_map = {p.category: p for p in self._parse_dataframe(df_prev)}
        
        change_list = []
        for cat in ["FII", "DII", "PRO", "CLIENT"]:
            c = curr_map.get(cat)
            p = prev_map.get(cat)
            
            if c and p:
                change_list.append(ParticipantData(
                    category=cat,
                    futures_long=c.futures_long - p.futures_long,
                    futures_short=c.futures_short - p.futures_short,
                    calls_bought=c.calls_bought - p.calls_bought,
                    calls_sold=c.calls_sold - p.calls_sold,
                    puts_bought=c.puts_bought - p.puts_bought,
                    puts_sold=c.puts_sold - p.puts_sold
                ))
        return change_list

    def get_mock_data(self, date: str = "") -> List[ParticipantData]:
        """Generate deterministic mock data based on date for demonstration"""
        seed_str = date if date else "default_seed"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        def rand_contracts(base: int, spread: int) -> int:
            return base + rng.randint(-spread, spread)

        mock_data = [
            ParticipantData(
                category="FII",
                futures_long=rand_contracts(125000, 15000),
                futures_short=rand_contracts(118000, 15000),
                calls_bought=rand_contracts(45000, 8000),
                calls_sold=rand_contracts(52000, 8000),
                puts_bought=rand_contracts(38000, 6000),
                puts_sold=rand_contracts(31000, 6000),
            ),
            ParticipantData(
                category="DII",
                futures_long=rand_contracts(45000, 8000),
                futures_short=rand_contracts(38000, 8000),
                calls_bought=rand_contracts(15000, 4000),
                calls_sold=rand_contracts(12000, 4000),
                puts_bought=rand_contracts(22000, 5000),
                puts_sold=rand_contracts(18000, 5000),
            ),
            ParticipantData(
                category="PRO",
                futures_long=rand_contracts(89000, 12000),
                futures_short=rand_contracts(95000, 12000),
                calls_bought=rand_contracts(67000, 10000),
                calls_sold=rand_contracts(72000, 10000),
                puts_bought=rand_contracts(54000, 8000),
                puts_sold=rand_contracts(49000, 8000),
            ),
            ParticipantData(
                category="CLIENT",
                futures_long=rand_contracts(67000, 10000),
                futures_short=rand_contracts(72000, 10000),
                calls_bought=rand_contracts(82000, 12000),
                calls_sold=rand_contracts(78000, 12000),
                puts_bought=rand_contracts(61000, 9000),
                puts_sold=rand_contracts(65000, 9000),
            ),
        ]
        return mock_data


# ─── Sentiment Analyzer ───────────────────────────────────────────
class SentimentAnalyzer:
    """Analyzes market sentiment based on participant positioning"""

    PARTICIPANT_NAMES = {
        "FII": "Foreign Institutional Investors",
        "DII": "Domestic Institutional Investors",
        "PRO": "Proprietary Traders",
        "CLIENT": "Retail Traders",
    }

    @staticmethod
    def interpret_futures(net_position: int) -> Dict[str, str]:
        if net_position > 1000:
            return {
                "activity": "Bought Futures",
                "trend": "Bullish",
                "sentiment": "Strongly Bullish – Net Long",
            }
        elif net_position > 0:
            return {
                "activity": "Bought Futures",
                "trend": "Bullish",
                "sentiment": "Mildly Bullish",
            }
        elif net_position < -1000:
            return {
                "activity": "Sold Futures",
                "trend": "Bearish",
                "sentiment": "Strongly Bearish – Net Short",
            }
        else:
            return {
                "activity": "Sold Futures",
                "trend": "Bearish",
                "sentiment": "Mildly Bearish",
            }

    @staticmethod
    def interpret_calls(net_calls: int) -> Dict[str, str]:
        if net_calls > 0:
            return {
                "activity": "Bought Calls",
                "trend": "Bullish",
                "sentiment": "Expecting upside",
            }
        else:
            return {
                "activity": "Sold Calls",
                "trend": "Bearish/Neutral",
                "sentiment": "Expecting stagnation/downside",
            }

    @staticmethod
    def interpret_puts(net_puts: int) -> Dict[str, str]:
        if net_puts > 0:
            return {
                "activity": "Bought Puts",
                "trend": "Bearish",
                "sentiment": "Hedging / expecting downside",
            }
        else:
            return {
                "activity": "Sold Puts",
                "trend": "Bullish",
                "sentiment": "Expecting upside / collecting premium",
            }

    @classmethod
    def analyze_participant(cls, data: ParticipantData) -> ParticipantAnalysis:
        f_info = cls.interpret_futures(data.futures_net)
        c_info = cls.interpret_calls(data.ce_net)
        p_info = cls.interpret_puts(data.pe_net)

        score = 0
        if f_info["trend"] == "Bullish":
            score += 2 if "Strongly" in f_info["sentiment"] else 1
        elif f_info["trend"] == "Bearish":
            score -= 2 if "Strongly" in f_info["sentiment"] else 1

        if c_info["activity"] == "Bought Calls":
            score += 1
        if p_info["activity"] == "Sold Puts":
            score += 1
        if p_info["activity"] == "Bought Puts":
            score -= 1

        if score >= 2:
            overall = "Bullish"
        elif score <= -2:
            overall = "Bearish"
        else:
            overall = "Neutral/Mixed"

        return ParticipantAnalysis(
            category=cls.PARTICIPANT_NAMES.get(data.category, data.category),
            symbol=data.category,
            futures=FuturesAnalysis(
                net=data.futures_net,
                long=data.futures_long,
                short=data.futures_short,
                activity=f_info["activity"],
                trend=f_info["trend"],
                sentiment=f_info["sentiment"]
            ),
            calls=OptionsAnalysis(
                net=data.ce_net,
                bought=data.calls_bought,
                sold=data.calls_sold,
                activity=c_info["activity"],
                trend=c_info["trend"],
                sentiment=c_info["sentiment"]
            ),
            puts=OptionsAnalysis(
                net=data.pe_net,
                bought=data.puts_bought,
                sold=data.puts_sold,
                activity=p_info["activity"],
                trend=p_info["trend"],
                sentiment=p_info["sentiment"]
            ),
            overall_sentiment=overall,
            sentiment_score=score,
        )


# ─── Singleton instances ───────────────────────────────────────────
fetcher = NSEFNODataFetcher()
analyzer = SentimentAnalyzer()


# ─── API Routes ────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/available-dates", response_model=List[DateOption])
async def get_available_dates():
    """Return the last 30 trading days (weekdays) as available dates"""
    dates: List[DateOption] = []
    current = datetime.now()

    count = 0
    while count < 30:
        # Skip weekends
        if current.weekday() < 5:
            value = current.strftime("%d-%m-%Y")
            label = current.strftime("%d %b %Y (%A)")
            dates.append(DateOption(value=value, label=label))
            count += 1
        current -= timedelta(days=1)

    return dates


@app.get("/api/fno-data", response_model=DashboardResponse)
async def get_fno_data(
    date: str = Query(..., description="Date in DD-MM-YYYY format"),
    mock: bool = Query(False, description="Force mock data"),
):
    """Fetch F&O participant data for a given trading date"""
    # Validate date format
    try:
        parsed_date = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use DD-MM-YYYY.",
        )

    is_mock = mock
    data: Optional[List[ParticipantData]] = None

    if not mock:
        data = fetcher.get_participant_oi_data(date)
        if data is None:
            logger.info(f"Live data unavailable for {date}, falling back to mock data")
            data = fetcher.get_mock_data(date)
            is_mock = True
    else:
        data = fetcher.get_mock_data(date)

    # Analyze all participants
    participants = [analyzer.analyze_participant(d) for d in data]

    # Market summary
    bull_count: int = 0
    bear_count: int = 0
    neutral_count: int = 0
    
    for p in participants:
        if p.overall_sentiment == "Bullish":
            bull_count += 1
        elif p.overall_sentiment == "Bearish":
            bear_count += 1
        else:
            neutral_count += 1

    sorted_by_score = sorted(participants, key=lambda x: x.sentiment_score, reverse=True)
    most_bullish = sorted_by_score[0].category if sorted_by_score else "N/A"
    most_bearish = sorted_by_score[-1].category if sorted_by_score else "N/A"

    fii = next((p for p in participants if p.symbol == "FII"), None)
    dii = next((p for p in participants if p.symbol == "DII"), None)

    if bull_count > bear_count:
        overall = "Optimistic – Majority bullish positioning"
    elif bear_count > bull_count:
        overall = "Cautious – Majority bearish/protective positioning"
    else:
        overall = "Mixed – No clear consensus"

    return DashboardResponse(
        date=date,
        participants=participants,
        market_summary=MarketSummary(
            bullish_count=bull_count,
            bearish_count=bear_count,
            neutral_count=neutral_count,
            overall_sentiment=overall,
            most_bullish=most_bullish,
            most_bearish=most_bearish,
            fii_sentiment=fii.overall_sentiment if fii else "N/A",
            dii_sentiment=dii.overall_sentiment if dii else "N/A",
        ),
        is_mock_data=is_mock,
    )


# ─── Static File Serving (Frontend) ──────────────────────────────────
# In Docker/Production, we build the frontend and serve it from /static
static_dir = os.path.join(os.path.dirname(__file__), "dist")
if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # API routes are handled above. This catch-all serves index.html for SPA routing.
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        
        file_path = os.path.join(static_dir, full_path)
        if full_path != "" and os.path.exists(file_path):
            return FileResponse(file_path)
        
        return FileResponse(os.path.join(static_dir, "index.html"))


# ─── Main ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # When running directly as a script, we use the app object.
    # The shell script uses 'python3 -m uvicorn' with reload for development.
    uvicorn.run(app, host="127.0.0.1", port=8000)
