import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'
import type { CSSProperties, ReactNode } from 'react'
import {
  motion,
  useInView,
  useReducedMotion as useMotionReducedMotion,
  useScroll,
  useTransform,
} from 'framer-motion'
import {
  IconArrowDown as ArrowDown,
  IconArrowDownRight as ArrowDownRight,
  IconArrowRight as ArrowRight,
  IconArrowUpRight as ArrowUpRight,
  IconAudioLines as AudioLines,
  IconBarChart as BarChart3,
  IconAlert as Bell,
  IconPest as Bug,
  IconCheck as Check,
  IconChevronDown as ChevronDown,
  IconCloudRain as CloudRain,
  IconErosion as Droplets,
  IconLearn as Flower2,
  IconLeaf as Leaf,
  IconLocation as MapPin,
  IconMenu as Menu,
  IconMessageSquare as MessageCircle,
  IconPhone as Phone,
  IconShieldCheck as ShieldCheck,
  IconSmartphone as Smartphone,
  IconSprout as Sprout,
  IconTractor as Tractor,
  IconTrendingUp as TrendingUp,
  IconWaves as Waves,
  IconClose as X,
} from '../components/icons'
import { Link } from 'react-router-dom'
import { LanguageSwitcher } from '../components/ui/LanguageSwitcher'
import type { ProblemTag } from '../components/ui/ProblemBadge'
import { useI18n } from '../i18n/I18nProvider'
import './landing.css'

const OutbreakMap = lazy(() => import('../components/landing/OutbreakMap'))
const landingAssets = import.meta.glob('../assets/*', {
  eager: true,
  query: '?url',
  import: 'default',
}) as Record<string, string>

type Problem = {
  tag: ProblemTag
  title: string
  story: string
  stat: string
  icon: React.ComponentType<{ size?: number; className?: string }>
  photo?: string
  alt?: string
}

const problems: Problem[] = [
  { tag: 'climate', title: 'Uncertain rains', story: 'â€œI planted after the first shower. Then the dry days came.â€', stat: '14-day forecast', icon: CloudRain, photo: 'climate', alt: 'Paper strips reading climate change' },
  { tag: 'soil', title: 'Tired soil', story: 'â€œThe harvest gets smaller, even when I work harder.â€', stat: '8 ways', icon: Sprout },
  { tag: 'ppe', title: 'Unsafe spraying', story: 'â€œI did not know how long to wait before picking.â€', stat: '1 checklist', icon: ShieldCheck },
  { tag: 'erosion', title: 'Soil washing away', story: 'â€œHeavy rain carries my topsoil down the hill.â€', stat: '3 controls', icon: Waves, photo: 'erosion', alt: 'Gully erosion cutting through a farm and exposing tree roots' },
  { tag: 'pests', title: 'Pests without warning', story: 'â€œBy the time I saw the damage, the caterpillars had spread.â€', stat: '7 days', icon: Bug, photo: 'pest-armyworm', alt: 'A caterpillar feeding on a maize cob' },
  { tag: 'market', title: 'A price guessed too late', story: 'â€œI sold before I knew what the next market was paying.â€', stat: '30 km', icon: TrendingUp },
  { tag: 'waste', title: 'No safe place for waste', story: 'â€œThe empty chemical container was left near the stream.â€', stat: '1 safe route', icon: Droplets },
  { tag: 'planting', title: 'Good advice, out of reach', story: 'â€œThe lesson was useful. The phone could not open it.â€', stat: '3 channels', icon: Phone },
]

const moduleCards: { title: string; tag: string; summary: string; benefit: string; icon: React.ComponentType<{ size?: number; className?: string }> }[] = [
  { title: 'Mvua Planner', tag: 'WEATHER', summary: 'Make the most of the coming rain.', benefit: 'Know when to plant, weed, feed and harvest.', icon: CloudRain },
  { title: 'Udongo Doctor', tag: 'SOIL', summary: 'Understand the soil beneath your crop.', benefit: 'Simple steps for soil health, ranked by cost.', icon: Sprout },
  { title: 'Spray Safe', tag: 'SAFETY', summary: 'Protect yourself and your harvest.', benefit: 'PPE checks, re-entry time and harvest dates.', icon: ShieldCheck },
  { title: 'Soko Link', tag: 'MARKET', summary: 'See prices before you sell.', benefit: 'Compare markets and connect with buyers.', icon: TrendingUp },
  { title: 'Pest Radar', tag: 'PESTS', summary: 'See what farmers nearby are reporting.', benefit: 'Early area alerts with practical first steps.', icon: Bug },
  { title: 'Mteremko Guard', tag: 'EROSION', summary: 'Keep your soil where your crops need it.', benefit: 'Low-cost erosion controls for your slope.', icon: Waves },
  { title: 'Shamba Academy', tag: 'LEARN', summary: 'Small lessons for the work in front of you.', benefit: 'Short lessons that work on a basic phone.', icon: Flower2 },
  { title: 'Taka Loop', tag: 'WASTE', summary: 'Turn farm waste into a safer resource.', benefit: 'Compost ideas and nearby disposal guidance.', icon: Leaf },
]

const sections = [
  ['home', 'Home'],
  ['problem', 'The problem'],
  ['climate', 'Climate'],
  ['erosion', 'Erosion'],
  ['pests', 'Pest radar'],
  ['how-it-works', 'How it works'],
  ['modules', 'Modules'],
  ['impact', 'Impact'],
] as const

function AssetPicture({
  name,
  alt,
  className = '',
  eager = false,
}: {
  name: string
  alt: string
  className?: string
  eager?: boolean
}) {
  const [failed, setFailed] = useState(false)
  const jpg = landingAssets[`../assets/${name}.jpg`]
  const webp800 = landingAssets[`../assets/${name}-800.webp`]
  const webp1600 = landingAssets[`../assets/${name}-1600.webp`]
  const sourceSet = [
    webp800 && `${webp800} 800w`,
    webp1600 && `${webp1600} 1600w`,
  ].filter(Boolean).join(', ')
  const fallbackSource = jpg ?? webp800 ?? webp1600
  return (
    <div className={`asset-picture asset-picture-${name} ${className} ${failed || !fallbackSource ? 'asset-missing' : ''}`}>
      {!failed && fallbackSource && (
        <picture>
          {sourceSet && <source type="image/webp" srcSet={sourceSet} sizes="(max-width: 700px) 100vw, 80vw" />}
          <img
            src={fallbackSource}
            alt={alt}
            loading={eager ? 'eager' : 'lazy'}
            decoding="async"
            onError={() => setFailed(true)}
          />
        </picture>
      )}
      <span className="asset-gradient" aria-hidden />
    </div>
  )
}

function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode
  className?: string
  delay?: number
}) {
  const reduceMotion = useMotionReducedMotion()
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: reduceMotion ? 0 : 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.18 }}
      transition={{ duration: reduceMotion ? 0.18 : 0.65, delay: reduceMotion ? 0 : delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  )
}

function CountUp({ value, suffix = '', label }: { value: number; suffix?: string; label: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const isInView = useInView(ref, { once: true })
  const reduced = useMotionReducedMotion()
  const [count, setCount] = useState(reduced ? value : 0)
  useEffect(() => {
    if (!isInView) return
    if (reduced) {
      setCount(value)
      return
    }
    const start = performance.now()
    const duration = 1100
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - (1 - progress) ** 4
      setCount(Math.round(eased * value))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [isInView, reduced, value])
  return <div className="count-item"><span ref={ref} className="count-number">{count}{suffix}</span><span className="count-label">{label}</span></div>
}

function SectionHeading({ eyebrow, title, description, light = false }: {
  eyebrow: string
  title: string
  description?: string
  light?: boolean
}) {
  return (
    <div className={`section-heading section-heading-landing ${light ? 'heading-light' : ''}`}>
      <p className="landing-eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      {description && <p className="section-description">{description}</p>}
    </div>
  )
}

function RainChart({ progress }: { progress: number }) {
  const reduced = useMotionReducedMotion()
  return (
    <svg className="rain-chart" viewBox="0 0 500 260" role="img" aria-label="Illustration of rainfall and temperature patterns across a planting season">
      <defs>
        <linearGradient id="rainFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#5B8C3A" stopOpacity=".35" />
          <stop offset="1" stopColor="#5B8C3A" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[50, 100, 150, 200].map((y) => <line key={y} x1="40" y1={y} x2="470" y2={y} className="chart-grid" />)}
      <path d="M40 198 C85 190,95 165,130 174 S182 205,220 152 S282 137,315 120 S373 147,405 97 S448 73,470 62 L470 215 L40 215 Z" fill="url(#rainFill)" />
      <motion.path
        d="M40 198 C85 190,95 165,130 174 S182 205,220 152 S282 137,315 120 S373 147,405 97 S448 73,470 62"
        fill="none"
        className="chart-line chart-rain"
        pathLength={1}
        initial={{ pathLength: reduced ? 1 : 0 }}
        animate={{ pathLength: reduced ? 1 : progress }}
        transition={{ duration: reduced ? 0.15 : 1.2, ease: 'easeInOut' }}
      />
      <motion.path
        d="M40 116 C90 105,95 127,135 119 S184 108,220 119 S277 92,318 102 S367 112,405 92 S446 106,470 87"
        fill="none"
        className="chart-line chart-temp"
        pathLength={1}
        initial={{ pathLength: reduced ? 1 : 0 }}
        animate={{ pathLength: reduced ? 1 : progress }}
        transition={{ duration: reduced ? 0.15 : 1.35, delay: reduced ? 0 : 0.12, ease: 'easeInOut' }}
      />
      {['Wk 1', 'Wk 2', 'Wk 3', 'Wk 4', 'Wk 5'].map((label, index) => (
        <text key={label} x={40 + index * 105} y="242" className="chart-label">{label}</text>
      ))}
      <circle cx="405" cy="97" r="5" className="chart-point" />
      <text x="377" y="73" className="chart-note">plant window</text>
    </svg>
  )
}

function ClimateScene({ reduced }: { reduced: boolean }) {
  const ref = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] })
  const saturate = useTransform(scrollYProgress, [0, 0.65], [0.25, 1])
  const chartProgress = useTransform(scrollYProgress, [0.08, 0.78], [0, 1])
  const photoFilter = useTransform(saturate, (value) => `saturate(${value}) sepia(${1 - value})`)
  const chart = useTransform(chartProgress, (value) => value)
  const [chartDraw, setChartDraw] = useState(0)
  useEffect(() => chart.on('change', (value) => setChartDraw(value)), [chart])
  return (
    <section id="climate" className="climate-scene" ref={ref}>
      <div className="climate-sticky">
        <motion.div className="climate-photo-wrap" style={reduced ? undefined : { filter: photoFilter }}>
          <AssetPicture name="climate" alt="Paper strips reading climate change, illustrating shifting growing conditions" />
        </motion.div>
        <div className="climate-shade" />
        <div className="climate-inner">
          <Reveal className="climate-copy">
            <p className="landing-eyebrow">01 / CLIMATE</p>
            <h2>Plant when the weather says yes.</h2>
            <p>Rainfall history and the 14-day forecast become a clear planting window, not another guess.</p>
            <div className="climate-points">
              <span><Check size={16} /> Rain-ready planting advice</span>
              <span><Check size={16} /> Week-by-week farm calendar</span>
              <span><Check size={16} /> Alerts in your language</span>
            </div>
          </Reveal>
          <motion.div
            className="chart-card"
            initial={{ opacity: 0, y: reduced ? 0 : 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: reduced ? 0.2 : 0.7 }}
          >
            <div className="chart-card-head">
              <div><span className="chart-kicker">MVUA PLANNER</span><h3>Rain is building</h3></div>
              <span className="rain-status"><CloudRain size={14} /> GOOD WINDOW</span>
            </div>
            <RainChart progress={reduced ? 1 : chartDraw} />
            <div className="plant-window"><span className="plant-window-icon"><Sprout size={19} /></span><div><strong>Plant this week</strong><small>Soil moisture is improving in your ward</small></div><ArrowUpRight size={18} /></div>
          </motion.div>
          <div className="climate-scroll-hint"><ArrowDown size={17} /> Scroll to see the forecast</div>
        </div>
      </div>
    </section>
  )
}

function PhoneMockup() {
  return (
    <div className="phone-mockup">
      <div className="phone-notch" />
      <div className="phone-content">
        <div className="phone-status"><span>9:41</span><span>â—â—â— â–°</span></div>
        <div className="phone-brand"><span className="mini-leaf"><Sprout size={14} /></span><span>shamba</span><Bell size={15} /></div>
        <div className="phone-greeting">Habari, Amina</div>
        <div className="phone-weather"><CloudRain size={20} /><div><strong>Rain expected</strong><small>In 2 hours Â· Kisii Central</small></div></div>
        <div className="phone-card-label">YOUR PLANTING WINDOW</div>
        <div className="phone-plant"><span>ðŸŒ±</span><div><strong>Plant this week</strong><small>Good soil moisture ahead</small></div></div>
        <div className="phone-nav"><Sprout size={14} /><BarChart3 size={14} /><BookOpenIcon /><Phone size={14} /></div>
      </div>
    </div>
  )
}

function BookOpenIcon() {
  return <Flower2 size={14} />
}

function RiskGauge({ score }: { score: number }) {
  const circumference = Math.PI * 56
  return (
    <div className="risk-gauge">
      <svg viewBox="0 0 140 90" aria-label={`Erosion risk score ${score} out of 100`}>
        <path d="M14 76 A56 56 0 0 1 126 76" className="gauge-track" pathLength={100} />
        <motion.path d="M14 76 A56 56 0 0 1 126 76" className="gauge-value" pathLength={100} animate={{ strokeDasharray: `${circumference * (score / 100)} ${circumference}` }} transition={{ duration: 0.55 }} />
      </svg>
      <div className="gauge-number"><strong>{score}</strong><span>/100</span></div>
    </div>
  )
}

function ErosionSection({ reduced }: { reduced: boolean }) {
  const [slope, setSlope] = useState(2)
  const slopes = ['Flat', 'Gentle', 'Steep']
  const scores = [18, 46, 82]
  const controls = [
    { name: 'Napier grass strips', detail: 'Plant across the slope', cost: 'LOW COST', effort: 'LOW EFFORT', icon: Sprout },
    { name: 'Trash lines', detail: 'Use crop residue as a barrier', cost: 'NO COST', effort: 'LOW EFFORT', icon: Leaf },
    { name: 'Terraces', detail: 'Shape the hillside into steps', cost: 'HIGHER COST', effort: 'MORE WORK', icon: Tractor },
  ]
  const ranked = slope === 0
    ? [controls[1], controls[0], controls[2]]
    : slope === 1
      ? controls
      : [controls[0], controls[2], controls[1]]
  return (
    <section className="erosion-section" id="erosion">
      <div className="erosion-layout">
        <div className="erosion-visual">
          <motion.div
            className="erosion-photo-frame"
            initial={{ clipPath: reduced ? 'inset(0)' : 'inset(0 100% 0 0)' }}
            whileInView={{ clipPath: 'inset(0)' }}
            viewport={{ once: true, amount: 0.3 }}
            transition={{ duration: reduced ? 0.2 : 1.1, ease: [0.77, 0, 0.18, 1] }}
          >
            <AssetPicture name="erosion" alt="Gully erosion exposing tree roots on a sloped farm" />
          </motion.div>
          <div className="erosion-image-caption"><Waves size={17} /><span>Keep the soil. Slow the water.</span></div>
        </div>
        <div className="erosion-copy">
          <p className="landing-eyebrow">02 / EROSION</p>
          <h2>Protect the soil that feeds your farm.</h2>
          <p className="erosion-intro">Rain and slope matter. See which simple controls can hold your topsoil in place.</p>
          <div className="slope-label-row"><span>YOUR SLOPE</span><strong>{slopes[slope]}</strong></div>
          <input
            aria-label="Select your farm slope"
            className="slope-slider"
            type="range"
            min="0"
            max="2"
            step="1"
            value={slope}
            onChange={(event) => setSlope(Number(event.target.value))}
          />
          <div className="slope-ticks"><span>Flat</span><span>Gentle</span><span>Steep</span></div>
          <div className="risk-row"><RiskGauge score={scores[slope]} /><div><span className="risk-caption">EROSION RISK</span><p>{slope === 2 ? 'Heavy rain can quickly remove valuable topsoil.' : slope === 1 ? 'Some runoff risk. Low-cost barriers can help.' : 'Lower slope risk. Keep the ground covered.'}</p></div></div>
          <div className="erosion-controls">
            {ranked.map(({ name, detail, cost, effort, icon: Icon }, index) => (
              <motion.div className="erosion-control" key={name} layout transition={{ duration: reduced ? 0.1 : 0.35 }}>
                <span className="control-rank">0{index + 1}</span><span className="control-icon"><Icon size={18} /></span>
                <div className="control-copy"><strong>{name}</strong><small>{detail}</small></div>
                <span className="control-cost">{slope === 2 && index === 0 ? 'BEST FIT' : cost}</span>
                <span className="control-effort">{effort}</span>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function PestPhoto({ name, alt, label }: { name: string; alt: string; label: string }) {
  return (
    <div className="pest-photo">
      <AssetPicture name={name} alt={alt} />
      <span className="pest-hotspot hotspot-one" aria-hidden />
      <span className="pest-hotspot hotspot-two" aria-hidden />
      <span className="pest-photo-label">{label}</span>
      <span className="pest-photo-shade" aria-hidden />
    </div>
  )
}

function PestSection({ reduced }: { reduced: boolean }) {
  const mapRef = useRef<HTMLDivElement>(null)
  const [mapVisible, setMapVisible] = useState(false)
  useEffect(() => {
    const element = mapRef.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setMapVisible(true)
        observer.disconnect()
      }
    }, { rootMargin: '200px' })
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return (
    <section className="pest-section" id="pests">
      <div className="pest-inner">
        <Reveal>
          <SectionHeading eyebrow="03 / PEST RADAR" title="When pests move, farmers know." description="A farmerâ€™s report can help the next farm act sooner. Officers verify reports before area alerts go out." />
        </Reveal>
        <div className="pest-photo-grid">
          <Reveal delay={0.03}><PestPhoto name="pest-armyworm" label="FALL ARMYWORM Â· MAIZE" alt="Caterpillar eating a maize cob, illustrating a fall armyworm report" /></Reveal>
          <Reveal delay={0.13}><PestPhoto name="pest-aphids" label="APHIDS Â· UNDER LEAF" alt="Aphids and other small insects clustered beneath a leaf" /></Reveal>
        </div>
        <div className="outbreak-layout">
          <div className="outbreak-copy">
            <span className="outbreak-live"><span /> WARD REPORTS Â· SAMPLE VIEW</span>
            <h3>Local signals.<br />Earlier action.</h3>
            <p>Confirmed reports help neighbours spot risk nearby, without calling a photo diagnosis.</p>
            <div className="outbreak-rule"><strong>3</strong><span>confirmed reports<br />in 7 days</span><ArrowRight size={21} /></div>
            <p className="outbreak-result"><Bell size={16} /> = area alert for nearby farmers growing the same crop</p>
          </div>
          <div className="map-shell" ref={mapRef}>
            {mapVisible
              ? <Suspense fallback={<div className="map-loading">Loading Kisii outbreak mapâ€¦</div>}><OutbreakMap reduced={reduced} /></Suspense>
              : <div className="map-loading">Outbreak reports in Kisii County</div>}
            <div className="map-stamp"><MapPin size={14} /> KISII COUNTY</div>
            <p className="map-footnote">Illustrative reports Â· not live surveillance data</p>
          </div>
        </div>
      </div>
    </section>
  )
}

function HowItWorks({ reduced }: { reduced: boolean }) {
  const nodes = [
    { icon: CloudRain, title: 'Sources', note: 'Weather Â· prices Â· farmer reports' },
    { icon: Sprout, title: 'Shamba brain', note: 'Rules Â· local crop knowledge' },
    { icon: MessageCircle, title: 'Messenger', note: 'App Â· SMS Â· voice' },
    { icon: Tractor, title: 'Farmer', note: 'Clear advice Â· right time' },
    { icon: Check, title: 'Feedback', note: 'Helpful? Â· improve the next alert' },
  ]
  return (
    <section className="how-section" id="how-it-works">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="04 / HOW IT WORKS" title="Local knowledge. Connected." description="A simple loop moves useful information from trusted sources to the people who can use it." /></Reveal>
        <div className="flow-diagram">
          <svg className="flow-lines" viewBox="0 0 1000 120" preserveAspectRatio="none" aria-hidden="true">
            <motion.path d="M70 60 H930" initial={{ pathLength: reduced ? 1 : 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: reduced ? 0.15 : 1.7, ease: 'easeInOut' }} />
            <motion.path d="M930 75 C780 118 220 118 70 75" initial={{ pathLength: reduced ? 1 : 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: reduced ? 0.15 : 1.4, delay: reduced ? 0 : 0.45, ease: 'easeInOut' }} />
            <motion.path className="flow-mobile-line" d="M500 0 V120" initial={{ pathLength: reduced ? 1 : 0 }} whileInView={{ pathLength: 1 }} viewport={{ once: true }} transition={{ duration: reduced ? 0.15 : 1.2, ease: 'easeInOut' }} />
          </svg>
          <div className="flow-nodes">
            {nodes.map(({ icon: Icon, title, note }, index) => (
              <motion.div
                className="flow-node"
                key={title}
                initial={{ opacity: 0, y: reduced ? 0 : 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.55 }}
                transition={{ duration: reduced ? 0.16 : 0.5, delay: reduced ? 0 : index * 0.11 }}
              >
                <span className="flow-node-number">0{index + 1}</span>
                <span className="flow-node-icon"><Icon size={21} /></span>
                <strong>{title}</strong>
                <small>{note}</small>
              </motion.div>
            ))}
          </div>
          <span className="feedback-label">THE FEEDBACK LOOP</span>
        </div>
      </div>
    </section>
  )
}

function UssdDemo() {
  const [screen, setScreen] = useState(0)
  const [trail, setTrail] = useState<string[]>([])
  const menu = useMemo(() => [
    { title: 'SHAMBA SMART 360', lines: ['1. Weather & planting', '2. Crop prices', '3. Pest alerts', '4. Ask an officer'], choices: ['1', '2', '3', '4'] },
    { title: 'WEATHER Â· KISII CENTRAL', lines: ['Rain expected tomorrow.', 'Planting window: GOOD', '1. Back to menu'], choices: ['1'] },
    { title: 'MARKET PRICES Â· KISII', lines: ['Tomato  KES 84/kg', 'Beans   KES 126/kg', '1. Back to menu'], choices: ['1'] },
    { title: 'PEST ALERTS Â· NYAMACHE', lines: ['Fall armyworm reported.', 'Check maize whorls today.', '1. Back to menu'], choices: ['1'] },
    { title: 'ASK AN OFFICER', lines: ['Leave a short message.', 'An officer can call you.', '1. Back to menu'], choices: ['1'] },
  ], [])
  const pick = (choice: string) => {
    setTrail((current) => [...current, choice])
    if (screen === 0) setScreen(Number(choice))
    else setScreen(0)
  }
  const reset = () => {
    setScreen(0)
    setTrail([])
  }
  return (
    <div className="ussd-phone" aria-label="Interactive USSD menu demo">
      <div className="ussd-speaker" />
      <div className="ussd-screen">
        <div className="ussd-network"><span>SHAMBA DEMO</span><span>â— â— â–´</span></div>
        <strong>{menu[screen].title}</strong>
        <div className="ussd-lines">{menu[screen].lines.map((line) => <span key={line}>{line}</span>)}</div>
        <div className="ussd-history">Key pressed: {trail[trail.length - 1] ?? 'â€”'}</div>
        <div className="ussd-keys">
          {menu[screen].choices.map((key) => <button key={key} onClick={() => pick(key)} aria-label={`Select ${key}`}>{key}</button>)}
          <button onClick={reset} aria-label="Restart USSD demo">âŒ‚</button>
          <button onClick={reset} aria-label="Restart USSD demo">â†µ</button>
        </div>
      </div>
      <div className="ussd-home" />
    </div>
  )
}

function VoiceWaveform({ reduced }: { reduced: boolean }) {
  return (
    <div className={`voice-wave ${reduced ? 'wave-static' : ''}`} role="img" aria-label="Voice call waveform">
      {Array.from({ length: 35 }, (_, index) =>       <i key={index} style={{ '--bar': `${12 + ((index * 17) % 40)}%`, '--delay': `${index * 0.035}s` } as CSSProperties} />)}
    </div>
  )
}

function PhoneSection({ reduced }: { reduced: boolean }) {
  return (
    <section className="phone-section" id="any-phone">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="05 / ANY PHONE" title="Smartphone, basic phone, or voice." description="Useful advice should not depend on the phone in your pocket." /></Reveal>
        <div className="phone-options">
          <Reveal className="phone-option">
            <div className="phone-option-heading"><span className="phone-option-icon"><Smartphone size={19} /></span><div><p>SMARTPHONE</p><h3>Tap for the full picture.</h3></div></div>
            <div className="smartphone-stage"><PhoneMockup /></div>
            <p className="phone-option-foot">Forecasts Â· farm calendar Â· local alerts</p>
          </Reveal>
          <Reveal className="phone-option" delay={0.1}>
            <div className="phone-option-heading"><span className="phone-option-icon"><Phone size={19} /></span><div><p>BASIC PHONE</p><h3>Dial in. Get the next step.</h3></div></div>
            <div className="ussd-stage"><UssdDemo /></div>
            <p className="phone-option-foot">Try the menu above â€” no app required</p>
          </Reveal>
          <Reveal className="phone-option" delay={0.2}>
            <div className="phone-option-heading"><span className="phone-option-icon"><AudioLines size={19} /></span><div><p>VOICE CALL</p><h3>Hear advice in Ekegusii.</h3></div></div>
            <div className="voice-stage">
              <div className="voice-call-card">
                <span className="voice-pulse"><Phone size={23} /></span>
                <span className="voice-call-status">INCOMING FARM TIP</span>
                <h4>Your farm tip is ready.</h4>
                <p>Short spoken guidance Â· sample voice card</p>
                <VoiceWaveform reduced={reduced} />
                <div className="voice-language"><span /> EKEGUSII AUDIO Â· REVIEW NEEDED</div>
              </div>
            </div>
            <p className="phone-option-foot">Short, spoken guidance for low-literacy users</p>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

function ModulesSection({ reduced }: { reduced: boolean }) {
  return (
    <section className="modules-section" id="modules">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="06 / EIGHT MODULES" title="One useful tool for every big challenge." description="Built around the real questions farmers ask through the season." /></Reveal>
        <div className="modules-grid">
          {moduleCards.map(({ title, tag, summary, benefit, icon: Icon }, index) => (
            <motion.article
              className="module-card"
              key={title}
              initial={{ opacity: 0, y: reduced ? 0 : 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.18 }}
              transition={{ duration: reduced ? 0.18 : 0.45, delay: reduced ? 0 : (index % 4) * 0.07 }}
              tabIndex={0}
            >
              <div className="module-card-inner">
                <div className="module-face module-front">
                  <span className="module-number">0{index + 1}</span>
                  <span className="module-icon"><Icon size={24} /></span>
                  <span className="module-tag">{tag}</span>
                  <h3>{title}</h3>
                  <p>{summary}</p>
                  <span className="module-hint">HOVER TO EXPLORE <ArrowUpRight size={14} /></span>
                </div>
                <div className="module-face module-back">
                  <span className="module-back-icon"><Icon size={24} /></span>
                  <span className="module-tag">FOR THE FARMER</span>
                  <h3>{title}</h3>
                  <p>{benefit}</p>
                  <Link to="/login" className="module-link">Try the demo <ArrowRight size={15} /></Link>
                </div>
              </div>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ImpactSection() {
  return (
    <section className="impact-section" id="impact">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="07 / A CLEAR VIEW" title="See what is happening across the county." description="A simple picture of reports, alerts and farmer activity â€” to help teams decide where support is needed." /></Reveal>
        <Reveal className="impact-dashboard">
          <div className="dashboard-topline"><div className="dash-logo"><Sprout size={18} /> SHAMBA / COUNTY VIEW</div><span className="sample-stamp">SAMPLE DATA Â· NOT LIVE</span></div>
          <div className="dashboard-head"><div><p>COUNTY SNAPSHOT</p><h3>Kisii County</h3></div><span className="dash-date">LAST 30 DAYS <ChevronDown size={14} /></span></div>
          <div className="impact-stats">
            <CountUp value={2400} suffix="+" label="farmers registered Â· sample" />
            <CountUp value={6} label="wards represented Â· sample" />
            <CountUp value={128} label="alerts shared Â· sample" />
            <CountUp value={82} suffix="%" label="reports reviewed Â· sample" />
          </div>
          <div className="dashboard-lower">
            <div className="activity-chart"><div className="dashboard-subhead"><strong>Farmer activity</strong><span>Reports & advice views</span></div><div className="bar-chart">{[35, 48, 42, 66, 54, 78, 61, 92, 69, 83, 56, 74].map((height, index) => <i key={index} style={{ '--height': `${height}%` } as CSSProperties} />)}</div><div className="chart-quarters"><span>WEEK 1</span><span>WEEK 2</span><span>WEEK 3</span><span>WEEK 4</span></div></div>
            <div className="ward-list"><div className="dashboard-subhead"><strong>Ward activity</strong><span>Example</span></div>{['Kisii Central', 'Nyamache', 'Bobasi', 'Marani'].map((ward, index) => <div className="ward-row" key={ward}><span>{ward}</span><i><b style={{ width: `${78 - index * 13}%` }} /></i><strong>{[72, 54, 41, 28][index]}</strong></div>)}</div>
          </div>
        </Reveal>
        <div className="impact-callout"><span><BarChart3 size={20} /></span><p><strong>Designed to support decisions, not replace them.</strong><br />County teams and farmer groups help turn signals into action on the ground.</p></div>
      </div>
    </section>
  )
}

function LimitsSection() {
  const provided = ['Local weather and market information', 'Useful alerts and practical next steps', 'Access through app, SMS and voice']
  const partners = ['County teams verify and act on reports', 'Cooperatives share local knowledge and reach', 'Dealers and buyers provide services and offers']
  return (
    <section className="limits-section">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="A PRACTICAL PARTNERSHIP" title="Useful by design. Honest about limits." description="Shamba Smart 360 connects farmers to timely information. People and local organisations make it real." /></Reveal>
        <div className="limits-grid">
          <Reveal className="limits-card">
            <span className="limits-kicker">WHAT SHAMBA DOES</span><h3>Information, in a farmerâ€™s hands.</h3>
            <ul>{provided.map((item) => <li key={item}><Check size={17} />{item}</li>)}</ul>
            <p className="limits-note">Forecasts are guidance, not guarantees. Pest suggestions are educational, never a diagnosis.</p>
          </Reveal>
          <Reveal className="limits-card limits-partners" delay={0.1}>
            <span className="limits-kicker">WHAT PARTNERS PROVIDE</span><h3>Local action, built together.</h3>
            <ul>{partners.map((item) => <li key={item}><Sprout size={17} />{item}</li>)}</ul>
            <p className="limits-note">Prices and example dashboard figures are sample data until verified locally.</p>
          </Reveal>
        </div>
      </div>
    </section>
  )
}

function ProblemSection({ reduced }: { reduced: boolean }) {
  return (
    <section className="problems-section" id="problem">
      <div className="landing-container">
        <Reveal><SectionHeading eyebrow="THE PROBLEM" title="Eight challenges. One season at a time." description="A farmer does not have one problem. They have a season full of connected decisions." /></Reveal>
        <div className="problems-scroll" role="list" aria-label="Eight farming challenges">
          {problems.map(({ tag, title, story, stat, icon: Icon, photo, alt }, index) => (
            <motion.article
              key={tag}
              className={`problem-card problem-card-${tag}`}
              role="listitem"
              initial={{ opacity: 0, x: reduced ? 0 : 24 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.25 }}
              transition={{ duration: reduced ? 0.18 : 0.5, delay: reduced ? 0 : (index % 4) * 0.08 }}
            >
              {photo && <AssetPicture name={photo} alt={alt ?? ''} className="problem-photo" />}
              <div className="problem-card-content">
                <span className="problem-icon"><Icon size={20} /></span>
                <span className="problem-card-number">0{index + 1}</span>
                <span className="problem-label">{tag}</span>
                <h3>{title}</h3>
                <p>{story}</p>
                <strong className="problem-stat">{stat}</strong>
              </div>
            </motion.article>
          ))}
        </div>
        <p className="scroll-cue"><ArrowDownRight size={16} /> Swipe to see all eight</p>
      </div>
    </section>
  )
}

function HowToUseFooter({ children }: { children: ReactNode }) {
  return <>{children}</>
}

export function LandingPage() {
  const reduceMotion = useMotionReducedMotion() ?? false
  const heroRef = useRef<HTMLElement>(null)
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] })
  const heroY = useTransform(scrollYProgress, [0, 1], [0, reduceMotion ? 0 : 120])
  const heroScale = useTransform(scrollYProgress, [0, 1], [1, reduceMotion ? 1 : 1.1])
  const heroShade = useTransform(scrollYProgress, [0, 1], [0, 0.25])
  const heroOverlayOpacity = useTransform(heroShade, (value) => 1 - value * 0.25)
  const [activeSection, setActiveSection] = useState('home')
  const [menuOpen, setMenuOpen] = useState(false)
  const { language } = useI18n()

  useEffect(() => {
    const observers: IntersectionObserver[] = []
    sections.forEach(([id]) => {
      const element = document.getElementById(id)
      if (!element) return
      const observer = new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting) setActiveSection(id)
      }, { rootMargin: '-35% 0px -55% 0px', threshold: 0 })
      observer.observe(element)
      observers.push(observer)
    })
    return () => observers.forEach((observer) => observer.disconnect())
  }, [])

  const scrollTo = (id: string) => {
    setMenuOpen(false)
    document.getElementById(id)?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth' })
  }

  return (
    <HowToUseFooter>
      <div className="landing-site">
        <header className="landing-nav">
          <a className="landing-brand" href="#home" onClick={() => scrollTo('home')}>
            <span className="landing-brand-mark"><Sprout size={22} /></span>
            <span><strong>SHAMBA</strong><small>SMART 360</small></span>
          </a>
          <nav className={`landing-links ${menuOpen ? 'links-open' : ''}`} aria-label="Main">
            {sections.slice(1, 7).map(([id, label]) => <button key={id} className={activeSection === id ? 'nav-active' : ''} onClick={() => scrollTo(id)}>{label}</button>)}
            <div className="landing-mobile-actions"><LanguageSwitcher /><Link to="/login" className="landing-cta">Try the demo <ArrowUpRight size={15} /></Link></div>
          </nav>
          <div className="landing-nav-actions">
            <div className="landing-language"><LanguageSwitcher />{language === 'guz' && <small>Needs native-speaker review</small>}</div>
            <Link to="/login" className="landing-cta">Try the demo <ArrowUpRight size={15} /></Link>
          </div>
          <button className="landing-menu-toggle" aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
            {menuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
        </header>

        <main>
          <section className="hero-section" id="home" ref={heroRef}>
            <motion.div className="hero-image-layer" style={reduceMotion ? undefined : { y: heroY, scale: heroScale }}>
              <AssetPicture name="hero-coffee" alt="Ripe red coffee cherries growing on a branch in Kisii" eager />
            </motion.div>
            <motion.div className="hero-overlay" style={reduceMotion ? undefined : { opacity: heroOverlayOpacity }} />
            <div className="hero-content">
              <motion.div
                className="hero-copy"
                initial={{ opacity: 0, y: reduceMotion ? 0 : 25 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: reduceMotion ? 0.15 : 0.8, delay: reduceMotion ? 0 : 0.2 }}
              >
                <p className="hero-kicker"><span /> FARM ADVICE, REIMAGINED <span className="kicker-line" /></p>
                <h1>The right advice,<br />at the right time,<br /><em>in your own language.</em></h1>
                <p className="hero-subline">Weather, crops, pests and markets â€” one trusted guide for every farm in Kisii County.</p>
                <div className="hero-actions">
                  <Link to="/login" className="landing-button landing-button-red">Open the app <ArrowUpRight size={18} /></Link>
                  <button className="landing-button landing-button-glass" onClick={() => scrollTo('any-phone')}><Phone size={17} /> See it on a basic phone</button>
                </div>
                <div className="hero-note"><span className="hero-note-dot" /> Built for farmers. Designed for any phone.</div>
              </motion.div>
              <div className="hero-notifications" aria-label="Example farm alerts">
                {[
                  { icon: CloudRain, title: 'Rain in 2 hours', note: 'Kisii Central Â· Plan ahead', kind: 'rain' },
                  { icon: Bug, title: 'Armyworm reported', note: 'Nyamache Â· 3 farms nearby', kind: 'pest' },
                  { icon: TrendingUp, title: 'Maize price up 18%', note: 'Kisii market Â· This week', kind: 'price' },
                ].map(({ icon: Icon, title, note, kind }, index) => (
                  <motion.div
                    className={`hero-float-card float-${kind}`}
                    key={title}
                    initial={{ opacity: 0, x: reduceMotion ? 0 : 25 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: reduceMotion ? 0.15 : 0.6, delay: reduceMotion ? 0 : 0.7 + index * 0.17 }}
                  >
                    <span className={`float-icon float-icon-${kind}`}><Icon size={17} /></span>
                    <span><strong>{title}</strong><small>{note}</small></span>
                    <ArrowUpRight size={15} className="float-arrow" />
                  </motion.div>
                ))}
              </div>
            </div>
            <div className="hero-bottom">
              <span className="hero-location"><MapPin size={15} /> KISII COUNTY, KENYA</span>
              <button onClick={() => scrollTo('problem')} className="hero-scroll">DISCOVER SHAMBA <ArrowDown size={15} /></button>
              <span className="hero-index">01 â€” 08</span>
            </div>
            <div className="hero-counts" aria-label="Shamba overview">
              <CountUp value={8} label="problems solved" />
              <CountUp value={3} label="languages" />
              <div className="count-item"><span className="count-number">0</span><span className="count-label">app data needed*</span></div>
              <small>*USSD and voice work without mobile data. Carrier charges may apply.</small>
            </div>
          </section>

          <ProblemSection reduced={reduceMotion} />
          <ClimateScene reduced={reduceMotion} />
          <ErosionSection reduced={reduceMotion} />
          <PestSection reduced={reduceMotion} />
          <HowItWorks reduced={reduceMotion} />
          <PhoneSection reduced={reduceMotion} />
          <ModulesSection reduced={reduceMotion} />
          <ImpactSection />
          <LimitsSection />

          <section className="final-cta">

            <div className="final-cta-content">
              <p className="landing-eyebrow">YOUR FARM. YOUR LANGUAGE. YOUR NEXT STEP.</p>
              <h2>Letâ€™s grow the next season,<br /><em>together.</em></h2>
              <p>One clear answer can change what happens next.</p>
              <Link to="/login" className="landing-button landing-button-red">Try the demo <ArrowUpRight size={18} /></Link>
              <span className="final-contact"><Phone size={14} /> Start on a smartphone, basic phone, or voice call</span>
            </div>
          </section>
        </main>

        <footer className="landing-footer">
          <div className="footer-top">
            <a className="landing-brand footer-brand" href="#home" onClick={() => scrollTo('home')}>
              <span className="landing-brand-mark"><Sprout size={21} /></span><span><strong>SHAMBA</strong><small>SMART 360</small></span>
            </a>
            <p>Practical farm advice for the people who grow our future.</p>
            <div className="footer-links"><a href="#problem" onClick={(event) => { event.preventDefault(); scrollTo('problem') }}>Our approach</a><a href="#modules" onClick={(event) => { event.preventDefault(); scrollTo('modules') }}>Explore modules</a><Link to="/login">Open the app <ArrowUpRight size={14} /></Link></div>
          </div>
          <div className="footer-bottom"><span>Â© {new Date().getFullYear()} Shamba Smart 360</span><span>Designed with Kisii County farmers in mind.</span><span className="footer-data">SAMPLE DATA IS LABELLED Â· ADVICE IS NOT A DIAGNOSIS</span></div>
        </footer>

        <nav className="section-progress" aria-label="Page sections">
          {sections.map(([id, label], index) => (
            <button key={id} onClick={() => scrollTo(id)} className={activeSection === id ? 'progress-active' : ''} aria-label={`Go to ${label}`} aria-current={activeSection === id ? 'location' : undefined}>
              <span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
            </button>
          ))}
        </nav>
      </div>
    </HowToUseFooter>
  )
}
