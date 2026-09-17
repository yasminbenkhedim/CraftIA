import { Job } from './job.model';

/**
 * Pure derivations from a Job, shared by the card that displays them and the pages that
 * search and sort on them.
 *
 * These were duplicated in the dashboard and the Library. That mattered more than the
 * usual copy-paste objection: the Library filters on the same title the card renders, so
 * a divergence would make search silently miss items that are visibly on screen.
 */

/**
 * The server-generated title when there is one.
 *
 * The rest is the fallback for jobs created before titles existed: a storyboard job
 * carries JSON in `prompt` rather than prose, so the raw string is unusable as a name.
 */
export function jobTitle(job: Job): string {
  if (job.title) return job.title;
  const prompt = (job.prompt || '').trim();
  if (!prompt) return `Job ${job.id.substring(0, 8)}`;
  if (prompt.startsWith('{')) {
    try {
      const parsed = JSON.parse(prompt);
      if (parsed?.title) return String(parsed.title).slice(0, 60);
    } catch {
      /* fall through to the word trim */
    }
  }
  const words = prompt.split(/\s+/).slice(0, 6).join(' ');
  return words.length < prompt.length ? words + '…' : words;
}

/**
 * Readable prompt text.
 *
 * `unwrapStoryboard` is what separates the two callers: the Library unpacks a storyboard
 * job's JSON because a wall of braces is useless when browsing, while the dashboard shows
 * it raw — which is what it has always shown, and what you want while debugging a run.
 */
export function jobPromptText(job: Job, unwrapStoryboard = false): string {
  const prompt = (job.prompt || '').trim();
  if (!unwrapStoryboard || !prompt.startsWith('{')) return prompt;
  try {
    const parsed = JSON.parse(prompt);
    return String(parsed?.title || parsed?.prompt || prompt);
  } catch {
    return prompt;
  }
}

/**
 * A job that finished but whose file storage retention has since removed.
 *
 * The `=== false` on artifact_available is deliberate: an older backend that does not send
 * the field leaves it undefined, and treating undefined as "gone" would hide every working
 * download button behind an Expired label.
 */
export function jobIsExpired(job: Job): boolean {
  if (job.status !== 'COMPLETED') return false;
  return job.artifact_expired === true || job.artifact_available === false;
}

/** The API sends naive UTC timestamps; `new Date()` alone would read them as local. */
export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
  const d = new Date(hasZone ? value : `${value}Z`);
  return isNaN(d.getTime()) ? null : d;
}

export function jobCreatedAt(job: Job): Date | null {
  return parseApiDate(job.created_at);
}

/** " on 05/09/2026", or "" when the job never expired. Reads as a clause, not a field. */
export function jobExpiredOn(job: Job): string {
  const d = parseApiDate(job.artifact_expired_at);
  return d ? ` on ${d.toLocaleDateString()}` : '';
}
