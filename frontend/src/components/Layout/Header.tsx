import { motion } from 'framer-motion'
import { TrendingUp, Wifi, WifiOff } from 'lucide-react'
import { useBackendHealth } from '@/hooks/useFNOData'
import { cn } from '@/lib/utils'
import { TimeLabel } from '../Dashboard/TimeLabel'

export function Header() {
  const { data: health, isLoading } = useBackendHealth()
  const isConnected = health?.status === 'healthy'

  return (
    <motion.header
      initial={{ y: -60, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="sticky top-0 z-50 border-b border-white/[0.06] bg-surface-950/70 backdrop-blur-2xl"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          {/* Logo */}
          <motion.div
            className="flex items-center gap-3"
            whileHover={{ scale: 1.02 }}
            transition={{ type: 'spring', stiffness: 400, damping: 15 }}
          >
            <div className="relative">
              <div className="absolute inset-0 bg-accent-500/25 blur-lg rounded-xl" />
              <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-accent-500 to-fuchsia-500 shadow-lg shadow-accent-500/20">
                <TrendingUp className="w-5 h-5 text-white" />
              </div>
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight gradient-text leading-tight">
                F&O Dashboard
              </h1>
              <p className="text-[11px] text-surface-400 tracking-wide leading-tight">
                NSE India Positioning Data
              </p>
            </div>
          </motion.div>

          {/* Time and Status Group */}
          <div className="flex items-center gap-6">
            <TimeLabel />

            {/* Backend Status */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="flex items-center gap-2"
            >
              <div
                className={cn(
                  'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300',
                  isConnected
                    ? 'bg-bullish-500/10 text-bullish-400 border border-bullish-500/20'
                    : isLoading
                      ? 'bg-neutral-500/10 text-neutral-400 border border-neutral-500/20'
                      : 'bg-bearish-500/10 text-bearish-400 border border-bearish-500/20',
                )}
              >
                {isLoading ? (
                  <div className="w-2 h-2 rounded-full bg-neutral-400 animate-pulse" />
                ) : isConnected ? (
                  <Wifi className="w-3.5 h-3.5" />
                ) : (
                  <WifiOff className="w-3.5 h-3.5" />
                )}
                <span>
                  {isLoading ? 'Connecting…' : isConnected ? 'Backend Live' : 'Disconnected'}
                </span>
              </div>
            </motion.div>
          </div>
        </div>
      </div>
    </motion.header>
  )
}
