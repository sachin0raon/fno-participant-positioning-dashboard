import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock } from 'lucide-react';

export function TimeLabel() {
    const [time, setTime] = useState(new Date());

    useEffect(() => {
        const timer = setInterval(() => {
            setTime(new Date());
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    const formattedDate = time.toLocaleDateString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
    });

    const hoursMinutes = time.toLocaleTimeString(undefined, {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
    });

    const seconds = time.toLocaleTimeString(undefined, {
        second: '2-digit',
    });

    return (
        <div className="flex flex-col items-end">
            <div className="flex items-center gap-2 text-surface-100 font-mono text-sm sm:text-base font-bold tracking-tight">
                <Clock className="w-4 h-4 text-accent-500 animate-pulse" />
                <div className="flex items-center min-w-[5.5rem] justify-end">
                    <span className="text-surface-100">{hoursMinutes.split(' ')[0]}</span>
                    <span className="text-accent-500/50 mx-0.5">:</span>
                    <div className="w-[1.2rem] flex justify-center overflow-hidden">
                        <AnimatePresence mode="popLayout">
                            <motion.span
                                key={seconds}
                                initial={{ y: 8, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ y: -8, opacity: 0 }}
                                transition={{ duration: 0.25, ease: "easeOut" }}
                                className="inline-block text-accent-400"
                            >
                                {seconds}
                            </motion.span>
                        </AnimatePresence>
                    </div>
                    <span className="ml-1.5 px-1 py-0.5 rounded text-[10px] sm:text-xs bg-accent-500/10 text-accent-400 font-black uppercase tracking-wider">
                        {hoursMinutes.split(' ')[1]}
                    </span>
                </div>
            </div>
            <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-surface-400 mt-0.5">
                {formattedDate}
            </span>
        </div>
    );
}
