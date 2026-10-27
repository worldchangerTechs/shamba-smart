export type Language = 'en' | 'sw' | 'guz'

export interface ApiList<T> {
  count?: number
  results?: T[]
}

export interface FarmerUser {
  id: number
  phone: string
  first_name: string
  last_name: string
  role: 'FARMER' | 'OFFICER' | 'ADMIN'
  language: Language
}

export interface Farm {
  id: number
  name: string
  size_acres: string | number
  slope_class: 'FLAT' | 'GENTLE' | 'STEEP'
  farmer: number
  lat: number
  lng: number
  soil_type?: string
  soil_ph?: number | null
}

export interface FarmerAlert {
  id: number
  severity: 'INFO' | 'WATCH' | 'URGENT' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  title: string
  body_by_language: Partial<Record<Language, string>>
  status: string
  created_at: string
}

export interface MarketPrice {
  id: number
  crop: number | { id: number; name: string }
  market_name: string
  price_per_kg: string | number
  date: string
  is_sample_data?: boolean
}

export interface WeatherSnapshot {
  id: number
  date: string
  rain_mm: number
  temp_min: number
  temp_max: number
  humidity: number
  ward: number | { id: number; name: string }
  forecast_json?: Record<string, unknown> | null
}

export function getList<T>(payload: T[] | ApiList<T> | undefined): T[] {
  if (!payload) return []
  return Array.isArray(payload) ? payload : payload.results ?? []
}
