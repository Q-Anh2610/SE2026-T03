import {
  parseAssetDetailResponse,
  parseAssetListResponse,
  parseResponse,
  validateAssetId,
  validateListQuery,
  validateRequest,
} from '../../features/search/contract'
import type { AssetClient, MockScenario, SearchClient } from '../../features/search/types'
import { apiUrl, getJson, REQUEST_TIMEOUT_MS } from './http'

export { ApiError, type ApiErrorKind } from './http'

export const isMockMode = import.meta.env.DEV && import.meta.env.MODE !== 'api'
  && import.meta.env.VITE_SEARCH_MODE !== 'api'

const assetListMessages = {
  network: 'Không kết nối được dịch vụ asset. Kiểm tra kết nối rồi thử lại.',
  invalid: 'Yêu cầu danh sách asset không hợp lệ. Kiểm tra trang và bộ lọc.',
  notFound: 'Không tìm thấy dịch vụ asset. Kiểm tra địa chỉ API.',
  routeNotFound: 'Không tìm thấy dịch vụ asset. Kiểm tra địa chỉ API.',
  unavailable: 'Dịch vụ asset chưa sẵn sàng. Hãy thử lại sau.',
  contract: 'API trả về dữ liệu không hợp lệ. Hãy kiểm tra cấu hình dịch vụ.',
}

const assetDetailMessages = {
  network: 'Không kết nối được dịch vụ asset. Kiểm tra kết nối rồi thử lại.',
  invalid: 'Mã asset không hợp lệ.',
  notFound: 'Không tìm thấy asset trong thư viện.',
  routeNotFound: 'Không tìm thấy dịch vụ asset. Kiểm tra địa chỉ API.',
  unavailable: 'Dịch vụ asset chưa sẵn sàng. Hãy thử lại sau.',
  contract: 'API trả về dữ liệu không hợp lệ. Hãy kiểm tra cấu hình dịch vụ.',
}

export function createHttpSearchClient(baseUrl = ''): SearchClient {
  return {
    async search(input, signal) {
      const request = validateRequest(input)
      const url = apiUrl(baseUrl, '/api/v1/search/text')
      let response: Response
      try {
        response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
          signal: AbortSignal.any([signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]),
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

export function createHttpAssetClient(baseUrl = ''): AssetClient {
  return {
    async listAssets(input, signal) {
      const query = validateListQuery(input)
      const params = new URLSearchParams({
        page: String(query.page),
        limit: String(query.limit),
      })
      for (const [key, value] of Object.entries(query.filters)) {
        if (value !== undefined && value !== null) params.set(key, String(value))
      }
      const url = apiUrl(baseUrl, `/api/v1/assets?${params.toString()}`)
      const payload = await getJson(url, signal, assetListMessages)
      return parseAssetListResponse(payload, query)
    },
    async getAsset(assetId, signal) {
      const normalizedId = validateAssetId(assetId)
      const url = apiUrl(baseUrl, `/api/v1/assets/${encodeURIComponent(normalizedId)}`)
      const payload = await getJson(url, signal, assetDetailMessages, ['ASSET_NOT_FOUND'])
      return parseAssetDetailResponse(payload, normalizedId)
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

export async function getAssetClient(scenario: MockScenario = 'success'): Promise<AssetClient> {
  if (isMockMode) {
    const { createMockAssetClient } = await import('../../features/search/mock')
    return createMockAssetClient(scenario)
  }
  return createHttpAssetClient(import.meta.env.VITE_API_BASE_URL ?? '')
}
