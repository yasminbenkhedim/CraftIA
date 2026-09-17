import { Job } from './job.model';

/**
 * Percentage coercion shared by every view that renders a progress bar.
 *
 * A null/absent percentage must be neutralised at ingest, not just at render time. In the
 * job detail view it feeds an easing loop where `displayProgress += NaN` latches the value
 * to NaN permanently -- every later frame computes `valid - NaN`, which is NaN again, so
 * the bar never recovers once real progress arrives and the loop's exit test never passes.
 */
export function toPercent(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return 0;
  }
  return Math.min(100, Math.max(0, n));
}

/** The job's percentage as a whole number, 0 when the server has not reported one yet. */
export function jobPercent(job: Job | null | undefined): number {
  if (!job) {
    return 0;
  }
  return Math.round(toPercent(job.progress ?? job.progress_percent));
}

/**
 * Label shown under the bar. A queued job that has not started reads "Queued..." rather
 * than whatever placeholder step the row was created with.
 */
export function jobStageLabel(job: Job | null | undefined): string {
  if (!job) {
    return 'Queued...';
  }
  const status = (job.status || '').toUpperCase();
  if ((status === 'QUEUED' || status === 'PENDING') && jobPercent(job) === 0) {
    return 'Queued...';
  }
  return job.stage_label || job.current_step || 'Queued...';
}
