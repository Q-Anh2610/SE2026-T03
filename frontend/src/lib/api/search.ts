import { isHttpUrl, parseResponse, validateRequest } from '../../features/search/contract'
import type { MockScenario, SearchClient } from '../../features/search/types'

export const isMockMode = import.meta.env.DEV && import.meta.env.MODE !== 'api'
  && import.meta.env.VITE_SEARCH_MODE !== 'api'

export function createHttpSearchClient(baseUrl = ''): SearchClient {
  return {
    async search(input, signal) {
      const request = validateRequest(input)
      if (baseUrl) {
        if (!isHttpUrl(baseUrl)) throw new Error('Địa chỉ API không hợp lệ. Hãy kiểm tra cấu hình frontend.')
        const parsed = new URL(baseUrl)
        if (parsed.pathname !== '/' || parsed.search || parsed.hash) {
          throw new Error('Địa chỉ API phải là origin HTTP(S), không có đường dẫn hoặc tham số.')
        }
      }
      let response: Response
      try {
        response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/v1/search/text`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
          signal: AbortSignal.any([signal, AbortSignal.timeout(15000)]),
        })
      } catch (error) {
        if (signal.aborted) throw error
        throw new Error('Không kết nối được dịch vụ tìm kiếm. Kiểm tra kết nối rồi thử lại.', { cause: error })
      }
      if (!response.ok) {
        throw new Error(response.status === 400 || response.status === 422
          ? 'Yêu cầu tìm kiếm không hợp lệ. Kiểm tra nội dung và bộ lọc.'
          : response.status === 404
            ? 'Không tìm thấy dịch vụ tìm kiếm. Kiểm tra địa chỉ API.'
            : 'Dịch vụ tìm kiếm chưa sẵn sàng. Hãy thử lại sau.')
      }
      let payload: unknown
      try {
        payload = await response.json()
      } catch (error) {
        throw new Error('API trả về dữ liệu không hợp lệ. Hãy kiểm tra cấu hình dịch vụ.', { cause: error })
      }
      return parseResponse(payload, request)
    },
  }
}

export async function getSearchClient(scenario: MockScenario): Promise<SearchClient> {
  if (isMockMode) {
    const { createMockSearchClient } = await import('../../features/search/mock')
    return createMockSearchClient(scenario)
  }
  return createHttpSearchClient(import.meta.env.VITE_API_BASE_URL ?? '')
}
