export const MAX_NOTIFICATION_TITLE_LENGTH = 120
export const MAX_NOTIFICATION_BODY_LENGTH = 240

/** Deliver a best-effort notification without requesting permission or leaking browser errors. */
export function notifyBusinessEvent(title: string, body: string): boolean {
  try {
    if (!title || title.length > MAX_NOTIFICATION_TITLE_LENGTH
      || typeof Notification === 'undefined' || Notification.permission !== 'granted') return false

    new Notification(title, { body: body.slice(0, MAX_NOTIFICATION_BODY_LENGTH) })
    return true
  } catch {
    return false
  }
}
