import 'leaflet/dist/leaflet.css'
import { CircleMarker, MapContainer, TileLayer, Tooltip } from 'react-leaflet'

const reports = [
  { position: [-0.677, 34.779] as [number, number], ward: 'Kisii Central', reports: 4 },
  { position: [-0.742, 34.812] as [number, number], ward: 'Bobasi', reports: 3 },
  { position: [-0.615, 34.706] as [number, number], ward: 'Nyamache', reports: 2 },
  { position: [-0.702, 34.678] as [number, number], ward: 'Marani', reports: 1 },
]

export default function OutbreakMap({ reduced }: { reduced: boolean }) {
  return (
    <MapContainer
      center={[-0.68, 34.76]}
      zoom={10}
      scrollWheelZoom={false}
      className={`outbreak-map ${reduced ? 'outbreak-map-reduced' : ''}`}
      attributionControl
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {reports.map(({ position, ward, reports: count }) => (
        <CircleMarker
          key={ward}
          center={position}
          radius={10 + count * 3}
          pathOptions={{
            color: '#9E2012',
            weight: 2,
            fillColor: '#FF1A1A',
            fillOpacity: 0.22,
          }}
        >
          <Tooltip direction="top" offset={[0, -8]}>{ward}: {count} sample reports</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
