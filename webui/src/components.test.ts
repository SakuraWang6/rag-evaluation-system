import { describe, expect, it } from 'vitest'
import { errorRemediation } from './components'

describe('error remediation', () => {
  it('describes target discovery failures as an authoring operation, not a platform outage', () => {
    const result = errorRemediation(
      'Failed to fetch (http://127.0.0.1:8765/api/v1/authoring/datasets/example/targets/discover)',
    )

    expect(result.title).toBe('error.targetDiscoveryTitle')
    expect(result.action).toBe('error.targetDiscoveryAction')
  })
})
