import { useState, useCallback } from 'react'
import { motion, AnimatePresence, Variants } from 'framer-motion'
import { RefreshCw, AlertTriangle } from 'lucide-react'
import { useDashboardData, useAvailableDates, useRefreshDashboard } from '@/hooks/useFNOData'
import { DateSelector } from '@/components/Dashboard/DateSelector'
import { SentimentOverview } from '@/components/Dashboard/SentimentOverview'
import { PositioningTable } from '@/components/Dashboard/PositioningTable'
import { ParticipantCards } from '@/components/Dashboard/ParticipantCards'
import { MarketVerdict } from '@/components/Dashboard/MarketVerdict'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ErrorFallback } from '@/components/ui/ErrorFallback'
import { Coffee, Clock } from 'lucide-react'



const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
        opacity: 1,
        transition: { staggerChildren: 0.08, delayChildren: 0.1 },
    },
}

const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
}

export default function Dashboard() {
    const { data: dates } = useAvailableDates()
    const [selectedDate, setSelectedDate] = useState('')

    const effectiveDate = selectedDate || dates?.[0]?.value || ''

    const {
        data: dashboardData,
        isLoading,
        isError,
        error,
        isFetching,
        refetch,
    } = useDashboardData(effectiveDate)

    const refreshDashboard = useRefreshDashboard()

    const handleRefresh = useCallback(() => {
        if (effectiveDate) refreshDashboard(effectiveDate)
    }, [effectiveDate, refreshDashboard])

    const handleDateChange = useCallback((date: string) => {
        setSelectedDate(date)
    }, [])

    return (
        <div className="space-y-6">
            {/* ─── Top Bar: Date selector + refresh ─── */}
            <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
                <DateSelector
                    dates={dates ?? []}
                    selectedDate={effectiveDate}
                    onChange={handleDateChange}
                />

                <div className="flex items-center gap-3">

                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        onClick={handleRefresh}
                        disabled={isFetching}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent-500/10 hover:bg-accent-500/20 border border-accent-500/20 text-accent-400 text-sm font-medium transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
                        Refresh
                    </motion.button>
                </div>
            </motion.div>

            {/* ─── Content ─── */}
            <AnimatePresence mode="wait">
                {isLoading ? (
                    <motion.div
                        key="loading"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center justify-center min-h-[60vh]"
                    >
                        <LoadingSpinner size="lg" text="Loading F&O positioning data…" />
                    </motion.div>
                ) : isError ? (
                    <motion.div
                        key="error"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="flex items-center justify-center min-h-[60vh]"
                    >
                        <ErrorFallback error={error} onRetry={() => refetch()} />
                    </motion.div>
                ) : dashboardData && ('is_holiday' in dashboardData || 'is_not_ready' in dashboardData) ? (
                    <motion.div
                        key="market-status"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8"
                    >
                        <div className="w-24 h-24 bg-accent-500/10 rounded-3xl flex items-center justify-center mb-8 border border-accent-500/20">
                            {'is_not_ready' in dashboardData && (dashboardData as any).is_not_ready ? (
                                <Clock className="w-12 h-12 text-accent-400" />
                            ) : (
                                <Coffee className="w-12 h-12 text-amber-400" />
                            )}
                        </div>
                        <h2 className="text-3xl font-bold text-white mb-4">
                            {'is_not_ready' in dashboardData && (dashboardData as any).is_not_ready 
                                ? 'Data Not Available Yet'
                                : 'Market is Closed'}
                        </h2>
                        <div className="bg-slate-800/50 backdrop-blur-md border border-slate-700/50 rounded-2xl p-6 max-w-lg">
                            <p className="text-slate-300 text-lg mb-2">
                                {'is_not_ready' in dashboardData && (dashboardData as any).is_not_ready
                                    ? 'Positions for today have not been released by exchange yet.'
                                    : 'The National Stock Exchange (NSE) is closed today.'}
                            </p>
                            <div className="flex items-start justify-center gap-3 text-accent-400 font-medium text-lg sm:text-xl">
                                <AlertTriangle className="w-5 h-5 sm:w-6 sm:h-6 text-amber-400 shrink-0 mt-0.5 sm:mt-1" />
                                <span>{(dashboardData as any).description}</span>
                            </div>
                            <p className="mt-4 text-slate-500 text-sm">
                                {'is_not_ready' in dashboardData && (dashboardData as any).is_not_ready
                                    ? 'Automated data synchronization will resume once NSE publishes the official participant data.'
                                    : 'Positions and participant data are updated only on active trading days.'}
                            </p>
                        </div>
                    </motion.div>
                ) : dashboardData && 'participants' in dashboardData ? (
                    <motion.div
                        key={`data-${dashboardData.date}`}
                        variants={containerVariants}
                        initial="hidden"
                        animate="visible"
                        className="space-y-6"
                    >
                        {/* Sentiment Overview Cards */}
                        <motion.div variants={itemVariants}>
                            <SentimentOverview data={dashboardData} />
                        </motion.div>

                        {/* Main Positioning Table */}
                        <motion.div variants={itemVariants}>
                            <PositioningTable participants={dashboardData.participants} />
                        </motion.div>

                        {/* Participant Detailed Analysis */}
                        <motion.div variants={itemVariants}>
                            <ParticipantCards participants={dashboardData.participants} />
                        </motion.div>

                        {/* Market Verdict */}
                        <motion.div variants={itemVariants}>
                            <MarketVerdict data={dashboardData} />
                        </motion.div>
                    </motion.div>
                ) : null}

            </AnimatePresence>
        </div>
    )
}
