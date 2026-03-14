import { motion, Variants } from 'framer-motion'
import { TrendingUp, TrendingDown, Minus, BarChart3, Users } from 'lucide-react'
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

    return (
        <motion.div
            variants={{ hidden: {}, visible: { transition: { staggerChildren: 0.06 } } }}
            initial="hidden"
            animate="visible"
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        >
            {/* Bullish Count */}
            <motion.div variants={cardVariants}>
                <MetricCard
                    title="Bullish"
                    value={market_summary.bullish_count}
                    subtitle="participants"
                    icon={<TrendingUp className="w-5 h-5" />}
                    variant="bullish"
                />
            </motion.div>

            {/* Bearish Count */}
            <motion.div variants={cardVariants}>
                <MetricCard
                    title="Bearish"
                    value={market_summary.bearish_count}
                    subtitle="participants"
                    icon={<TrendingDown className="w-5 h-5" />}
                    variant="bearish"
                />
            </motion.div>

            {/* Neutral Count */}
            <motion.div variants={cardVariants}>
                <MetricCard
                    title="Neutral/Mixed"
                    value={market_summary.neutral_count}
                    subtitle="participants"
                    icon={<Minus className="w-5 h-5" />}
                    variant="neutral"
                />
            </motion.div>

            {/* Total Futures Net */}
            <motion.div variants={cardVariants}>
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
}: {
    title: string
    value: number | string
    subtitle: string
    icon: React.ReactNode
    variant: 'bullish' | 'bearish' | 'neutral'
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
                'relative rounded-2xl border p-5 transition-shadow duration-300',
                colors.bg,
                colors.border,
                colors.glow,
                'hover:shadow-xl',
            )}
        >
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-xs font-medium text-surface-400 uppercase tracking-wider mb-1">
                        {title}
                    </p>
                    <p className={cn('text-3xl font-bold tracking-tight', colors.valueColor)}>
                        {value}
                    </p>
                    <p className="text-xs text-surface-500 mt-1">{subtitle}</p>
                </div>
                <div className={cn('flex items-center justify-center w-10 h-10 rounded-xl', colors.iconBg)}>
                    <span className={colors.iconColor}>{icon}</span>
                </div>
            </div>
        </motion.div>
    )
}
