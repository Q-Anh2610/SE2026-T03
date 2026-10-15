import { useEffect, useRef } from 'react'

export function SearchBackdrop() {
  const backdrop = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = backdrop.current
    if (!element) return
    const motion = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let frame = 0

    function update() {
      frame = 0
      const offset = motion?.matches ? 0 : Math.min(Math.max(window.scrollY, 0), window.innerHeight) * .12
      element!.style.setProperty('--hero-shift', `${offset}px`)
    }

    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(update)
    }

    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    motion?.addEventListener?.('change', update)
    const observer = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(([entry]) => {
      element.dataset.visible = String(entry.isIntersecting)
    })
    observer?.observe(element)
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      motion?.removeEventListener?.('change', update)
      observer?.disconnect()
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  return (
    <div ref={backdrop} className="hero-backdrop" aria-hidden="true">
      <img className="hero-landscape" src={`${import.meta.env.BASE_URL}images/discovery/alpine-lake-hero.webp`}
        alt="" fetchPriority="high" decoding="async" />
      <div className="hero-water-light" />
    </div>
  )
}
