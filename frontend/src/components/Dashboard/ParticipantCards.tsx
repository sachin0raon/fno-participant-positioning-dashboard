import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import * as Tabs from '@radix-ui/react-tabs'
import { TrendingUp, Phone, Shield, ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { cn, formatCompact, PARTICIPANT_META } from '@/lib/utils'
import type { ParticipantAnalysis, ParticipantSymbol } from '@/types'

interface ParticipantCardsProps {
    participants: ParticipantAnalysis[]
}

export function ParticipantCards({ participants }: ParticipantCardsProps) {
    const [activeTab, setActiveTab] = useState<string>(participants[0]?.symbol ?? 'FII')

    const handleTabChange = (value: string) => {
        setActiveTab(value)
    }

    return (
        <div className="rounded-2xl border border-white/[0.06] glass overflow-hidden">
            {/* Section Header */}
            <div className="px-6 py-4 border-b border-white/[0.06]">
                <h2 className="text-base font-semibold text-white">Detailed Positioning Analysis</h2>
                <p className="text-xs text-surface-400 mt-0.5">
                    Drill down into each participant's Futures, Calls, and Puts positions
                </p>
            </div>

            <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
                {/* Tab List */}
                <Tabs.List className="flex border-b border-white/[0.06] px-4 gap-1 overflow-x-auto">
                    {participants.map((p) => {
                        const meta = PARTICIPANT_META[p.symbol as ParticipantSymbol]
                        return (
                            <Tabs.Trigger
                                key={p.symbol}
                                value={p.symbol}
                                className={cn(
                                    'flex items-center gap-2 px-4 py-3 text-sm font-medium',
                                    'border-b-2 transition-all duration-200 whitespace-nowrap',
                                    'data-[state=active]:border-accent-400 data-[state=active]:text-white',
                                    'data-[state=inactive]:border-transparent data-[state=inactive]:text-surface-500',
                                    'hover:text-surface-200',
                                )}
                            >
                                <span className="text-base">{meta?.icon}</span>
                                <span>{meta?.shortName ?? p.symbol}</span>
                                <SentimentDot sentiment={p.overall_sentiment} />
                            </Tabs.Trigger>
                        )
                    })}
                </Tabs.List>

                {/* Tab Content */}
                <div className="relative">
                    <AnimatePresence mode="wait">
                        {participants
                            .filter((p) => p.symbol === activeTab)
                            .map((p) => (
                                <Tabs.Content key={p.symbol} value={p.symbol} forceMount className="outline-none">
                                    <motion.div
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -8 }}
                                        transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                                        className="p-6"
                                    >
                                        <ParticipantDetail data={p} />
                                    </motion.div>
                                </Tabs.Content>
                            ))}
                    </AnimatePresence>
                </div>
            </Tabs.Root>
        </div>
    )
}

/* ─── Participant Detail View ─── */
function ParticipantDetail({ data }: { data: ParticipantAnalysis }) {
    const meta = PARTICIPANT_META[data.symbol as ParticipantSymbol]

    return (
        <div className="space-y-5">
            {/* Participant header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div
                        className={cn(
                            'flex items-center justify-center w-10 h-10 rounded-xl text-xl',
                            'bg-gradient-to-br shadow-lg',
                            meta?.gradient,
                        )}
                    >
                        {meta?.icon}
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-white">{data.category}</h3>
                        <p className="text-xs text-surface-500">{meta?.description}</p>
                    </div>
                </div>

                <div
                    className={cn(
                        'px-4 py-2 rounded-xl text-sm font-semibold border',
                        data.overall_sentiment === 'Bullish' && 'bg-bullish-500/15 text-bullish-400 border-bullish-500/25',
                        data.overall_sentiment === 'Bearish' && 'bg-bearish-500/15 text-bearish-400 border-bearish-500/25',
                        data.overall_sentiment === 'Neutral/Mixed' && 'bg-neutral-500/15 text-neutral-400 border-neutral-500/25',
                    )}
                >
                    {data.overall_sentiment === 'Bullish' && '▲ '}
                    {data.overall_sentiment === 'Bearish' && '▼ '}
                    {data.overall_sentiment === 'Neutral/Mixed' && '◆ '}
                    Overall: {data.overall_sentiment}
                </div>
            </div>

            {/* 3-column grid for each instrument */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <InstrumentCard
                    title="Futures"
                    icon={<TrendingUp className="w-4 h-4" />}
                    iconColor="text-indigo-400"
                    iconBg="bg-indigo-500/15"
                    net={data.futures.net}
                    rows={[
                        { label: 'Long', value: data.futures.long },
                        { label: 'Short', value: data.futures.short },
                    ]}
                    activity={data.futures.activity}
                    trend={data.futures.trend}
                    sentiment={data.futures.sentiment}
                />

                <InstrumentCard
                    title="Call Options (CE)"
                    icon={<Phone className="w-4 h-4" />}
                    iconColor="text-bullish-400"
                    iconBg="bg-bullish-500/15"
                    net={data.calls.net}
                    rows={[
                        { label: 'Bought', value: data.calls.bought },
                        { label: 'Sold', value: data.calls.sold },
                    ]}
                    activity={data.calls.activity}
                    trend={data.calls.trend}
                    sentiment={data.calls.sentiment}
                />

                <InstrumentCard
                    title="Put Options (PE)"
                    icon={<Shield className="w-4 h-4" />}
                    iconColor="text-bearish-400"
                    iconBg="bg-bearish-500/15"
                    net={data.puts.net}
                    rows={[
                        { label: 'Bought', value: data.puts.bought },
                        { label: 'Sold', value: data.puts.sold },
                    ]}
                    activity={data.puts.activity}
                    trend={data.puts.trend}
                    sentiment={data.puts.sentiment}
                />
            </div>
        </div>
    )
}

/* ─── Instrument Card ─── */
function InstrumentCard({
    title,
    icon,
    iconColor,
    iconBg,
    net,
    rows,
    activity,
    trend,
    sentiment,
}: {
    title: string
    icon: React.ReactNode
    iconColor: string
    iconBg: string
    net: number
    rows: { label: string; value: number }[]
    activity: string
    trend: string
    sentiment: string
}) {
    const isBullish = trend.includes('Bullish')
    const isBearish = trend.includes('Bearish')

    return (
        <motion.div
            whileHover={{ y: -2 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 space-y-4"
        >
            {/* Card title */}
            <div className="flex items-center gap-2">
                <div className={cn('flex items-center justify-center w-7 h-7 rounded-lg', iconBg)}>
                    <span className={iconColor}>{icon}</span>
                </div>
                <h4 className="text-sm font-semibold text-white">{title}</h4>
            </div>

            {/* Net Position */}
            <div>
                <p className="text-xs text-surface-500 uppercase tracking-wider mb-1">Net Position</p>
                <p
                    className={cn(
                        'text-2xl font-bold tracking-tight',
                        net > 0 ? 'text-bullish-400' : net < 0 ? 'text-bearish-400' : 'text-surface-300',
                    )}
                >
                    {net > 0 ? '+' : ''}
                    {formatCompact(net)}
                </p>
            </div>

            {/* Long/Short or Bought/Sold */}
            <div className="space-y-2">
                {rows.map(({ label, value }) => (
                    <div key={label} className="flex items-center justify-between">
                        <span className="text-xs text-surface-500">{label}</span>
                        <span className="text-sm font-mono font-medium text-surface-300">
                            {formatCompact(value)}
                        </span>
                    </div>
                ))}
            </div>

            {/* Divider */}
            <div className="border-t border-white/[0.05]" />

            {/* Activity + Trend */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <span className="text-xs text-surface-500">Activity</span>
                    <span
                        className={cn(
                            'text-xs font-semibold',
                            activity.includes('Bought') && 'text-bullish-400',
                            activity.includes('Sold') && 'text-bearish-400',
                            !activity.includes('Bought') && !activity.includes('Sold') && 'text-surface-300',
                        )}
                    >
                        {activity}
                    </span>
                </div>
                <div className="flex items-center justify-between">
                    <span className="text-xs text-surface-500">Trend</span>
                    <span
                        className={cn(
                            'inline-flex items-center gap-1 text-xs font-semibold',
                            isBullish && 'text-bullish-400',
                            isBearish && 'text-bearish-400',
                            !isBullish && !isBearish && 'text-neutral-400',
                        )}
                    >
                        {isBullish ? <ArrowUpRight className="w-3 h-3" /> : isBearish ? <ArrowDownRight className="w-3 h-3" /> : null}
                        {trend}
                    </span>
                </div>
                <div>
                    <span className="text-[11px] text-surface-500 italic">{sentiment}</span>
                </div>
            </div>
        </motion.div>
    )
}

/* ─── Small sentiment dot ─── */
function SentimentDot({ sentiment }: { sentiment: string }) {
    return (
        <span
            className={cn(
                'w-2 h-2 rounded-full',
                sentiment === 'Bullish' && 'bg-bullish-400',
                sentiment === 'Bearish' && 'bg-bearish-400',
                sentiment === 'Neutral/Mixed' && 'bg-neutral-400',
            )}
        />
    )
}
