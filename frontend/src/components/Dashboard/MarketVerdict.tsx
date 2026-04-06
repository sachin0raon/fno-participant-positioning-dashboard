import { motion } from 'framer-motion'
import {
    Shield,
    Lightbulb,
    ArrowUpRight,
    ArrowDownRight,
    Minus,
    Eye,
    Scale,
} from 'lucide-react'
import { cn, PARTICIPANT_META } from '@/lib/utils'
import type { DashboardData, ParticipantSymbol } from '@/types'

interface MarketVerdictProps {
    data: DashboardData
}

const WEIGHT_LABELS: Record<string, string> = {
    FII: '🌍 FII (40%)',
    DII: '🏛 DII (25%)',
    PRO: '💼 PRO (20%)',
    CLIENT: '👤 Retail (15%)',
}

export function MarketVerdict({ data }: MarketVerdictProps) {
    const { market_summary, participants } = data
    const sentiment = market_summary.overall_sentiment
    const ws = market_summary.weighted_score
    const breakdown = market_summary.score_breakdown

    const isBullish = ws >= 0.5
    const isBearish = ws <= -0.5
    const isMixed = !isBullish && !isBearish

    // Find FII and DII for contrast
    const fii = participants.find((p) => p.symbol === 'FII')
    const dii = participants.find((p) => p.symbol === 'DII')

    // Sort by sentiment score
    const sorted = [...participants].sort((a, b) => b.sentiment_score - a.sentiment_score)
    const mostBullish = sorted[0]
    const mostBearish = sorted[sorted.length - 1]

    return (
        <div className="rounded-2xl border border-white/[0.06] glass overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent-500/10">
                    <Eye className="w-4 h-4 text-accent-400" />
                </div>
                <div>
                    <h2 className="text-base font-semibold text-white">Market-Wide Sentiment Verdict</h2>
                    <p className="text-xs text-surface-400">
                        Weighted composite analysis across all participant categories
                    </p>
                </div>
            </div>

            <div className="p-6 space-y-6">
                {/* Main Verdict Banner */}
                <motion.div
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                    className={cn(
                        'rounded-xl p-5 border',
                        isBullish && 'bg-bullish-500/[0.08] border-bullish-500/20',
                        isBearish && 'bg-bearish-500/[0.08] border-bearish-500/20',
                        isMixed && 'bg-neutral-500/[0.08] border-neutral-500/20',
                    )}
                >
                    <div className="flex items-center gap-3 mb-2">
                        {isBullish ? (
                            <ArrowUpRight className="w-6 h-6 text-bullish-400" />
                        ) : isBearish ? (
                            <ArrowDownRight className="w-6 h-6 text-bearish-400" />
                        ) : (
                            <Minus className="w-6 h-6 text-neutral-400" />
                        )}
                        <h3
                            className={cn(
                                'text-xl font-bold',
                                isBullish && 'text-bullish-400',
                                isBearish && 'text-bearish-400',
                                isMixed && 'text-neutral-400',
                            )}
                        >
                            Weighted Score: {ws >= 0 ? '+' : ''}{ws.toFixed(2)}
                        </h3>
                        {market_summary.contrarian_retail && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                Contrarian Retail
                            </span>
                        )}
                    </div>
                    <p className="text-sm text-surface-300 leading-relaxed">{sentiment}</p>
                </motion.div>

                {/* Score Breakdown */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2 mb-3">
                        <Scale className="w-4 h-4 text-accent-400" />
                        <h3 className="text-sm font-semibold text-white">Weighted Contribution</h3>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {(['FII', 'DII', 'PRO', 'CLIENT'] as const).map((sym) => {
                            const contrib = breakdown[sym] ?? 0
                            const isPos = contrib >= 0
                            return (
                                <div
                                    key={sym}
                                    className={cn(
                                        'rounded-xl border p-3 text-center space-y-1',
                                        isPos
                                            ? 'border-bullish-500/15 bg-bullish-500/[0.04]'
                                            : 'border-bearish-500/15 bg-bearish-500/[0.04]',
                                    )}
                                >
                                    <p className="text-xs text-surface-400 font-medium">{WEIGHT_LABELS[sym]}</p>
                                    <p
                                        className={cn(
                                            'text-lg font-bold font-mono',
                                            isPos ? 'text-bullish-400' : 'text-bearish-400',
                                        )}
                                    >
                                        {isPos ? '+' : ''}{contrib.toFixed(2)}
                                    </p>
                                </div>
                            )
                        })}
                    </div>
                </div>

                {/* Key Observations */}
                <div className="space-y-3">
                    <div className="flex items-center gap-2 mb-3">
                        <Lightbulb className="w-4 h-4 text-accent-400" />
                        <h3 className="text-sm font-semibold text-white">Key Observations</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {/* Most Bullish */}
                        {mostBullish && (
                            <ObservationCard
                                icon="🟢"
                                title="Most Bullish Participant"
                                value={mostBullish.category}
                                detail={`Sentiment Score: ${mostBullish.sentiment_score > 0 ? '+' : ''}${mostBullish.sentiment_score}`}
                                variant="bullish"
                            />
                        )}

                        {/* Most Bearish */}
                        {mostBearish && (
                            <ObservationCard
                                icon="🔴"
                                title="Most Cautious Participant"
                                value={mostBearish.category}
                                detail={`Sentiment Score: ${mostBearish.sentiment_score > 0 ? '+' : ''}${mostBearish.sentiment_score}`}
                                variant="bearish"
                            />
                        )}

                        {/* FII-DII Contrast */}
                        {fii && dii && (
                            <ObservationCard
                                icon="🔄"
                                title="FII-DII Contrast"
                                value={`FII: ${fii.overall_sentiment} vs DII: ${dii.overall_sentiment}`}
                                detail={
                                    fii.overall_sentiment === dii.overall_sentiment
                                        ? 'Both aligned – stronger signal'
                                        : 'Divergent views – watch for volatility'
                                }
                                variant="neutral"
                            />
                        )}

                        {/* Score Distribution */}
                        <ObservationCard
                            icon="📊"
                            title="Participant Breakdown"
                            value={`${market_summary.bullish_count} Bullish · ${market_summary.bearish_count} Bearish · ${market_summary.neutral_count} Neutral`}
                            detail={
                                market_summary.bullish_count > market_summary.bearish_count
                                    ? 'Majority leaning bullish'
                                    : market_summary.bearish_count > market_summary.bullish_count
                                        ? 'Majority leaning bearish'
                                        : 'Evenly split – indecisive market'
                            }
                            variant="neutral"
                        />
                    </div>
                </div>

                {/* Participant Sentiment Bar */}
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-white">Sentiment Score by Participant</h3>
                    <div className="space-y-2">
                        {sorted.map((p) => {
                            const meta = PARTICIPANT_META[p.symbol as ParticipantSymbol]
                            const maxScore = 4
                            const normalized = ((p.sentiment_score + maxScore) / (maxScore * 2)) * 100
                            const isBull = p.sentiment_score > 0

                            return (
                                <div key={p.symbol} className="flex items-center gap-3">
                                    <div className="w-20 text-sm font-medium text-surface-300 flex items-center gap-1.5">
                                        <span className="text-sm">{meta?.icon}</span>
                                        {meta?.shortName ?? p.symbol}
                                    </div>
                                    <div className="flex-1 h-2.5 bg-surface-800 rounded-full overflow-hidden">
                                        <motion.div
                                            initial={{ width: 0 }}
                                            animate={{ width: `${Math.max(normalized, 5)}%` }}
                                            transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
                                            className={cn(
                                                'h-full rounded-full',
                                                isBull
                                                    ? 'bg-gradient-to-r from-bullish-600 to-bullish-400'
                                                    : 'bg-gradient-to-r from-bearish-600 to-bearish-400',
                                            )}
                                        />
                                    </div>
                                    <span
                                        className={cn(
                                            'w-10 text-right text-xs font-mono font-semibold',
                                            isBull ? 'text-bullish-400' : 'text-bearish-400',
                                        )}
                                    >
                                        {p.sentiment_score > 0 ? '+' : ''}
                                        {p.sentiment_score}
                                    </span>
                                </div>
                            )
                        })}
                    </div>
                </div>
            </div>
        </div>
    )
}

/* ─── Observation Card ─── */
function ObservationCard({
    icon,
    title,
    value,
    detail,
    variant,
}: {
    icon: string
    title: string
    value: string
    detail: string
    variant: 'bullish' | 'bearish' | 'neutral'
}) {
    return (
        <div
            className={cn(
                'rounded-xl border p-4 space-y-1.5',
                variant === 'bullish' && 'border-bullish-500/15 bg-bullish-500/[0.04]',
                variant === 'bearish' && 'border-bearish-500/15 bg-bearish-500/[0.04]',
                variant === 'neutral' && 'border-white/[0.06] bg-white/[0.02]',
            )}
        >
            <div className="flex items-center gap-2">
                <span className="text-base">{icon}</span>
                <span className="text-xs font-medium text-surface-400 uppercase tracking-wider">{title}</span>
            </div>
            <p className="text-sm font-semibold text-white">{value}</p>
            <p className="text-xs text-surface-500">{detail}</p>
        </div>
    )
}
