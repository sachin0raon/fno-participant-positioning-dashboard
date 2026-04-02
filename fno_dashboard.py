"""
F&O Participant Positioning API Server
FastAPI backend serving Futures & Options positioning data
Data source: National Stock Exchange of India (NSE)
"""

import logging
import os
import json
import asyncio
from pathlib import Path
from functools import lru_cache
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Union
import pandas as pd
import nselib
from nselib import derivatives
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from contextlib import asynccontextmanager


# ─── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ─── Constants ──────────────────────────────────────────────────────
load_dotenv()
IST = ZoneInfo("Asia/Kolkata")
CACHE_DIR = Path("data_cache")
CACHE_DIR.mkdir(exist_ok=True)

# ─── FastAPI App ────────────────────────────────────────────────────
# ─── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage lifecycle of Telegram bot and Scheduler"""
    if TELEGRAM_ENABLED:
        try:
            await setup_telegram_bot(app)
            if hasattr(app.state, "telegram_app"):
                tg_app = app.state.telegram_app
                # setup_telegram_bot already called initialize() to set commands
                await tg_app.start()
                
                # Start polling as a background task
                if tg_app.updater:
                    await tg_app.updater.start_polling(drop_pending_updates=True)
                    logger.info("Telegram bot polling started")
                
                if hasattr(app.state, "scheduler"):
                    app.state.scheduler.start()
                    logger.info("Scheduler started for daily dashboard")
        except Exception as e:
            logger.error(f"Error during lifespan startup: {e}")
    
    yield
    
    # Cleanup
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        try:
            app.state.scheduler.shutdown()
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down scheduler: {e}")

    if hasattr(app.state, "telegram_app"):
        try:
            tg_app = app.state.telegram_app
            if tg_app.updater and tg_app.updater.running:
                await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
            logger.info("Telegram bot shutdown complete")
        except Exception as e:
            logger.error(f"Error shutting down Telegram bot: {e}")


# ─── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title="F&O Dashboard API",
    description="NSE India Futures & Options Participant Positioning Data",
    version="2.0.0",
    lifespan=lifespan
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

class DateOption(BaseModel):
    value: str
    label: str
    status: Optional[str] = None

class MarketStatusInfo(BaseModel):
    is_holiday: bool = False
    is_not_ready: bool = False
    description: str
    date: str

# ─── NSE Data Fetcher ──────────────────────────────────────────────
class NSEFNODataFetcher:
    """Fetches F&O participant data from NSE India"""

    def __init__(self):
        self._holidays = None
        self._holidays_last_fetch = None

    def get_holidays(self) -> List[str]:
        """Fetch and cache NSE holidays for Equity Derivatives"""
        now = datetime.now()
        # Refresh cache daily
        if self._holidays is not None and self._holidays_last_fetch is not None:
            if (now - self._holidays_last_fetch).days < 1:
                return self._holidays

        try:
            logger.info("Fetching NSE holiday calendar...")
            df = nselib.trading_holiday_calendar()
            # Filter for Equity Derivatives if possible, else use any
            if 'Product' in df.columns:
                df = df[df['Product'] == 'Equity Derivatives']
            
            # Dates are in DD-Mon-YYYY format (e.g., 15-Jan-2026)
            # Convert to DD-MM-YYYY format for consistent comparison
            holiday_list = []
            for date_str in df['tradingDate'].values:
                try:
                    dt = datetime.strptime(date_str, "%d-%b-%Y")
                    holiday_list.append(dt.strftime("%d-%m-%Y"))
                except Exception as e:
                    logger.warning(f"Failed to parse holiday date {date_str}: {e}")
            
            self._holidays = holiday_list
            self._holidays_last_fetch = now
            return self._holidays
        except Exception as e:
            logger.error(f"Error fetching holidays: {e}")
            return []

    def is_holiday(self, date_str: str) -> bool:
        """Check if a given date (DD-MM-YYYY) is a holiday or weekend"""
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        # Weekend?
        if dt.weekday() >= 5:
            return True
        # Public Holiday?
        holidays = self.get_holidays()
        return date_str in holidays

    def get_holiday_description(self, date_str: str) -> Optional[str]:
        """Get description of the holiday if it is one"""
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        if dt.weekday() == 5: return "Saturday (Weekend)"
        if dt.weekday() == 6: return "Sunday (Weekend)"
        
        try:
            df = nselib.trading_holiday_calendar()
            if 'Product' in df.columns:
                df = df[df['Product'] == 'Equity Derivatives']
            
            # Match date
            matching = df[df['tradingDate'].apply(lambda x: datetime.strptime(x, "%d-%b-%Y").strftime("%d-%m-%Y") == date_str)]
            if not matching.empty:
                return str(matching['description'].values[0])
        except:
            pass
        return None

    def get_previous_trading_day(self, date_str: str) -> str:
        """Helper to find the previous trading day (skipping weekends and holidays)"""
        dt = datetime.strptime(date_str, "%d-%m-%Y")
        prev = dt - timedelta(days=1)
        
        while True:
            prev_str = prev.strftime("%d-%m-%Y")
            if prev.weekday() >= 5 or prev_str in self.get_holidays():
                prev -= timedelta(days=1)
            else:
                break
        return prev.strftime("%d-%m-%Y")

    def _get_cache_path(self, date: str) -> Path:
        return CACHE_DIR / f"oi_{date}.json"

    def _fetch_from_cache(self, date: str) -> Optional[List[Dict[str, Any]]]:
        path = self._get_cache_path(date)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Cache Read Error ({date}): {e}")
        return None

    def _save_to_cache(self, date: str, data: List[ParticipantData]):
        path = self._get_cache_path(date)
        try:
            with open(path, 'w') as f:
                json.dump([asdict(p) for p in data], f, indent=2)
        except Exception as e:
            logger.error(f"Cache Write Error ({date}): {e}")

    @lru_cache(maxsize=100)
    def _fetch_raw_nse_data(self, date: str) -> Optional[List[ParticipantData]]:
        """
        Fetch participant-wise open interest.
        Checks local file cache first, then calls nselib. If nselib fails, falls back to direct NSE requests.
        """
        # 1. Check file cache first
        cached_raw = self._fetch_from_cache(date)
        if cached_raw:
            logger.info(f"Cache hit for {date}")
            return [ParticipantData(**d) for d in cached_raw]

        # 2. Fetch from NSE via nselib first
        logger.info(f"Cache miss for {date}. Calling NSE API via nselib.")
        df = None
        try:
            df = derivatives.participant_wise_open_interest(date)
        except Exception as e:
            logger.warning(f"nselib failed for {date}: {e}. Falling back to manual fetch.")

        if df is None or df.empty:
            # 3. Fallback to direct requests if nselib fails to fetch or returns empty DataFrame
            try:
                import requests
                import io
                
                dt_obj = datetime.strptime(date, "%d-%m-%Y")
                date_str = dt_obj.strftime("%d%m%Y")
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                }
                
                urls = [
                    f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv",
                    f"https://archives.nseindia.com/content/nsccl/fao_participant_oi_{date_str}.csv"
                ]
                
                for url in urls:
                    logger.info(f"Fallback URL: {url}")
                    try:
                        # requests auto-negotiates HTTP/1.1 and naturally skips Akamai HTTP/2 blocks
                        resp = requests.get(url, headers=headers, timeout=15)
                        if resp.status_code == 200:
                            df_fallback = pd.read_csv(io.BytesIO(resp.content), on_bad_lines='skip', skiprows=1)
                            if not df_fallback.empty:
                                df = df_fallback
                                break
                    except Exception as req_e:
                        logger.warning(f"Fallback request failed for {url}: {req_e}")
            except Exception as e:
                logger.error(f"NSE API Fallback Error for {date}: {e}")

        if df is None or df.empty:
            logger.warning(f"No data available for {date} from nselib or fallback.")
            return None
        
        try:
            parsed = self._parse_dataframe(df)
            if parsed:
                self._save_to_cache(date, parsed)
            return parsed
        except Exception as e:
            logger.error(f"Error parsing dataframe for {date}: {e}")
            return None

    async def get_participant_oi_data(self, date: str) -> Optional[List[ParticipantData]]:
        """
        Fetch participant-wise Open Interest change for a given date.
        Calculates Change = (Today's OI - Yesterday's OI)
        """
        try:
            logger.info(f"Processing data for {date}")
            
            # 1. Fetch Today's Data
            curr_data = await asyncio.to_thread(self._fetch_raw_nse_data, date)
            if not curr_data:
                return None
            
            # 2. Fetch Yesterday's Data
            prev_date = self.get_previous_trading_day(date)
            prev_data = await asyncio.to_thread(self._fetch_raw_nse_data, prev_date)
            
            if not prev_data:
                logger.warning(f"Previous day data ({prev_date}) not found. Returning raw positioning.")
                return curr_data

            # 3. Calculate Change
            return self._calculate_change(curr_data, prev_data)

        except Exception as e:
            logger.error(f"Data Processor Error: {e}")
            return None

    def _calculate_change(self, curr: List[ParticipantData], prev: List[ParticipantData]) -> List[ParticipantData]:
        """Calculates Today - Yesterday for all fields from parsed data"""
        curr_map = {p.category: p for p in curr}
        prev_map = {p.category: p for p in prev}
        
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

# ─── Telegram Bot Configuration ─────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip() or None
TELEGRAM_CRON_SCHEDULE = os.getenv("TELEGRAM_CRON_SCHEDULE", "0 16 * * 1-5")
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


# ─── API Routes ────────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(IST).isoformat()}


@app.get("/api/available-dates", response_model=List[DateOption])
async def get_available_dates():
    """Return the last 30 weekdays, including holidays and the current pending day."""
    dates: List[DateOption] = []
    now_ist = datetime.now(IST)
    holidays = fetcher.get_holidays()

    # Start from today regardless of time
    current = now_ist
    count = 0
    while count < 30:
        val = current.strftime("%d-%m-%Y")
        # Include all weekdays
        if current.weekday() < 5:
            # 1. Base label
            label = current.strftime("%d %b %Y (%A)")
            
            # 2. Status additions
            # Holiday?
            status = None
            if val in holidays:
                status = fetcher.get_holiday_description(val) or "Holiday"
            # Today and early?
            elif val == now_ist.strftime("%d-%m-%Y"):
                if now_ist.hour < 18 or (now_ist.hour == 18 and now_ist.minute < 30):
                    status = "Pending Update"

            dates.append(DateOption(value=val, label=label, status=status))
            count += 1
        current -= timedelta(days=1)

    return dates


async def _fetch_and_analyze_data(date: str) -> Optional[DashboardResponse]:
    """Internal helper to fetch data, analyze it and format response"""
    data = await fetcher.get_participant_oi_data(date)

    if not data:
        return None

    # Analyze all participants
    participants = [analyzer.analyze_participant(d) for d in data]

    # Market summary
    bull_count = sum(1 for p in participants if p.overall_sentiment == "Bullish")
    bear_count = sum(1 for p in participants if p.overall_sentiment == "Bearish")
    neutral_count = len(participants) - bull_count - bear_count
    
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
        )
    )


@app.get("/api/fno-data", response_model=Union[DashboardResponse, MarketStatusInfo])
async def get_fno_data(
    date: str = Query(..., description="Date in DD-MM-YYYY format"),
):
    """Fetch F&O participant data for a given trading date"""
    # Validate date format
    try:
        dt_req = datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use DD-MM-YYYY.",
        )

    # 1. Holiday Check
    if fetcher.is_holiday(date):
        return MarketStatusInfo(
            is_holiday=True,
            description=fetcher.get_holiday_description(date) or "Market Holiday",
            date=date
        )

    # 2. Check if it's today and too early
    now_ist = datetime.now(IST)
    if date == now_ist.strftime("%d-%m-%Y"):
        if now_ist.hour < 18 or (now_ist.hour == 18 and now_ist.minute < 30):
            return MarketStatusInfo(
                is_not_ready=True,
                description="Today's market data is typically published by NSE after 6:30 PM IST.",
                date=date
            )

    # 3. Fetch data
    response = await _fetch_and_analyze_data(date)
    if not response:
        # Check if it was a holiday but fetcher didn't know (fallback)
        raise HTTPException(status_code=404, detail=f"No data available for {date}. Please ensure it was a trading day.")
    return response


# ─── Telegram Bot Functions ──────────────────────────────────────────

def format_compact_message(data: DashboardResponse) -> str:
    """Generate a rich premium formatted message for Telegram"""
    lines = []
    lines.append("🏦 *F&O PARTICIPANT POSITIONING* 🏦")
    lines.append(f"📅 *Date:* `{data.date}`")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    
    # Market summary
    summary = data.market_summary
    lines.append(f"🌐 *MARKET SENTIMENT:* {summary.overall_sentiment}")
    lines.append(f"🐂 {summary.bullish_count} Bullish | 🐻 {summary.bearish_count} Bearish | ⚪ {summary.neutral_count} Neutral")
    lines.append("")
    lines.append(f"🏆 *LEADERS:*")
    lines.append(f"🔥 Top Bull: *{summary.most_bullish}*")
    lines.append(f"❄️ Top Bear: *{summary.most_bearish}*")
    lines.append("━━━━━━━━━━━━━━━━━━━━")

    # Participants
    lines.append("📊 *POSITION ANALYSIS:*")
    lines.append("")
    
    for p in data.participants:
        emoji = "🟢" if p.overall_sentiment == "Bullish" else "🔴" if p.overall_sentiment == "Bearish" else "⚪"
        
        lines.append(f"{emoji} *{p.category}* ({p.overall_sentiment})")
        lines.append(f" ├ 📈 *Futures:* `{p.futures.net:+d}`")
        lines.append(f" ├ 📞 *Calls:* `{p.calls.net:+d}`")
        lines.append(f" └ 📉 *Puts:* `{p.puts.net:+d}`")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"🏛️ *FII:* {summary.fii_sentiment} | *DII:* {summary.dii_sentiment}")
    lines.append(f"🤖 _Source: NSE India | Analyzed via Python_")

    return "\n".join(lines)


async def send_dashboard_message(chat_id: str, date: str = None, silent_skip: bool = False, header: str = "", smart_fallback: bool = False):
    """Send dashboard report to a specific chat"""
    if not hasattr(app.state, "telegram_app"):
        logger.warning("Telegram app not initialized")
        return

    now = datetime.now(IST)
    target_date = date or now.strftime("%d-%m-%Y")

    # 1. Weekend/Holiday Check for specific date
    try:
        if fetcher.is_holiday(target_date):
            if silent_skip:
                logger.info(f"Silently skipping weekend/holiday scheduling: {target_date}")
                return
            
            if smart_fallback:
                prev_date_str = fetcher.get_previous_trading_day(target_date)
                holiday_desc = fetcher.get_holiday_description(target_date)
                fallback_header = f"ℹ️ *Market is Closed* ({target_date} - {holiday_desc})\nShowing latest available report (*{prev_date_str}*):\n\n"
                # Call again with the previous trading day, disable fallback to avoid infinite loops
                return await send_dashboard_message(chat_id, prev_date_str, header=fallback_header, smart_fallback=False)

            holiday_desc = fetcher.get_holiday_description(target_date) or "Market Holiday"
            await app.state.telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"🍹 *Market is Closed* ({target_date})\n\nReason: *{holiday_desc}*\n\nPositions are only updated on trading days.",
                parse_mode="Markdown"
            )
            return
    except Exception as e:
        logger.error(f"Date check error: {e}")
        pass

    # 2. Data Fetching
    logger.info(f"Fetching dashboard for {target_date} (smart_fallback={smart_fallback})")
    data = await _fetch_and_analyze_data(target_date)

    if data:
        message = header + format_compact_message(data)
        try:
            await app.state.telegram_app.bot.send_message(chat_id=chat_id, text=message, parse_mode="Markdown")
            logger.info(f"Dashboard sent for {target_date}")
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    elif smart_fallback:
        # 3. Fallback logic: if data missing for the requested date, try previous trading day
        prev_date_str = fetcher.get_previous_trading_day(target_date)
        fallback_header = f"ℹ️ *Today's data is not yet available* ({target_date})\nShowing latest available report (*{prev_date_str}*):\n\n"
        logger.info(f"Data not available for {target_date}, falling back to {prev_date_str}")
        return await send_dashboard_message(chat_id, prev_date_str, header=fallback_header, smart_fallback=False)
    else:
        # Final failure message if no fallback or fallback also failed
        try:
            failure_msg = f"{header}🔴 *Data Unavailable*\n\nUnable to fetch F&O positioning data for *{target_date}* from NSE India at this time. This usually happens if the exchange hasn't released the data yet or there's a connectivity issue."
            await app.state.telegram_app.bot.send_message(chat_id=chat_id, text=failure_msg, parse_mode="Markdown")
            logger.warning(f"Sent failure notification for {target_date}")
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


# ─── Telegram Bot Handlers ────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        logger.warning(f"Unauthorized access from {update.message.chat_id}")
        return

    await update.message.reply_text(
        "📊 *F&O Dashboard Bot*\n\n"
        "Available commands:\n"
        "/recent - Get latest report\n"
        "/date DD-MM-YYYY - Get report for specific date\n"
        "/cron - Show/update schedule\n"
        "/help - Show this help message",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        return

    await update.message.reply_text(
        "📊 *F&O Dashboard Commands*\n\n"
        "*Commands:*\n"
        "/recent - Get latest F&O report\n"
        "/date `DD-MM-YYYY` - Get report for a specific date\n"
        "Example: `/date 14-03-2026`\n\n"
        "*Utilities:*\n"
        "/status - Check bot health & cache stats\n"
        "/cron - Show current schedule\n"
        "/cron `<expression>` - Update schedule\n"
        "Example: `/cron 0 9 * * 1-5` (9 AM weekdays)\n\n"
        "Format: `minute hour day month day_of_week`",
        parse_mode="Markdown"
    )


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recent command"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        return

    chat_id = str(update.message.chat_id)
    await send_dashboard_message(chat_id, smart_fallback=True)


async def date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /date command with argument"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        return

    if not context.args:
        await update.message.reply_text("Usage: /date DD-MM-YYYY\nExample: /date 14-03-2026")
        return

    date_arg = context.args[0]
    # Validate date format
    try:
        if fetcher.is_holiday(date_arg):
            holiday_desc = fetcher.get_holiday_description(date_arg) or "Market Holiday"
            await update.message.reply_text(f"❌ *{date_arg}* was a holiday/weekend ({holiday_desc}). Markets were closed.", parse_mode="Markdown")
            return
    except ValueError:
        await update.message.reply_text("Invalid date format. Use DD-MM-YYYY\nExample: /date 14-03-2026")
        return

    data = await _fetch_and_analyze_data(date_arg)
    if data:
        message = format_compact_message(data)
        await update.message.reply_text(message, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"No data available for {date_arg}")


async def cron_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cron command to update scheduler schedule"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        return

    global TELEGRAM_CRON_SCHEDULE

    if not context.args:
        current = TELEGRAM_CRON_SCHEDULE
        await update.message.reply_text(
            f"📅 *Current Schedule:* `{current}`\n\n"
            "Usage: `/cron <cron_expression>`\n"
            "Example: `/cron */5 * * * *` (every 5 minutes)\n"
            "Example: `/cron 0 9 * * 1-5` (9 AM weekdays)\n\n"
            "Format: `minute hour day month day_of_week`",
            parse_mode="Markdown"
        )
        return

    cron_arg = " ".join(context.args)

    # Validate the cron expression
    parsed = parse_cron_expression(cron_arg)
    if not parsed:
        await update.message.reply_text("Invalid cron expression. Use: minute hour day month day_of_week")
        return

    # Reschedule the job
    old_schedule = TELEGRAM_CRON_SCHEDULE
    TELEGRAM_CRON_SCHEDULE = cron_arg

    try:
        # Remove existing job if it exists
        try:
            app.state.scheduler.remove_job("daily_dashboard")
        except Exception:
            pass

        app.state.scheduler.add_job(
            send_dashboard_message,
            "cron",
            args=[TELEGRAM_CHAT_ID],
            kwargs={"silent_skip": True, "smart_fallback": True},
            **parsed,
            id="daily_dashboard"
        )
        await update.message.reply_text(
            f"✅ *Schedule updated!*\n\n"
            f"Old: `{old_schedule}`\n"
            f"New: `{cron_arg}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        TELEGRAM_CRON_SCHEDULE = old_schedule
        await update.message.reply_text(f"❌ Failed to update scheduler: {e}")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    if TELEGRAM_CHAT_ID and str(update.message.chat_id) != str(TELEGRAM_CHAT_ID):
        return

    # Check components
    bot_status = "✅ Active"
    scheduler_status = "✅ Active" if hasattr(app.state, "scheduler") and app.state.scheduler.running else "❌ Inactive"
    
    next_run = "N/A"
    if hasattr(app.state, "scheduler"):
        job = app.state.scheduler.get_job("daily_dashboard")
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%d-%m-%Y %H:%M:%S IST")
    
    now = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    await update.message.reply_text(
        f"🤖 *Bot Status:* {bot_status}\n"
        f"📅 *Scheduler:* {scheduler_status}\n"
        f"⏰ *Next Report:* `{next_run}`\n"
        f"🕒 *Current Time:* `{now}`\n\n"
        f"📡 *NSE Data Cache:* {len(list(CACHE_DIR.glob('*.json')))} files stored",
        parse_mode="Markdown"
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    from telegram.error import RetryAfter
    if isinstance(context.error, RetryAfter):
        logger.warning(f"Flood limit hit! Need to wait {context.error.retry_after} seconds.")
        # Don't spam logs with the same error if polling
        return
    logger.error(f"Update {update} caused error {context.error}")


async def setup_telegram_bot(fastapi_app: FastAPI):
    """Initialize and configure the Telegram bot"""
    if not TELEGRAM_ENABLED:
        logger.info("Telegram bot disabled: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return

    logger.info(f"Initializing Telegram bot...")

    # Create application
    # Use a more robust builder
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register handlers before initialize
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("recent", recent_command))
    telegram_app.add_handler(CommandHandler("date", date_command))
    telegram_app.add_handler(CommandHandler("cron", cron_command))
    telegram_app.add_handler(CommandHandler("status", status_command))
    telegram_app.add_error_handler(error_handler)
    
    # Store app
    fastapi_app.state.telegram_app = telegram_app

    # Set command list for Telegram UI
    commands = [
        BotCommand("recent", "Get latest F&O participant report"),
        BotCommand("date", "Get report for specific date (DD-MM-YYYY)"),
        BotCommand("cron", "Show or update the automated schedule"),
        BotCommand("status", "Check bot health and next run time"),
        BotCommand("help", "Show all available commands"),
        BotCommand("start", "Start the bot and show welcome message"),
    ]
    
    try:
        # We need to initialize to use the bot instance
        await telegram_app.initialize()
        await telegram_app.bot.set_my_commands(commands)
        
        # Log bot info to verify single instance
        me = await telegram_app.bot.get_me()
        logger.info(f"Bot @{me.username} initialized successfully (ID: {me.id})")
        
    except Exception as e:
        logger.error(f"Failed to initialize Telegram bot: {e}")
        return

    # Setup scheduler
    parsed_cron = parse_cron_expression(TELEGRAM_CRON_SCHEDULE)
    if not parsed_cron:
        logger.error(f"Invalid default cron schedule: {TELEGRAM_CRON_SCHEDULE}. Task NOT scheduled.")
        return

    scheduler = AsyncIOScheduler(timezone=IST)
    fastapi_app.state.scheduler = scheduler
    
    scheduler.add_job(
        send_dashboard_message,
        "cron",
        args=[TELEGRAM_CHAT_ID],
        kwargs={"silent_skip": True, "smart_fallback": True},
        **parsed_cron,
        id="daily_dashboard"
    )

    logger.info(f"Scheduler job 'daily_dashboard' added with schedule: {TELEGRAM_CRON_SCHEDULE}")


def parse_cron_expression(cron_str: str) -> Optional[Dict[str, Any]]:
    """
    Parse a 5-part cron expression string into APScheduler kwargs.
    Returns None if expression is invalid.
    """
    parts = cron_str.split()
    if len(parts) != 5:
        return None

    minute, hour, day, month, dow = parts
    kwargs = {}

    # Map fields. APScheduler's CronTrigger handles strings like '*/5' or '1-5' natively.
    if minute != "*": kwargs["minute"] = minute
    if hour != "*": kwargs["hour"] = hour
    if day != "*": kwargs["day"] = day
    if month != "*": kwargs["month"] = month
    if dow != "*": kwargs["day_of_week"] = dow

    return kwargs


# ─── FastAPI Events ───────────────────────────────────────────────────


# FastAPI startup/shutdown now handled via lifespan context manager


# ─── API Routes for Telegram ──────────────────────────────────────────

@app.get("/api/telegram/test")
async def test_telegram():
    """Test endpoint to send a message via Telegram"""
    if not TELEGRAM_ENABLED or not TELEGRAM_CHAT_ID:
        return {"error": "Telegram not configured"}
    today = datetime.now(IST).strftime("%d-%m-%Y")
    await send_dashboard_message(TELEGRAM_CHAT_ID, today)
    return {"status": "Message sent"}


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
