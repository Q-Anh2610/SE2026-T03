import { act, fireEvent, render } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SearchBackdrop } from './SearchBackdrop'

function setupMotion(reduced = false) {
  const motion = { matches: reduced, addEventListener: vi.fn(), removeEventListener: vi.fn() }
  vi.stubGlobal('matchMedia', vi.fn(() => motion))
  const frames: FrameRequestCallback[] = []
  const request = vi.fn((callback: FrameRequestCallback) => { frames.push(callback); return frames.length })
  vi.stubGlobal('requestAnimationFrame', request)
  const cancel = vi.fn()
  vi.stubGlobal('cancelAnimationFrame', cancel)
  vi.stubGlobal('scrollY', 0)
  return { motion, frames, request, cancel }
}

describe('landscape motion lifecycle', () => {
  it('batches scroll events, clamps the offset and cancels pending work on unmount', () => {
    const { frames, request, cancel } = setupMotion()
    const { container, unmount } = render(<SearchBackdrop />)
    const background = container.firstElementChild as HTMLElement
    expect(background.style.getPropertyValue('--hero-shift')).toBe('0px')
    vi.stubGlobal('scrollY', 200)
    fireEvent.scroll(window)
    fireEvent.scroll(window)
    expect(request).toHaveBeenCalledTimes(1)
    act(() => frames[0](0))
    expect(background.style.getPropertyValue('--hero-shift')).toBe('24px')
    vi.stubGlobal('scrollY', -100)
    fireEvent.scroll(window)
    act(() => frames[1](0))
    expect(background.style.getPropertyValue('--hero-shift')).toBe('0px')
    vi.stubGlobal('scrollY', window.innerHeight * 2)
    fireEvent.resize(window)
    act(() => frames[2](0))
    expect(background.style.getPropertyValue('--hero-shift')).toBe(`${window.innerHeight * .12}px`)
    fireEvent.scroll(window)
    unmount()
    expect(cancel).toHaveBeenCalledWith(4)
    fireEvent.scroll(window)
    expect(request).toHaveBeenCalledTimes(4)
  })

  it('reacts to reduced motion changes and removes its subscription', () => {
    const { motion } = setupMotion(true)
    vi.stubGlobal('scrollY', 200)
    const { container, unmount } = render(<SearchBackdrop />)
    const background = container.firstElementChild as HTMLElement
    const update = motion.addEventListener.mock.calls[0][1] as () => void
    expect(background.style.getPropertyValue('--hero-shift')).toBe('0px')
    motion.matches = false
    act(update)
    expect(background.style.getPropertyValue('--hero-shift')).toBe('24px')
    unmount()
    expect(motion.removeEventListener).toHaveBeenCalledWith('change', update)
  })

  it('pauses offscreen animation and disconnects its observer', () => {
    setupMotion()
    let notify!: IntersectionObserverCallback
    const observe = vi.fn()
    const disconnect = vi.fn()
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: IntersectionObserverCallback) { notify = callback }
      observe = observe
      disconnect = disconnect
    })
    const { container, unmount } = render(<SearchBackdrop />)
    const background = container.firstElementChild as HTMLElement
    expect(observe).toHaveBeenCalledWith(background)
    act(() => notify([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver))
    expect(background.dataset.visible).toBe('false')
    act(() => notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver))
    expect(background.dataset.visible).toBe('true')
    unmount()
    expect(disconnect).toHaveBeenCalledOnce()
  })

  it('works without optional media and observer browser APIs', () => {
    setupMotion()
    vi.stubGlobal('matchMedia', undefined)
    vi.stubGlobal('IntersectionObserver', undefined)
    const { unmount } = render(<SearchBackdrop />)
    unmount()
    vi.stubGlobal('matchMedia', () => ({ matches: false }))
    const second = render(<SearchBackdrop />)
    second.unmount()
  })
})
