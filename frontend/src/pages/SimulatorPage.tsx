import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'
const USSD_URL = `${API_BASE.replace(/\/+$/, '')}/ussd/`

function createPhone() {
  return `+2547${Math.floor(10000000 + Math.random() * 89999999)}`
}

function createSessionId() {
  return `SIM-${Math.random().toString(36).slice(2, 10).toUpperCase()}`
}

export function SimulatorPage() {
  const [phone] = useState(createPhone)
  const [sessionId, setSessionId] = useState(createSessionId)
  const [input, setInput] = useState('')
  const [sequence, setSequence] = useState('')
  const [screenText, setScreenText] = useState('Dial *384# to start')
  const [active, setActive] = useState(false)
  const [ended, setEnded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const requestUssd = async (text: string) => {
    setLoading(true)
    setError('')
    try {
      const body = new URLSearchParams({
        sessionId,
        phoneNumber: phone,
        networkCode: '63902',
        serviceCode: '*384#',
        text,
      })
      const response = await fetch(USSD_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: body.toString(),
      })
      const raw = await response.text()
      if (!response.ok) throw new Error(raw || `Request failed (${response.status}).`)
      const isEnd = raw.startsWith('END ')
      setScreenText(raw.replace(/^(CON |END )/, ''))
      setEnded(isEnd)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'USSD request failed.')
    } finally {
      setLoading(false)
    }
  }

  const dial = () => {
    setActive(true)
    setSequence('')
    setInput('')
    void requestUssd('')
  }

  const submitOption = () => {
    if (!active || ended || !input.trim()) return
    const nextSequence = sequence ? `${sequence}*${input.trim()}` : input.trim()
    setSequence(nextSequence)
    setInput('')
    void requestUssd(nextSequence)
  }

  const reset = () => {
    setSessionId(createSessionId())
    setInput('')
    setSequence('')
    setScreenText('Dial *384# to start')
    setActive(false)
    setEnded(false)
    setError('')
  }

  return (
    <main className="min-h-screen bg-[var(--paper)] px-4 py-8 text-[var(--soil)]">
      <section className="mx-auto grid w-full max-w-xl gap-5">
        <header>
          <p className="font-mono text-xs font-medium tracking-widest text-[var(--leaf)]">BASIC PHONE DEMO</p>
          <h1 className="mt-2 font-display text-4xl text-[var(--forest)]">USSD simulator</h1>
          <p className="mt-2 text-sm leading-6 text-stone-700">Try the Shamba Smart 360 menu with the same request flow used by the USSD callback.</p>
        </header>
        <section className="rounded-2xl border border-stone-300 bg-white p-5 shadow-sm">
          <div className="mb-3 flex justify-between gap-3 font-mono text-xs text-stone-600">
            <span>{phone}</span>
            <span>*384#</span>
          </div>
          <div className="min-h-56 rounded-lg border border-[var(--leaf)] bg-[#101710] p-4 font-mono text-sm leading-6 text-[#b8e4a0]" aria-live="polite">
            <pre className="whitespace-pre-wrap">{screenText}</pre>
            {loading && <p className="mt-2 text-xs text-[#b8e4a0]">Connecting...</p>}
          </div>
          {error && <p className="mt-3 text-sm text-[var(--cherry-deep)]" role="alert">{error}</p>}
          <form className="mt-4 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); submitOption() }}>
            {!active ? (
              <button className="min-h-12 flex-1 rounded-lg bg-[var(--forest)] px-4 font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--leaf)]" type="button" disabled={loading} onClick={dial}>Dial *384#</button>
            ) : (
              <>
                <label className="sr-only" htmlFor="ussd-choice">Menu choice</label>
                <input id="ussd-choice" className="min-h-12 min-w-0 flex-1 rounded-lg border border-stone-400 px-3 font-mono focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--leaf)]" value={input} onChange={(event) => setInput(event.target.value)} disabled={loading || ended} placeholder="Enter menu choice" />
                <button className="min-h-12 rounded-lg bg-[var(--forest)] px-5 font-semibold text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--leaf)]" type="submit" disabled={loading || ended || !input.trim()}>Send</button>
              </>
            )}
            <button className="min-h-12 rounded-lg border border-stone-400 px-4 font-semibold text-[var(--soil)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--leaf)]" type="button" onClick={reset}>Reset</button>
          </form>
          {ended && <p className="mt-3 text-center text-xs text-stone-600">Session ended. Reset to start again.</p>}
        </section>
      </section>
    </main>
  )
}
