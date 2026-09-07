import type { AuthoringDataset, AuthoringDiscoveryJob, AuthoringGenerationJob } from './types'

const terminalAuthoringStates = new Set(['registered', 'formal_released', 'archived', 'deleted'])

/** The private provenance record must never reopen as a product-flow draft. */
export function latestResumableAuthoringDataset(
  datasets: AuthoringDataset[],
): AuthoringDataset | null {
  return datasets
    .filter((item) => !terminalAuthoringStates.has(item.state) && !(item.formal_release_ids?.length))
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at))[0] ?? null
}

/** Prefer live work, otherwise retain the newest completed job's diagnostics. */
export function visibleGenerationJob(
  jobs: AuthoringGenerationJob[],
): AuthoringGenerationJob | null {
  return jobs.find((job) => job.state === 'queued' || job.state === 'running') ?? jobs[0] ?? null
}

/** Prefer live source discovery, otherwise retain the newest job diagnostic. */
export function visibleDiscoveryJob(
  jobs: AuthoringDiscoveryJob[],
): AuthoringDiscoveryJob | null {
  return jobs.find((job) => job.state === 'queued' || job.state === 'running') ?? jobs[0] ?? null
}

export function generationJobProgress(job: AuthoringGenerationJob | null): {
  completed: number
  succeeded: number
  failed: number
  total: number
} {
  if (!job) return { completed: 0, succeeded: 0, failed: 0, total: 0 }
  const succeeded = job.items.filter((item) => item.state === 'succeeded').length
  const failed = job.items.filter((item) => item.state === 'failed').length
  const cancelled = job.items.filter((item) => item.state === 'cancelled').length
  return { completed: succeeded + failed + cancelled, succeeded, failed, total: job.items.length }
}
