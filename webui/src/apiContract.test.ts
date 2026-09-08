import { afterEach, describe, expect, it, vi } from 'vitest'
import contract from '../../contracts/webui-critical-api.json'
import { api } from './api'

type CriticalOperation = {
  id: string
  method: string
  client: {
    method: keyof typeof api
    args: unknown[]
    path: string
  }
}

const operations = contract.operations as CriticalOperation[]

afterEach(() => {
  vi.unstubAllGlobals()
})

describe.each(operations)('$id', (operation) => {
  it('keeps the WebUI request aligned with the critical API contract', async () => {
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) =>
        new Response('{}', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const clientMethod = api[operation.client.method] as unknown as (
      ...args: unknown[]
    ) => Promise<unknown>
    await clientMethod(...operation.client.args)

    expect(fetchMock).toHaveBeenCalledOnce()
    const [input, init] = fetchMock.mock.calls[0]
    expect(new URL(String(input)).pathname).toBe(
      `${contract.base_path}${operation.client.path}`,
    )
    expect((init?.method ?? 'GET').toUpperCase()).toBe(operation.method)
  })
})
