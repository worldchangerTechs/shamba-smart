import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip } from 'react-leaflet'
import type { FeatureCollection, Point } from 'geojson'

export type CountyFarmMarker = {
  id: number
  lat: number
  lng: number
  label: string
  slope: string
}

export type CountyOutbreakProperties = {
  id: number
  ward: string
  pest_name: string
  confirmed_count: number
  level: string
  crop?: string | null
}

export type CountyOutbreaks = FeatureCollection<Point, CountyOutbreakProperties>

export default function CountyDashboardMap({
  farms,
  outbreaks,
  showErosion,
  showOutbreaks,
}: {
  farms: CountyFarmMarker[]
  outbreaks?: CountyOutbreaks
  showErosion: boolean
  showOutbreaks: boolean
}) {
  return (
    <MapContainer center={[-0.68, 34.76]} zoom={9} scrollWheelZoom={false} className="county-dashboard-map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {showErosion && farms.map((farm) => {
        const color = farm.slope === 'STEEP' ? '#9E2012' : farm.slope === 'GENTLE' ? '#D8972C' : '#5B8C3A'
        return <CircleMarker key={`farm-${farm.id}`} center={[farm.lat, farm.lng]} radius={7} pathOptions={{ color, fillColor: color, fillOpacity: 0.62, weight: 2 }}>
          <Tooltip>{farm.label} · {farm.slope.toLowerCase()} slope screen</Tooltip>
        </CircleMarker>
      })}
      {showOutbreaks && outbreaks && <GeoJSON
        key={`outbreaks-${outbreaks.features.length}`}
        data={outbreaks}
        pointToLayer={(_feature, latlng) => L.circleMarker(latlng, {
          radius: 8,
          color: '#9E2012',
          fillColor: '#FF1A1A',
          fillOpacity: 0.35,
          weight: 2,
        })}
        onEachFeature={(feature, layer) => {
          const properties = feature.properties as CountyOutbreaks['features'][number]['properties']
          layer.bindTooltip(`${properties.ward}: ${properties.pest_name} · ${properties.confirmed_count} confirmed`)
        }}
      />}
    </MapContainer>
  )
}
