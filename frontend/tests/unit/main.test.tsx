import { expect, it, vi } from 'vitest'

it('mounts the app in React StrictMode at the root element', async () => {
  const render = vi.fn()
  const createRoot = vi.fn(() => ({ render }))
  vi.doMock('react-dom/client', () => ({ createRoot }))
  document.body.innerHTML = '<div id="root"></div>'
  await import('../../src/main')
  expect(createRoot).toHaveBeenCalledWith(document.getElementById('root'))
  expect(render).toHaveBeenCalledOnce()
  expect(render.mock.calls[0][0].props.children).toBeDefined()
  vi.doUnmock('react-dom/client')
})
