"""
F&O Participant Positioning API Server
FastAPI backend serving Futures & Options positioning data
Data source: National Stock Exchange of India (NSE)
"""

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

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

# ─── FastAPI App ────────────────────────────────────────────────────
# ─── Lifespan ────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage lifecycle of Telegram bot and Scheduler"""
    if TELEGRAM_ENABLED:
        await setup_telegram_bot(app)
        if hasattr(app.state, "telegram_app"):
            await app.state.telegram_app.initialize()
            await app.state.telegram_app.start()
            await app.state.telegram_app.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram bot polling started")
            if hasattr(app.state, "scheduler"):
                app.state.scheduler.start()
                logger.info("Scheduler started for daily dashboard")
    
    yield
    
    # Cleanup
    if hasattr(app.state, "scheduler") and app.state.scheduler.running:
        app.state.scheduler.shutdown()
    if hasattr(app.state, "telegram_app"):
        if app.state.telegram_app.updater and app.state.telegram_app.updater.running:
            await app.state.telegram_app.updater.stop()
        await app.state.telegram_app.stop()
        await app.state.telegram_app.shutdown()
    logger.info("Telegram bot stopped")


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
    """Return the last 30 trading days (weekdays) as available dates"""
    dates: List[DateOption] = []
    current = datetime.now(IST)

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


async def _fetch_and_analyze_data(date: str) -> Optional[DashboardResponse]:
    """Internal helper to fetch data, analyze it and format response"""
    data = fetcher.get_participant_oi_data(date)

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


@app.get("/api/fno-data", response_model=DashboardResponse)
async def get_fno_data(
    date: str = Query(..., description="Date in DD-MM-YYYY format"),
):
    """Fetch F&O participant data for a given trading date"""
    # Validate date format
    try:
        datetime.strptime(date, "%d-%m-%Y")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use DD-MM-YYYY.",
        )

    response = await _fetch_and_analyze_data(date)
    if not response:
        raise HTTPException(status_code=404, detail=f"No data available for {date}")
    return response


# ─── Telegram Bot Functions ──────────────────────────────────────────

def format_compact_message(data: DashboardResponse) -> str:
    """Generate a compact formatted message for Telegram"""
    lines = []
    lines.append(f"📊 *F&O Dashboard - {data.date}*")
    lines.append("")

    # Market summary
    summary = data.market_summary
    lines.append(f"🌐 *Overall Sentiment:* {summary.overall_sentiment}")
    lines.append(f"🐂 {summary.bullish_count} Bullish | 🐻 {summary.bearish_count} Bearish | ➖ {summary.neutral_count} Neutral")
    lines.append(f"🔥 *Top Bull:* {summary.most_bullish} | ❄️ *Top Bear:* {summary.most_bearish}")
    lines.append("")

    # Participants
    lines.append("*Position Analysis:*")
    for p in data.participants:
        emoji = "🟢" if p.overall_sentiment == "Bullish" else "🔴" if p.overall_sentiment == "Bearish" else "⚪"
        fut = f"F:{p.futures.net:+d}"
        ce = f"CE:{p.calls.net:+d}"
        pe = f"PE:{p.puts.net:+d}"
        lines.append(f"{emoji} *{p.symbol}*: {fut} | {ce} | {pe}")

    lines.append("")
    lines.append(f"🏛️ *FII:* {summary.fii_sentiment} | *DII:* {summary.dii_sentiment}")

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
        dt = datetime.strptime(target_date, "%d-%m-%Y").replace(tzinfo=IST)
        if dt.weekday() >= 5:
            if silent_skip:
                logger.info(f"Silently skipping weekend scheduling: {target_date}")
                return
            
            if smart_fallback:
                prev_date_str = fetcher.get_previous_trading_day(target_date)
                fallback_header = f"ℹ️ *Market is Closed* ({target_date})\nShowing latest available report (*{prev_date_str}*):\n\n"
                # Call again with the previous trading day, disable fallback to avoid infinite loops
                return await send_dashboard_message(chat_id, prev_date_str, header=fallback_header, smart_fallback=False)

            await app.state.telegram_app.bot.send_message(
                chat_id=chat_id,
                text=f"🍹 *Market is Closed* ({target_date})\n\nPositions are only updated on trading days (Monday - Friday).",
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
        "*Scheduler:*\n"
        "/cron - Show current schedule\n"
        "/cron `<expression>` - Update schedule\n"
        "Example: `/cron */5 * * * *` (every 5 min)\n"
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
        dt_arg = datetime.strptime(date_arg, "%d-%m-%Y")
        if dt_arg.weekday() >= 5:
            await update.message.reply_text(f"❌ *{date_arg}* was a weekend. Markets are closed on Saturdays and Sundays.", parse_mode="Markdown")
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

    logger.info(f"Initializing Telegram bot with token: {TELEGRAM_BOT_TOKEN[:5]}...")

    # Create application
    telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    fastapi_app.state.telegram_app = telegram_app

    # Register handlers
    telegram_app.add_handler(CommandHandler("start", start_command))
    telegram_app.add_handler(CommandHandler("help", help_command))
    telegram_app.add_handler(CommandHandler("recent", recent_command))
    telegram_app.add_handler(CommandHandler("date", date_command))
    telegram_app.add_handler(CommandHandler("cron", cron_command))
    telegram_app.add_error_handler(error_handler)

    # Set command list for Telegram UI
    commands = [
        BotCommand("recent", "Get latest F&O participant report"),
        BotCommand("date", "Get report for specific date (DD-MM-YYYY)"),
        BotCommand("cron", "Show or update the automated schedule"),
        BotCommand("help", "Show all available commands"),
        BotCommand("start", "Start the bot and show welcome message"),
    ]
    await telegram_app.bot.set_my_commands(commands)

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

    logger.info(f"Telegram bot initialized. Schedule: {TELEGRAM_CRON_SCHEDULE}")


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
