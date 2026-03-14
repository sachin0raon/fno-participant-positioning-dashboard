import { motion, Variants } from 'framer-motion'
import { ArrowUpRight, ArrowDownRight, Table2 } from 'lucide-react'
import { cn, formatNumber, toPositionRows, PARTICIPANT_META, getTrendIcon } from '@/lib/utils'
import type { ParticipantAnalysis, PositionRow, ParticipantSymbol } from '@/types'

interface PositioningTableProps {
    participants: ParticipantAnalysis[]
}

const rowVariants: Variants = {
    hidden: { opacity: 0, x: -10 },
    visible: (i: number) => ({
        opacity: 1,
        x: 0,
        transition: { delay: i * 0.03, duration: 0.35, ease: [0.22, 1, 0.36, 1] },
    }),
}

export function PositioningTable({ participants }: PositioningTableProps) {
    const rows = toPositionRows(participants)

    return (
        <div className="rounded-2xl border border-white/[0.06] glass overflow-hidden">
            {/* Header */}
            <div className="flex items-center gap-3 px-6 py-4 border-b border-white/[0.06]">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent-500/10">
                    <Table2 className="w-4 h-4 text-accent-400" />
                </div>
                <div>
                    <h2 className="text-base font-semibold text-white">Participant Positioning Summary</h2>
                    <p className="text-xs text-surface-400">
                        Net changes across Futures, Call Options (CE), and Put Options (PE)
                    </p>
                </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-white/[0.06]">
                            <th className="text-left px-6 py-3 text-xs font-semibold text-surface-400 uppercase tracking-wider">
                                Participant
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-surface-400 uppercase tracking-wider">
                                Instrument
                            </th>
                            <th className="text-right px-4 py-3 text-xs font-semibold text-surface-400 uppercase tracking-wider">
                                Net Change
                            </th>
                            <th className="text-left px-4 py-3 text-xs font-semibold text-surface-400 uppercase tracking-wider">
                                Activity
                            </th>
                            <th className="text-center px-6 py-3 text-xs font-semibold text-surface-400 uppercase tracking-wider">
                                Trend
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <motion.tr
                                key={`${row.symbol}-${row.instrument}`}
                                custom={i}
                                variants={rowVariants}
                                initial="hidden"
                                animate="visible"
                                className={cn(
                                    'border-b border-white/[0.03] transition-colors duration-150',
                                    'hover:bg-white/[0.03]',
                                    row.instrument === 'Future' && 'bg-white/[0.015]',
                                )}
                            >
                                {/* Participant */}
                                <td className="px-6 py-3.5">
                                    {row.instrument === 'Future' ? (
                                        <ParticipantBadge symbol={row.symbol} />
                                    ) : (
                                        <span className="text-surface-500 pl-6 text-xs">└</span>
                                    )}
                                </td>

                                {/* Instrument */}
                                <td className="px-4 py-3.5">
                                    <InstrumentBadge instrument={row.instrument} />
                                </td>

                                {/* Net Change */}
                                <td className="px-4 py-3.5 text-right">
                                    <span
                                        className={cn(
                                            'font-mono font-semibold text-sm',
                                            row.change > 0 ? 'text-bullish-400' : row.change < 0 ? 'text-bearish-400' : 'text-surface-400',
                                        )}
                                    >
                                        {formatNumber(row.change)}
                                    </span>
                                </td>

                                {/* Activity */}
                                <td className="px-4 py-3.5">
                                    <span
                                        className={cn(
                                            'text-sm font-medium',
                                            row.activity.includes('Bought') && 'text-bullish-300',
                                            row.activity.includes('Sold') && 'text-bearish-300',
                                            !row.activity.includes('Bought') &&
                                            !row.activity.includes('Sold') &&
                                            'text-surface-300',
                                        )}
                                    >
                                        {row.activity}
                                    </span>
                                </td>

                                {/* Trend */}
                                <td className="px-6 py-3.5 text-center">
                                    <TrendBadge trend={row.trend} />
                                </td>
                            </motion.tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

/* ─── Sub-components ─── */

function ParticipantBadge({ symbol }: { symbol: ParticipantSymbol }) {
    const meta = PARTICIPANT_META[symbol]
    return (
        <div className="flex items-center gap-2.5">
            <div
                className={cn(
                    'flex items-center justify-center w-7 h-7 rounded-lg text-sm',
                    'bg-gradient-to-br shadow-lg',
                    meta.gradient,
                )}
            >
                {meta.icon}
            </div>
            <div>
                <span className="font-semibold text-white text-sm">{meta.shortName}</span>
                <p className="text-[10px] text-surface-500 leading-tight hidden lg:block">
                    {meta.name}
                </p>
            </div>
        </div>
    )
}

function InstrumentBadge({ instrument }: { instrument: string }) {
    const configs: Record<string, { bg: string; text: string; label: string }> = {
        Future: { bg: 'bg-indigo-500/15 border-indigo-500/25', text: 'text-indigo-400', label: 'Future' },
        CE: { bg: 'bg-bullish-500/15 border-bullish-500/25', text: 'text-bullish-400', label: 'CE (Call)' },
        PE: { bg: 'bg-bearish-500/15 border-bearish-500/25', text: 'text-bearish-400', label: 'PE (Put)' },
    }

    const config = configs[instrument] ?? { bg: 'bg-surface-700', text: 'text-surface-300', label: instrument }

    return (
        <span
            className={cn(
                'inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium border',
                config.bg,
                config.text,
            )}
        >
            {config.label}
        </span>
    )
}

function TrendBadge({ trend }: { trend: string }) {
    const isBullish = trend.includes('Bullish')
    const isBearish = trend.includes('Bearish')

    return (
        <span
            className={cn(
                'inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold',
                isBullish && 'bg-bullish-500/15 text-bullish-400',
                isBearish && 'bg-bearish-500/15 text-bearish-400',
                !isBullish && !isBearish && 'bg-neutral-500/15 text-neutral-400',
            )}
        >
            {isBullish ? (
                <ArrowUpRight className="w-3.5 h-3.5" />
            ) : isBearish ? (
                <ArrowDownRight className="w-3.5 h-3.5" />
            ) : null}
            {trend}
        </span>
    )
}
