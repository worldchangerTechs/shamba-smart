import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'

export type FarmerMapMarker = {
  id: number | string
  lat: number
  lng: number
  label: string
  detail?: string
}

export default function FarmerMap({ markers = [] }: { markers?: FarmerMapMarker[] }) {
  const center: [number, number] = markers.length
    ? [markers.reduce((sum, marker) => sum + marker.lat, 0) / markers.length, markers.reduce((sum, marker) => sum + marker.lng, 0) / markers.length]
    : [-0.68, 34.76]

  return (
    <MapContainer center={center} zoom={markers.length === 1 ? 12 : 10} scrollWheelZoom={false} className="farmer-leaflet-map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {markers.map((marker) => (
        <CircleMarker key={marker.id} center={[marker.lat, marker.lng]} radius={9} pathOptions={{ color: '#1B4D1E', weight: 2, fillColor: '#5B8C3A', fillOpacity: 0.72 }}>
          <Tooltip direction="top" offset={[0, -8]}>{marker.label}{marker.detail ? `: ${marker.detail}` : ''}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
