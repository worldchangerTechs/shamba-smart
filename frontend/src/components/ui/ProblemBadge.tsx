import type React from 'react'
import {
  IconClimate,
  IconErosion,
  IconLearn,
  IconMarket,
  IconPest,
  IconProtection,
  IconSoil,
  IconWaste,
  type IconProps,
} from '../icons'

export type ProblemTag = 'erosion' | 'pests' | 'ppe' | 'soil' | 'climate' | 'market' | 'waste' | 'planting'
const problemIcons: Record<ProblemTag, React.ComponentType<IconProps>> = {
  erosion: IconErosion,
  pests: IconPest,
  ppe: IconProtection,
  soil: IconSoil,
  climate: IconClimate,
  market: IconMarket,
  waste: IconWaste,
  planting: IconLearn,
}
const labels: Record<ProblemTag, string> = {
  erosion: 'Erosion',
  pests: 'Pests',
  ppe: 'Spray safety',
  soil: 'Soil health',
  climate: 'Climate',
  market: 'Market',
  waste: 'Waste',
  planting: 'Planting',
}

export function ProblemBadge({ problem, label }: { problem: ProblemTag; label?: string }) {
  const Icon = problemIcons[problem]
  return (
    <span className={`problem-badge problem-${problem}`}>
      <Icon size={15} aria-hidden />
      <span>{label ?? labels[problem]}</span>
    </span>
  )
}
