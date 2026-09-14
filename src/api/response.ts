export type ApiPayload<T> = T | { data: T; success?: boolean };

// Legacy endpoints return the value directly; current endpoints use api_success.
export function unwrapApiData<T>(payload: ApiPayload<T>): T {
  if (payload && typeof payload === 'object' && 'success' in payload && payload.success === false) {
    throw new Error('服务未能完成请求，请重试');
  }
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data;
  }
  return payload as T;
}

export function unwrapApiList<T>(payload: ApiPayload<T[]>): T[] {
  const data = unwrapApiData(payload);
  if (!Array.isArray(data)) throw new Error('列表数据格式异常，请重试');
  return data;
}
