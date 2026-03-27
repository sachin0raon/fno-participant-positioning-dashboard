import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchDashboardData, fetchAvailableDates, fetchHealth } from '@/lib/api'
import type { DashboardData, DateOption, DashboardResponse } from '@/types'
import { useCallback } from 'react'

export function useDashboardData(date: string) {
  return useQuery<DashboardResponse, Error>({
    queryKey: ['fno-data', date],
    queryFn: () => fetchDashboardData(date),

    enabled: !!date,
    staleTime: 5 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 10000),
  })
}

export function useAvailableDates() {
  return useQuery<DateOption[], Error>({
    queryKey: ['available-dates'],
    queryFn: fetchAvailableDates,
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  })
}

export function useBackendHealth() {
  return useQuery<{ status: string; timestamp: string }, Error>({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
    retry: false,
    staleTime: 15_000,
  })
}

export function useRefreshDashboard() {
  const queryClient = useQueryClient()

  const refresh = useCallback(
    (date: string) => {
      return queryClient.invalidateQueries({ queryKey: ['fno-data', date] })
    },
    [queryClient],
  )

  return refresh
}
