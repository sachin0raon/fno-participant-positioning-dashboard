import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ParticipantSymbol, SentimentType, PositionRow, ParticipantAnalysis } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/* ─── Number formatting ─── */
export function formatNumber(num: number): string {
  const sign = num > 0 ? '+' : ''
  return `${sign}${num.toLocaleString('en-IN')}`
}

export function formatCompact(num: number): string {
  return num.toLocaleString('en-IN')
}

/* ─── Sentiment utilities ─── */
const SENTIMENT_STYLES: Record<string, { text: string; bg: string; glow: string; icon: string }> = {
  Bullish: {
    text: 'text-bullish-400',
    bg: 'bg-bullish-500/15 border-bullish-500/25',
    glow: 'glow-bullish',
    icon: '▲',
  },
  Bearish: {
    text: 'text-bearish-400',
    bg: 'bg-bearish-500/15 border-bearish-500/25',
    glow: 'glow-bearish',
    icon: '▼',
  },
  Neutral: {
    text: 'text-neutral-400',
    bg: 'bg-neutral-500/15 border-neutral-500/25',
    glow: 'glow-accent',
    icon: '◆',
  },
}

export function getSentimentColor(sentiment: string): string {
  if (sentiment.includes('Bullish')) return SENTIMENT_STYLES.Bullish.text
  if (sentiment.includes('Bearish')) return SENTIMENT_STYLES.Bearish.text
  return SENTIMENT_STYLES.Neutral.text
}

export function getSentimentBgColor(sentiment: string): string {
  if (sentiment.includes('Bullish')) return SENTIMENT_STYLES.Bullish.bg
  if (sentiment.includes('Bearish')) return SENTIMENT_STYLES.Bearish.bg
  return SENTIMENT_STYLES.Neutral.bg
}

export function getSentimentGlow(sentiment: string): string {
  if (sentiment.includes('Bullish')) return SENTIMENT_STYLES.Bullish.glow
  if (sentiment.includes('Bearish')) return SENTIMENT_STYLES.Bearish.glow
  return SENTIMENT_STYLES.Neutral.glow
}

export function getTrendIcon(trend: string): string {
  if (trend.includes('Bullish')) return SENTIMENT_STYLES.Bullish.icon
  if (trend.includes('Bearish')) return SENTIMENT_STYLES.Bearish.icon
  return SENTIMENT_STYLES.Neutral.icon
}

/* ─── Participant display info ─── */
export const PARTICIPANT_META: Record<ParticipantSymbol, {
  name: string
  shortName: string
  gradient: string
  icon: string
  description: string
}> = {
  FII: {
    name: 'Foreign Institutional Investors',
    shortName: 'FII',
    gradient: 'from-violet-500 to-indigo-600',
    icon: '🌍',
    description: 'Global funds investing in Indian markets',
  },
  DII: {
    name: 'Domestic Institutional Investors',
    shortName: 'DII',
    gradient: 'from-emerald-500 to-teal-600',
    icon: '🏛️',
    description: 'Indian mutual funds, insurance companies, banks',
  },
  PRO: {
    name: 'Proprietary Traders',
    shortName: 'PRO',
    gradient: 'from-amber-500 to-orange-600',
    icon: '💼',
    description: 'Broker proprietary desks and trading firms',
  },
  CLIENT: {
    name: 'Retail Traders',
    shortName: 'Retail',
    gradient: 'from-pink-500 to-rose-600',
    icon: '👤',
    description: 'Individual traders and investors',
  },
}

/* ─── Transform analysis → flat position rows (for the main table) ─── */
export function toPositionRows(participants: ParticipantAnalysis[]): PositionRow[] {
  const rows: PositionRow[] = []

  for (const p of participants) {
    const displayName = PARTICIPANT_META[p.symbol]?.shortName ?? p.symbol

    rows.push({
      participant: displayName,
      symbol: p.symbol,
      instrument: 'Future',
      change: p.futures.net,
      activity: p.futures.activity,
      trend: p.futures.trend,
    })
    rows.push({
      participant: displayName,
      symbol: p.symbol,
      instrument: 'CE',
      change: p.calls.net,
      activity: p.calls.activity,
      trend: p.calls.trend,
    })
    rows.push({
      participant: displayName,
      symbol: p.symbol,
      instrument: 'PE',
      change: p.puts.net,
      activity: p.puts.activity,
      trend: p.puts.trend,
    })
  }

  return rows
}
