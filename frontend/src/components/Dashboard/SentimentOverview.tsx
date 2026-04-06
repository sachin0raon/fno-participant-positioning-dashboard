import { motion, Variants } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus, BarChart3, Scale } from 'lucide-react'
import { cn, formatNumber, PARTICIPANT_META } from '@/lib/utils'
import type { DashboardData } from '@/types'

interface SentimentOverviewProps {
    data: DashboardData
}

const cardVariants: Variants = {
    hidden: { opacity: 0, y: 16, scale: 0.97 },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] },
    },
}

export function SentimentOverview({ data }: SentimentOverviewProps) {
    const { market_summary, participants } = data

    // Calculate total net futures across all participants
    const totalFuturesNet = participants.reduce((sum, p) => sum + p.futures.net, 0)

    // Weighted score badge
    const ws = market_summary.weighted_score
    const wsLabel = ws >= 1.5 ? 'Strongly Bullish' : ws >= 0.5 ? 'Moderately Bullish' : ws > -0.5 ? 'Mixed' : ws > -1.5 ? 'Moderately Bearish' : 'Strongly Bearish'
    const wsVariant: 'bullish' | 'bearish' | 'neutral' = ws >= 0.5 ? 'bullish' : ws <= -0.5 ? 'bearish' : 'neutral'

    return (
        <motion.div
            variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06 } } }}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        >
            {/* Overall Market Sentiment – hero card */}
            <motion.div variants={cardVariants} className="h-full">
                <MetricCard
                    title="Market Sentiment"
                    value={wsLabel}
                    subtitle={`Score: ${ws >= 0 ? '+' : ''}${ws.toFixed(2)} / ±4.00`}
                    icon={<Scale className="w-5 h-5" />}
                    variant={wsVariant}
                    badge={market_summary.contrarian_retail ? 'CR' : undefined}
                    hero
                />
            </motion.div>

            {/* Bullish Count */}
            <motion.div variants={cardVariants} className="h-full">
                <MetricCard
                    title="Bullish"
                    value={market_summary.bullish_count}
                    subtitle="participants"
                    icon={<TrendingUp className="w-5 h-5" />}
                    variant="bullish"
                />
            </motion.div>

            {/* Bearish Count */}
            <motion.div variants={cardVariants} className="h-full">
                <MetricCard
                    title="Bearish"
                    value={market_summary.bearish_count}
                    subtitle="participants"
                    icon={<TrendingDown className="w-5 h-5" />}
                    variant="bearish"
                />
            </motion.div>

            {/* Total Futures Net */}
            <motion.div variants={cardVariants} className="h-full">
                <MetricCard
                    title="Total Futures Net"
                    value={formatNumber(totalFuturesNet)}
                    subtitle={totalFuturesNet >= 0 ? 'net long' : 'net short'}
                    icon={<BarChart3 className="w-5 h-5" />}
                    variant={totalFuturesNet > 0 ? 'bullish' : totalFuturesNet < 0 ? 'bearish' : 'neutral'}
                />
            </motion.div>
        </motion.div>
    )
}

/* ─── MetricCard ─── */
function MetricCard({
    title,
    value,
    subtitle,
    icon,
    variant,
    badge,
    hero = false,
}: {
    title: string
    value: number | string
    subtitle: string
    icon: React.ReactNode
    variant: 'bullish' | 'bearish' | 'neutral'
    badge?: string
    hero?: boolean
}) {
    const colorMap = {
        bullish: {
            bg: 'bg-bullish-500/[0.08]',
            border: 'border-bullish-500/20',
            iconBg: 'bg-bullish-500/15',
            iconColor: 'text-bullish-400',
            valueColor: 'text-bullish-400',
            glow: 'hover:shadow-bullish-500/10',
        },
        bearish: {
            bg: 'bg-bearish-500/[0.08]',
            border: 'border-bearish-500/20',
            iconBg: 'bg-bearish-500/15',
            iconColor: 'text-bearish-400',
            valueColor: 'text-bearish-400',
            glow: 'hover:shadow-bearish-500/10',
        },
        neutral: {
            bg: 'bg-neutral-500/[0.08]',
            border: 'border-neutral-500/20',
            iconBg: 'bg-neutral-500/15',
            iconColor: 'text-neutral-400',
            valueColor: 'text-neutral-400',
            glow: 'hover:shadow-neutral-500/10',
        },
    }

    const colors = colorMap[variant]

    return (
        <motion.div
            whileHover={{ y: -2, scale: 1.01 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            className={cn(
                'relative rounded-2xl border p-5 transition-shadow duration-300 h-full',
                colors.bg,
                colors.border,
                colors.glow,
                'hover:shadow-xl',
            )}
        >
            <div className="flex items-start justify-between">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <p className="text-xs font-medium text-surface-400 uppercase tracking-wider">
                            {title}
                        </p>
                        {badge && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-400 border border-amber-500/30">
                                {badge}
                            </span>
                        )}
                    </div>
                    <p className={cn(
                        'font-bold tracking-tight',
                        colors.valueColor,
                        hero ? 'text-lg font-extrabold leading-snug' : 'text-3xl',
                    )}>
                        {value}
                    </p>
                    <p className={cn(
                        'mt-1',
                        hero ? 'text-xs font-mono text-surface-400' : 'text-xs text-surface-500',
                    )}>
                        {subtitle}
                    </p>
                </div>
                <div className={cn('flex items-center justify-center w-10 h-10 rounded-xl', colors.iconBg)}>
                    <span className={colors.iconColor}>{icon}</span>
                </div>
            </div>
        </motion.div>
    )
}
