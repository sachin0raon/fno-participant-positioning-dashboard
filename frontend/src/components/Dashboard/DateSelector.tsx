import { motion } from 'framer-motion'
import { Calendar, ChevronDown } from 'lucide-react'
import * as Select from '@radix-ui/react-select'
import { cn } from '@/lib/utils'
import type { DateOption } from '@/types'

interface DateSelectorProps {
  dates: DateOption[]
  selectedDate: string
  onChange: (value: string) => void
}

export function DateSelector({ dates, selectedDate, onChange }: DateSelectorProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="flex items-center gap-3"
    >
      <div className="flex items-center gap-2 text-surface-400">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-accent-500/10 border border-accent-500/20">
          <Calendar className="w-4 h-4 text-accent-400" />
        </div>
        <span className="text-sm font-medium hidden sm:inline">Trading Date</span>
      </div>

      <Select.Root value={selectedDate} onValueChange={onChange}>
        <Select.Trigger
          id="date-selector"
          className={cn(
            'inline-flex items-center justify-between gap-2',
            'px-4 py-2.5 min-w-[220px]',
            'glass-strong rounded-xl',
            'text-sm text-white font-medium',
            'transition-all duration-200',
            'hover:bg-white/[0.08]',
            'focus:outline-none focus:ring-2 focus:ring-accent-500/40',
            'data-[state=open]:bg-white/[0.1] data-[state=open]:ring-2 data-[state=open]:ring-accent-500/40',
          )}
        >
          <Select.Value placeholder="Select date…" />
          <Select.Icon>
            <ChevronDown className="w-4 h-4 text-surface-400" />
          </Select.Icon>
        </Select.Trigger>

        <Select.Portal>
          <Select.Content
            className={cn(
              'overflow-y-auto z-[100]',
              'bg-surface-900/95 backdrop-blur-xl',
              'border border-white/[0.08]',
              'rounded-xl shadow-2xl shadow-black/40',
              'max-h-[320px]',
              '[-webkit-overflow-scrolling:touch]',
            )}
            position="popper"
            sideOffset={8}
            align="start"
          >
            <Select.ScrollUpButton className="flex items-center justify-center h-6 text-surface-400">
              <ChevronDown className="w-4 h-4 rotate-180" />
            </Select.ScrollUpButton>

            <Select.Viewport className="p-1.5">
              {dates.map((date) => (
                <Select.Item
                  key={date.value}
                  value={date.value}
                  className={cn(
                    'relative flex items-center px-3 py-2.5',
                    'text-sm text-surface-300 rounded-lg',
                    'cursor-pointer outline-none select-none',
                    'transition-colors duration-150',
                    'data-[highlighted]:bg-accent-500/15 data-[highlighted]:text-white',
                    'data-[state=checked]:text-accent-400 data-[state=checked]:font-medium',
                  )}
                >
                  <Select.ItemText>{date.label}</Select.ItemText>
                </Select.Item>
              ))}
            </Select.Viewport>

            <Select.ScrollDownButton className="flex items-center justify-center h-6 text-surface-400">
              <ChevronDown className="w-4 h-4" />
            </Select.ScrollDownButton>
          </Select.Content>
        </Select.Portal>
      </Select.Root>
    </motion.div>
  )
}
