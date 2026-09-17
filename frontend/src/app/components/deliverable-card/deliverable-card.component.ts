import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Job } from '../../models/job.model';
import { jobPercent, jobStageLabel } from '../../models/progress.util';
import { jobCreatedAt, jobExpiredOn, jobIsExpired, jobPromptText, jobTitle } from '../../models/job.util';
import { JobService } from '../../services/job.service';

/**
 * The deliverable card, shared by the dashboard and the Library.
 *
 * Both pages show the same object — one job, one thumbnail, one set of badges — but for
 * different reasons, so the differences are expressed as a `variant` rather than by
 * forking the markup:
 *
 *   'run'   (dashboard) — a job as a PROCESS. Carries the live status badge, the running
 *                         spinner, the failure overlay, the progress block and the scrub
 *                         bar. Every status appears here, so the card must render all of
 *                         them.
 *   'asset' (library)   — a job as a DELIVERABLE. Only completed work reaches it, so the
 *                         status badge is noise; expiry and re-running are what matter.
 *
 * One `variant` input beats a handful of booleans: the two modes are coherent wholes, and
 * a caller cannot accidentally assemble a nonsensical combination like a progress bar on
 * an expired card. Interactive state (a re-run in flight, a spent credit balance) stays as
 * separate inputs because it is genuinely per-card and changes over time.
 *
 * Thumbnail load/error state lives here rather than in the pages. It is presentation
 * bookkeeping — which posters decoded, which 404'd and must not be retried — and both
 * pages previously kept their own duplicate copies of it.
 */
@Component({
  selector: 'app-deliverable-card',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <article class="card" [ngClass]="'card-' + job.status.toLowerCase()" [class.card-dim]="dimWhenExpired && isExpired">

      <a class="thumb" [ngClass]="'thumb-' + thumbTone" [routerLink]="['/jobs', job.id]">
        <!-- The gradient underneath stays visible until (or unless) this loads. -->
        <img
          *ngIf="thumbnailSrc as src"
          class="thumb-img"
          [src]="src"
          [alt]="'Preview frame from ' + title"
          loading="lazy"
          decoding="async"
          (load)="onThumbLoad()"
          (error)="onThumbError()"
          [class.loaded]="thumbLoaded" />

        <span class="thumb-lines" *ngIf="!thumbLoaded" aria-hidden="true"></span>
        <span class="thumb-wash" *ngIf="!thumbLoaded" aria-hidden="true"></span>
        <span class="thumb-scrim" aria-hidden="true"></span>

        <span class="thumb-badges">
          <span class="cf-tag" [ngClass]="'cf-tag-' + thumbTone">{{ typeLabel }}</span>

          <!-- Process view: always show where the job stands. -->
          <span
            *ngIf="variant === 'run'"
            class="cf-tag cf-tag-dot"
            [ngClass]="'cf-tag-' + (isExpired ? 'expired' : job.status.toLowerCase())"
          >{{ isExpired ? 'EXPIRED' : job.status }}</span>

          <!-- Asset view: everything here is COMPLETED, so only expiry is worth saying. -->
          <span *ngIf="variant === 'asset' && isExpired" class="cf-tag cf-tag-dot cf-tag-expired">EXPIRED</span>
        </span>

        <span class="thumb-slug mono">JOB-{{ job.id.substring(0, 8) }}</span>

        <span class="thumb-state" *ngIf="variant === 'run' && isRunning" aria-hidden="true">
          <span class="thumb-spin"></span>
          <span class="cf-sheen"><span></span></span>
        </span>

        <span class="thumb-state thumb-state-failed" *ngIf="variant === 'run' && job.status === 'FAILED'" aria-hidden="true">
          <span class="thumb-bang">!</span>
        </span>

        <!-- The source file is gone, so there is no frame left to extract: the
             placeholder is the honest representation, not a missing image. -->
        <span class="thumb-state thumb-state-expired" *ngIf="isExpired" aria-hidden="true">
          <span class="thumb-expired-mark">⧗</span>
        </span>

        <span class="thumb-hover" aria-hidden="true">
          <span class="thumb-open">›</span>
        </span>

        <span class="scrub" *ngIf="variant === 'run'" aria-hidden="true">
          <span [style.width.%]="percent"></span>
        </span>
      </a>

      <div class="card-body">
        <div class="card-head">
          <span class="card-title" [title]="title">{{ title }}</span>
          <span class="card-time mono">{{ createdAt | date: dateFormat }}</span>
        </div>

        <p class="card-prompt">{{ promptText }}</p>

        <div class="card-progress" *ngIf="variant === 'run' && isRunning">
          <div class="card-progress-head mono">
            <span class="stage">{{ stageLabel }}</span>
            <span class="pct">{{ percent }}%</span>
          </div>
          <div class="card-progress-track">
            <div class="card-progress-fill" [style.width.%]="percent"></div>
          </div>
        </div>

        <p class="expired-note" *ngIf="variant === 'asset' && isExpired">
          File removed by storage retention{{ expiredOn }}. Re-run to regenerate it.
        </p>

        <div class="card-foot">
          <a [routerLink]="['/jobs', job.id]" class="view">View details →</a>

          <button
            *ngIf="job.status === 'COMPLETED' && !isExpired"
            type="button"
            class="dl"
            (click)="onDownload($event)"
            [attr.aria-label]="'Download ' + title">
            <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor"
                 stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M10 3v9" /><path d="M6 9.5l4 3.5 4-3.5" /><path d="M3.5 16.5h13" />
            </svg>
            Download
          </button>

          <!-- Re-run costs a credit like any other job, so it is disabled when the
               balance is spent rather than failing at the API with a 402. -->
          <button
            *ngIf="variant === 'asset' && isExpired"
            type="button"
            class="dl rerun"
            [disabled]="rerunning || rerunDisabled"
            [title]="rerunHint"
            (click)="onRerun($event)">
            <span class="rerun-spin" *ngIf="rerunning" aria-hidden="true"></span>
            <svg *ngIf="!rerunning" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor"
                 stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M16.5 6.5a6.5 6.5 0 1 0 1.2 5.5" /><path d="M17.5 3v4h-4" />
            </svg>
            {{ rerunning ? 'Starting…' : 'Re-run' }}
          </button>

          <!-- Process view keeps a placeholder where the button would be, so the footer
               does not reflow as a job moves through its states. -->
          <span *ngIf="variant === 'run' && isExpired" class="dl dl-expired" [title]="expiredHint">Expired</span>
          <span *ngIf="variant === 'run' && job.status !== 'COMPLETED'" class="dl dl-idle">
            {{ job.status === 'FAILED' ? 'Unavailable' : 'Pending' }}
          </span>
        </div>
      </div>
    </article>
  `,
  styles: [`
    /* The host is the grid item; the card fills it so cards in a row stay equal height. */
    :host { display: flex; min-width: 0; }

    .card {
      flex: 1; min-width: 0;
      display: flex; flex-direction: column; border-radius: 16px; overflow: hidden;
      border: 1px solid var(--cf-border-soft); background: rgba(16, 16, 23, .72);
      transition: transform .22s cubic-bezier(.2, .7, .3, 1), box-shadow .22s ease, border-color .22s ease;
    }
    .card:hover { transform: translateY(-5px); border-color: rgba(146, 118, 255, .5); box-shadow: 0 24px 52px rgba(0, 0, 0, .55); }
    /* Expired cards recede: still browsable, visibly no longer a live deliverable. */
    .card-dim { background: rgba(14, 14, 19, .6); }
    .card-dim .thumb { filter: saturate(.35); }
    .card-dim:hover { border-color: rgba(255, 255, 255, .2); }

    .thumb { position: relative; display: block; aspect-ratio: 16 / 9; overflow: hidden; }
    .thumb-video { background: linear-gradient(140deg, #1B1430, #2A1C4A 60%, #141B2E); }
    .thumb-deck { background: linear-gradient(140deg, #2A1A16, #3A2418 60%, #1C1512); }
    .thumb-report { background: linear-gradient(140deg, #141F1B, #193029 60%, #101A18); }
    .card-failed .thumb { background: linear-gradient(140deg, #2A1418, #3B1A20 60%, #1C1216); }
    /* Fades in once decoded so a card never flashes a half-painted frame. */
    .thumb-img {
      position: absolute; inset: 0; width: 100%; height: 100%;
      object-fit: cover; display: block;
      opacity: 0; transition: opacity .3s ease;
    }
    .thumb-img.loaded { opacity: 1; }
    .thumb-lines { position: absolute; inset: 0; background-image: repeating-linear-gradient(118deg, rgba(255, 255, 255, .05) 0 1px, transparent 1px 12px); }
    .thumb-wash { position: absolute; inset: 0; background: radial-gradient(closest-side at 64% 40%, rgba(124, 92, 255, .22), transparent); }
    /* Keeps the JOB-ID legible over a bright frame. The badges sit on their own
       translucent backing, so only the bottom needs darkening. */
    .thumb-scrim {
      position: absolute; inset: 0; pointer-events: none;
      background: linear-gradient(0deg, rgba(8, 8, 12, .74) 0%, rgba(8, 8, 12, .3) 24%, transparent 48%);
    }

    .thumb-badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; }
    .thumb-slug { position: absolute; left: 11px; bottom: 11px; font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase; color: rgba(255, 255, 255, .45); }

    .thumb-state { position: absolute; inset: 0; display: grid; place-items: center; }
    .thumb-spin { width: 38px; height: 38px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, .14); border-top-color: var(--cf-accent-link); animation: cfSpin 1s linear infinite; }
    .thumb-state .cf-sheen > span { width: 30%; animation: cfShimmer 2.6s ease-in-out infinite; }
    .thumb-state-failed { background: rgba(24, 8, 10, .35); }
    .thumb-bang {
      width: 34px; height: 34px; border-radius: 50%; border: 1.5px solid rgba(248, 113, 113, .5);
      background: rgba(248, 113, 113, .14); display: grid; place-items: center; color: var(--cf-err-soft); font-size: 16px;
    }
    .thumb-state-expired { background: rgba(10, 10, 14, .58); }
    .thumb-expired-mark {
      width: 34px; height: 34px; border-radius: 50%; border: 1.5px solid rgba(255, 255, 255, .22);
      background: rgba(255, 255, 255, .06); display: grid; place-items: center;
      color: var(--cf-text-dimmer); font-size: 15px;
    }

    .thumb-hover {
      position: absolute; inset: 0; display: grid; place-items: center; opacity: 0;
      background: linear-gradient(0deg, rgba(8, 8, 12, .6), rgba(8, 8, 12, .04));
      transition: opacity .22s ease;
    }
    .card:hover .thumb-hover { opacity: 1; }
    .thumb-open {
      width: 46px; height: 46px; border-radius: 50%; background: rgba(255, 255, 255, .15);
      backdrop-filter: blur(8px); border: 1px solid rgba(255, 255, 255, .3);
      display: grid; place-items: center; color: #fff; font-size: 26px; line-height: 1; padding-bottom: 3px;
      transform: scale(.82); transition: transform .22s cubic-bezier(.2, .7, .3, 1);
    }
    .card:hover .thumb-open { transform: scale(1); }

    .scrub { position: absolute; left: 0; right: 0; bottom: 0; height: 2px; background: rgba(255, 255, 255, .1); }
    .scrub > span { display: block; height: 100%; background: linear-gradient(90deg, #7C5CFF, #3B82F6); transition: width .6s ease; }

    .card-body { padding: 14px 15px 15px; display: flex; flex-direction: column; gap: 11px; flex: 1; }
    .card-head { display: flex; align-items: center; gap: 9px; }
    .card-title { font-size: 14px; font-weight: 600; letter-spacing: -.01em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .card-time { margin-left: auto; flex: none; font-size: 10.5px; color: var(--cf-text-dimmer); }
    .card-prompt {
      margin: 0; font-size: 12.4px; line-height: 1.55; color: var(--cf-text-muted);
      display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    .expired-note { margin: 0; font-size: 11px; line-height: 1.5; color: var(--cf-text-dimmer); }

    .card-progress { display: flex; flex-direction: column; gap: 6px; }
    .card-progress-head { display: flex; align-items: baseline; justify-content: space-between; font-size: 10.5px; gap: 8px; }
    .card-progress-head .stage { color: var(--cf-accent-link-hover); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .card-progress-head .pct { color: var(--cf-text-dimmer); flex: none; }
    .card-progress-track { height: 4px; border-radius: 99px; background: rgba(255, 255, 255, .07); overflow: hidden; }
    .card-progress-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, #7C5CFF, #3B82F6); box-shadow: 0 0 10px rgba(124, 92, 255, .5); transition: width .6s ease; }

    .card-foot { margin-top: auto; padding-top: 4px; display: flex; align-items: center; gap: 9px; }
    .view { font-size: 12.5px; font-weight: 500; color: var(--cf-accent-link); text-decoration: none; transition: color .15s ease; }
    .view:hover { color: var(--cf-accent-link-hover); }
    .dl {
      margin-left: auto; display: flex; align-items: center; gap: 7px; height: 31px; padding: 0 12px;
      border-radius: 9px; font-family: inherit; font-size: 12px; cursor: pointer;
      border: 1px solid var(--cf-border-strong); background: rgba(255, 255, 255, .05); color: #D6D6E2;
      transition: background .15s ease, opacity .15s ease;
    }
    .dl:hover { background: rgba(255, 255, 255, .1); }
    .dl:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }
    .dl-idle { border-color: var(--cf-border-soft); background: rgba(255, 255, 255, .02); color: var(--cf-text-dimmer); cursor: default; }
    .dl-expired { border-color: var(--cf-border-soft); background: rgba(255, 255, 255, .02); color: var(--cf-text-dimmer); cursor: help; }
    .rerun { border-color: rgba(146, 118, 255, .4); background: rgba(124, 92, 255, .14); color: var(--cf-accent-on-pill); }
    .rerun:hover:not(:disabled) { background: rgba(124, 92, 255, .24); }
    .dl:disabled { opacity: .45; cursor: not-allowed; }
    .rerun-spin {
      width: 13px; height: 13px; border-radius: 50%; flex: none;
      border: 1.5px solid rgba(255, 255, 255, .2); border-top-color: currentColor;
      animation: cfSpin .8s linear infinite;
    }
  `]
})
export class DeliverableCardComponent {
  @Input({ required: true }) job!: Job;

  /** 'run' = dashboard (a job in progress); 'asset' = library (a finished deliverable). */
  @Input() variant: 'run' | 'asset' = 'run';

  /** A re-run this card started, still waiting on the API. */
  @Input() rerunning = false;
  @Input() rerunDisabled = false;
  @Input() rerunHint = '';

  @Output() download = new EventEmitter<Job>();
  @Output() rerun = new EventEmitter<Job>();

  /** Poster decoded — lets the gradient underneath fade out. */
  thumbLoaded = false;
  /** Poster request failed; retrying it on every change detection would spam the server. */
  private thumbFailed = false;

  constructor(private jobService: JobService) {}

  // --------------------------------------------------------------- variants

  private get isAsset(): boolean {
    return this.variant === 'asset';
  }

  /**
   * The dashboard shows a time (today's runs, at a glance); the Library shows a date
   * (work from weeks ago).
   */
  get dateFormat(): string {
    return this.isAsset ? 'd MMM' : 'shortTime';
  }

  get dimWhenExpired(): boolean {
    return this.isAsset;
  }

  // ----------------------------------------------------------------- status

  get isRunning(): boolean {
    return this.job.status === 'RUNNING' || this.job.status === 'QUEUED';
  }

  get isExpired(): boolean {
    return jobIsExpired(this.job);
  }

  get expiredOn(): string {
    return jobExpiredOn(this.job);
  }

  get expiredHint(): string {
    return `This deliverable was removed by storage retention${this.expiredOn}. The job record is kept, but the file is gone — re-run the prompt to regenerate it.`;
  }

  get percent(): number {
    return jobPercent(this.job);
  }

  get stageLabel(): string {
    return jobStageLabel(this.job);
  }

  // ---------------------------------------------------------------- display

  get thumbnailSrc(): string | null {
    if (!this.job.thumbnail_url || this.thumbFailed) return null;
    return this.jobService.getThumbnailUrl(this.job.thumbnail_url);
  }

  onThumbLoad(): void {
    this.thumbLoaded = true;
  }

  onThumbError(): void {
    this.thumbFailed = true;
    this.thumbLoaded = false;
  }

  /** Drives both the thumbnail gradient and the type badge. */
  get thumbTone(): string {
    if (this.job.agent_type === 'presentation') return 'deck';
    if (this.job.agent_type === 'latex') return 'report';
    return 'video';
  }

  get typeLabel(): string {
    if (this.job.agent_type === 'presentation') return 'Deck';
    if (this.job.agent_type === 'latex') return 'Report';
    if (this.job.agent_type === 'video') return 'Video';
    return this.job.agent_type;
  }

  get title(): string {
    return jobTitle(this.job);
  }

  get promptText(): string {
    return jobPromptText(this.job, this.isAsset);
  }

  get createdAt(): Date | null {
    return jobCreatedAt(this.job);
  }

  // ---------------------------------------------------------------- actions

  onDownload(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.download.emit(this.job);
  }

  onRerun(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    if (this.rerunning || this.rerunDisabled) return;
    this.rerun.emit(this.job);
  }
}
