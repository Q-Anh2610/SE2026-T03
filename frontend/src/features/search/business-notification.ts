export const MAX_NOTIFICATION_TITLE_LENGTH = 120
export const MAX_NOTIFICATION_BODY_LENGTH = 240

/** Deliver a best-effort notification without requesting permission or leaking browser errors. */
export function notifyBusinessEvent(title: string, body: string): boolean {
  try {
    if (!title || exceedsCharacterLimit(title, MAX_NOTIFICATION_TITLE_LENGTH)
      || typeof Notification === 'undefined' || Notification.permission !== 'granted') return false

    new Notification(title, { body: takeCharacters(body, MAX_NOTIFICATION_BODY_LENGTH) })
    return true
  } catch {
    return false
  }
}

function exceedsCharacterLimit(value: string, limit: number): boolean {
  let count = 0
  const characters = value[Symbol.iterator]()
  while (count <= limit && !characters.next().done) {
    count += 1
  }
  return count > limit
}

function takeCharacters(value: string, limit: number): string {
  let result = ''
  let count = 0
  for (const character of value) {
    if (count === limit) break
    result += character
    count += 1
  }
  return result
}
