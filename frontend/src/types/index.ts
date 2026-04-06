/* ─── API Response Models ─── */
export interface InstrumentAnalysis {
  net: number
  activity: string
  trend: 'Bullish' | 'Bearish' | 'Neutral' | 'Bearish/Neutral'
  sentiment: string
}

export interface FuturesAnalysis extends InstrumentAnalysis {
  long: number
  short: number
}

export interface OptionsAnalysis extends InstrumentAnalysis {
  bought: number
  sold: number
}

export interface ParticipantAnalysis {
  category: string
  symbol: 'FII' | 'DII' | 'PRO' | 'CLIENT'
  futures: FuturesAnalysis
  calls: OptionsAnalysis
  puts: OptionsAnalysis
  overall_sentiment: 'Bullish' | 'Bearish' | 'Neutral/Mixed'
  sentiment_score: number
}

export interface MarketSummary {
  bullish_count: number
  bearish_count: number
  neutral_count: number
  overall_sentiment: string
  weighted_score: number
  score_breakdown: Record<string, number>
  most_bullish: string
  most_bearish: string
  fii_sentiment: string
  dii_sentiment: string
  contrarian_retail: boolean
}

export interface DashboardData {
  date: string
  participants: ParticipantAnalysis[]
  market_summary: MarketSummary
}

export interface MarketStatusInfo {
  is_holiday?: boolean
  is_not_ready?: boolean
  description: string
  date: string
}

export type DashboardResponse = DashboardData | MarketStatusInfo



export interface DateOption {
  value: string
  label: string
  status?: string
}


/* ─── Participant Display Info ─── */
export type ParticipantSymbol = 'FII' | 'DII' | 'PRO' | 'CLIENT'

export type SentimentType = 'Bullish' | 'Bearish' | 'Neutral/Mixed'

export type InstrumentType = 'Future' | 'CE' | 'PE'

export interface PositionRow {
  participant: string
  symbol: ParticipantSymbol
  instrument: InstrumentType
  change: number
  activity: string
  trend: string
}
