import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { SiteFooter } from './SiteFooter'

describe('SiteFooter', () => {
  it('shows only the brand, introduction and back-to-top link', () => {
    render(<SiteFooter />)

    const footer = screen.getByRole('contentinfo')
    expect(within(footer).getByText('Connected')).toBeVisible()
    expect(within(footer).getByText('Không gian cho ý tưởng tiếp theo.')).toBeVisible()
    expect(footer).toHaveTextContent(/^ConnectedKhông gian cho ý tưởng tiếp theo\.Trở về đầu trang$/)
    expect(within(footer).getAllByRole('link')).toHaveLength(1)
  })

  it('links back to the main content', () => {
    render(<SiteFooter />)

    expect(screen.getByRole('link', { name: 'Trở về đầu trang' })).toHaveAttribute('href', '#main')
  })

  it('allows keyboard users to reach and activate the link', async () => {
    const user = userEvent.setup()
    render(<SiteFooter />)
    const link = screen.getByRole('link', { name: 'Trở về đầu trang' })
    let activated = false
    link.addEventListener('click', (event) => {
      event.preventDefault()
      activated = true
    })

    await user.tab()
    expect(link).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(activated).toBe(true)
  })
})
