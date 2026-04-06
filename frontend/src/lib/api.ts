import type { DashboardData, DateOption, DashboardResponse } from '@/types'

const API_BASE_URL = '/api'

export async function fetchDashboardData(
  date: string,
  contrarianRetail: boolean = false,
): Promise<DashboardResponse> {
  const params = new URLSearchParams({
    date,
    contrarian_retail: String(contrarianRetail),
  })

  const response = await fetch(`${API_BASE_URL}/fno-data?${params}`)

  if (!response.ok) {
    const errorBody = await response.text().catch(() => response.statusText)
    throw new Error(`Failed to fetch data: ${errorBody}`)
  }

  return response.json()
}

export async function fetchAvailableDates(): Promise<DateOption[]> {
  const response = await fetch(`${API_BASE_URL}/available-dates`)

  if (!response.ok) {
    throw new Error(`Failed to fetch dates: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchHealth(): Promise<{ status: string; timestamp: string }> {
  const response = await fetch(`${API_BASE_URL}/health`)

  if (!response.ok) {
    throw new Error('Backend not available')
  }

  return response.json()
}
