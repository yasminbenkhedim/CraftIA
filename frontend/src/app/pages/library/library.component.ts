import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Job } from '../../models/job.model';
import { JobService } from '../../services/job.service';
import { CreditsService } from '../../services/credits.service';
import { DeliverableCardComponent } from '../../components/deliverable-card/deliverable-card.component';
import { jobCreatedAt, jobIsExpired, jobPromptText, jobTitle } from '../../models/job.util';

interface TypeFilter {
  label: string;
  match: (j: Job) => boolean;
}

/**
 * Library — the finished work, as assets rather than as processes.
 *
 * The dashboard answers "is my render done?"; this answers "where is the deck I made for
 * that client last month?". It therefore shows only COMPLETED jobs, sorts newest first,
 * and makes expiry a first-class state: a job whose file storage retention has removed is
 * still a record worth keeping, and its prompt is still worth re-running.
 *
 * Card styling deliberately mirrors the dashboard's rather than importing it. The two
 * pages' cards are visually the same but structurally divergent (no progress bar here, a
 * re-run action instead), and the dashboard component is already at its CSS budget. If a
 * third page ever needs this card, extract it into a shared component then — not before.
 */
@Component({
  selector: 'app-library',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, DeliverableCardComponent],
  template: `
    <div class="lib">
      <!-- ===== head ===== -->
      <section class="lib-head">
        <div class="lib-titles">
          <h1>Library</h1>
          <p class="lib-sub">{{ subtitle }}</p>
        </div>

        <button type="button" class="cf-btn-ghost refresh" (click)="loadJobs()" [disabled]="isLoading">
          <span class="refresh-icon" [class.spinning]="isLoading">
            <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor"
                 stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M16.5 6.5a6.5 6.5 0 1 0 1.2 5.5" /><path d="M17.5 3v4h-4" />
            </svg>
          </span>
          Refresh
        </button>
      </section>

      <!-- ===== toolbar ===== -->
      <section class="tools">
        <label class="search" [class.filled]="query.trim().length > 0">
          <svg class="search-icon" viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor"
               stroke-width="1.6" stroke-linecap="round" aria-hidden="true">
            <circle cx="9" cy="9" r="5.5" /><path d="M13.5 13.5L17 17" />
          </svg>
          <input
            type="search"
            [(ngModel)]="query"
            placeholder="Search titles and prompts…"
            aria-label="Search the library"
            autocomplete="off" />
          <button
            type="button"
            class="search-clear"
            *ngIf="query.trim().length > 0"
            (click)="query = ''"
            aria-label="Clear search">×</button>
        </label>

        <div class="type-pills">
          <button
            type="button"
            class="cf-pill"
            *ngFor="let f of typeFilters"
            [class.cf-pill-on]="activeType === f.label"
            (click)="activeType = f.label">
            {{ f.label }}<span class="mono pill-count">{{ countFor(f) }}</span>
          </button>
        </div>
      </section>

      <!-- ===== states ===== -->
      <div class="cf-loading" *ngIf="isLoading">
        <div class="cf-spinner"></div>
        <p>Loading your library…</p>
      </div>

      <div class="cf-empty cf-panel" *ngIf="!isLoading && errorMessage">
        <h3>Could not load your library</h3>
        <p>{{ errorMessage }}</p>
        <button type="button" class="cf-btn-primary" (click)="loadJobs()">Try again</button>
      </div>

      <div class="cf-empty cf-panel" *ngIf="!isLoading && !errorMessage && completed.length === 0">
        <h3>Nothing in your library yet</h3>
        <p>Finished videos, decks and reports land here automatically.</p>
        <a routerLink="/create" class="cf-btn-primary">Create your first deliverable</a>
      </div>

      <div class="cf-empty cf-panel"
           *ngIf="!isLoading && !errorMessage && completed.length > 0 && visibleJobs.length === 0">
        <h3>No matches</h3>
        <p>{{ noMatchHint }}</p>
        <button type="button" class="cf-btn-primary" (click)="clearFilters()">Clear filters</button>
      </div>

      <!-- ===== grid ===== -->
      <div class="grid" *ngIf="!isLoading && visibleJobs.length > 0">
        <app-deliverable-card
          *ngFor="let job of visibleJobs"
          [job]="job"
          variant="asset"
          [rerunning]="rerunningId === job.id"
          [rerunDisabled]="credits.isOutOfCredits()"
          [rerunHint]="rerunTitle(job)"
          (download)="downloadArtifact($event)"
          (rerun)="rerun($event)" />
      </div>

      <div class="toast" *ngIf="rerunError">⚠️ {{ rerunError }}</div>
    </div>
  `,
  styles: [`
    .lib { display: flex; flex-direction: column; gap: 18px; max-width: 1180px; margin: 0 auto; padding: 28px 32px 56px; }

    .lib-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
    .lib-titles h1 { margin: 0 0 5px; font-size: 26px; font-weight: 600; letter-spacing: -.022em; }
    .lib-sub { margin: 0; font-size: 12.5px; color: var(--cf-text-muted); }

    .refresh { display: inline-flex; align-items: center; gap: 8px; }
    .refresh-icon { display: inline-flex; }
    .refresh-icon.spinning { animation: cfSpin 1s linear infinite; }

    /* — toolbar — */
    .tools { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .search {
      position: relative; display: flex; align-items: center; gap: 8px;
      flex: 1; min-width: 220px; max-width: 420px; height: 36px; padding: 0 11px;
      border-radius: var(--cf-radius-sm);
      border: 1px solid var(--cf-border-card);
      background: rgba(255, 255, 255, .02);
      transition: border-color .15s ease, background .15s ease;
    }
    .search:focus-within, .search.filled { border-color: rgba(146, 118, 255, .5); background: rgba(124, 92, 255, .07); }
    .search-icon { color: var(--cf-text-dimmer); flex: none; }
    .search input {
      all: unset; flex: 1; min-width: 0; font-size: 12.5px; color: var(--cf-text);
    }
    .search input::placeholder { color: var(--cf-text-dimmer); }
    /* Safari draws its own clear affordance on type=search; ours is the only one. */
    .search input::-webkit-search-cancel-button { display: none; }
    .search-clear {
      all: unset; cursor: pointer; flex: none; padding: 0 3px;
      font-size: 15px; line-height: 1; color: var(--cf-text-dimmer);
    }
    .search-clear:hover { color: var(--cf-text); }

    .type-pills { display: flex; gap: 6px; flex-wrap: wrap; }
    .pill-count { margin-left: 6px; font-size: 10px; opacity: .65; }

    /* — grid —
       The card itself is DeliverableCardComponent, shared with the dashboard. Only the
       layout that positions the cards belongs to this page. */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
    @media (max-width: 620px) { .grid { grid-template-columns: 1fr; } }

    .toast {
      position: sticky; bottom: 16px; align-self: center;
      padding: 10px 16px; border-radius: var(--cf-radius);
      border: 1px solid rgba(248, 113, 113, .32); background: rgba(30, 10, 12, .92);
      color: var(--cf-err-soft); font-size: 12.5px;
    }

    @media (max-width: 860px) { .lib { padding: 22px 16px 48px; } }
  `]
})
export class LibraryComponent implements OnInit {
  jobs: Job[] = [];
  isLoading = true;
  errorMessage = '';

  query = '';
  activeType = 'All';

  rerunningId: string | null = null;
  rerunError = '';

  readonly typeFilters: TypeFilter[] = [
    { label: 'All', match: () => true },
    { label: 'Video', match: j => j.agent_type === 'video' },
    { label: 'Report', match: j => j.agent_type === 'latex' },
    { label: 'Deck', match: j => j.agent_type === 'presentation' }
  ];

  readonly loadedThumbs = new Set<string>();
  private readonly failedThumbs = new Set<string>();

  constructor(
    private jobService: JobService,
    private router: Router,
    public credits: CreditsService
  ) {}

  ngOnInit(): void {
    this.loadJobs();
    this.credits.refreshQuiet();
  }

  // ----------------------------------------------------------------- loading

  loadJobs(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.jobService.listJobs().subscribe({
      next: jobs => {
        this.jobs = jobs;
        this.isLoading = false;
      },
      error: err => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Could not reach the server.';
      }
    });
  }

  // ----------------------------------------------------------------- listing

  /**
   * Finished work only, newest first.
   *
   * QUEUED, RUNNING and FAILED jobs belong on the dashboard — this page is about what
   * was actually produced. Expired jobs stay: the record and its prompt are still useful
   * even once the file is gone.
   */
  get completed(): Job[] {
    return this.jobs
      .filter(j => j.status === 'COMPLETED')
      .sort((a, b) => (this.createdAt(b)?.getTime() ?? 0) - (this.createdAt(a)?.getTime() ?? 0));
  }

  get visibleJobs(): Job[] {
    const f = this.typeFilters.find(x => x.label === this.activeType);
    const byType = f ? this.completed.filter(f.match) : this.completed;

    const q = this.query.trim().toLowerCase();
    if (!q) return byType;
    return byType.filter(j =>
      this.titleFor(j).toLowerCase().includes(q) || this.promptFor(j).toLowerCase().includes(q)
    );
  }

  countFor(f: TypeFilter): number {
    return this.completed.filter(f.match).length;
  }

  get subtitle(): string {
    const n = this.completed.length;
    if (!n) return 'Your finished deliverables live here';
    const expired = this.completed.filter(j => this.isExpired(j)).length;
    const base = `${n} deliverable${n === 1 ? '' : 's'}`;
    return expired ? `${base} · ${expired} expired` : base;
  }

  get noMatchHint(): string {
    const q = this.query.trim();
    if (q && this.activeType !== 'All') return `Nothing of type “${this.activeType}” matches “${q}”.`;
    if (q) return `Nothing matches “${q}”.`;
    return `You have no deliverables of type “${this.activeType}” yet.`;
  }

  clearFilters(): void {
    this.query = '';
    this.activeType = 'All';
  }

  // ----------------------------------------------------------------- display
  //
  // Rendering belongs to DeliverableCardComponent. These four stay because the PAGE
  // reasons about them: search matches on the title and prompt the card shows, the list
  // sorts on the creation date, and the subtitle counts expired items. They delegate to
  // the same shared helpers the card uses, so search can never miss an item that is
  // visibly on screen.

  isExpired(job: Job): boolean {
    return jobIsExpired(job);
  }

  titleFor(job: Job): string {
    return jobTitle(job);
  }

  promptFor(job: Job): string {
    return jobPromptText(job, true);
  }

  createdAt(job: Job): Date | null {
    return jobCreatedAt(job);
  }

  // ----------------------------------------------------------------- actions

  /** Invoked by the card's (download) output, which has already stopped the event. */
  downloadArtifact(job: Job): void {
    this.jobService.downloadArtifact(job.id).subscribe({
      next: blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `deliverable_${job.id.substring(0, 8)}`;
        a.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => {
        // Almost always a file that vanished since the list was fetched. Re-reading the
        // list re-derives artifact_available and flips the card to its expired state,
        // rather than leaving a button that keeps failing.
        this.rerunError = 'That file is no longer on the server. Refreshing the library…';
        this.loadJobs();
      }
    });
  }

  rerunTitle(job: Job): string {
    if (this.credits.isOutOfCredits()) return 'No credits left — a re-run costs one credit like any other job.';
    return `Regenerate “${this.titleFor(job)}” from the same prompt and settings. Costs 1 credit.`;
  }

  /**
   * Recreate an expired job from its original prompt and render settings.
   *
   * A new job, not a resurrection: it goes through /api/jobs like any other, so it is
   * charged a credit, admission-checked, and blocked with 402 if the balance is spent.
   * The old record is left untouched so the history stays honest about what expired.
   */
  rerun(job: Job): void {
    if (this.rerunningId) return;

    this.rerunningId = job.id;
    this.rerunError = '';

    this.jobService.createJob({
      prompt: job.prompt,
      agent_type: job.agent_type as any,
      // Replays aspect ratio, length, voice and language. The server drops any setting
      // that is no longer supported (an engine removed since the original run) rather
      // than honouring it, so an old job cannot re-run with a dead engine.
      // `?? undefined`: the server sends null for a job with no stored settings, and
      // JobCreate's optional field must be omitted rather than sent as null.
      video_options: job.video_options ?? undefined
    }).subscribe({
      next: created => {
        this.rerunningId = null;
        this.credits.refreshQuiet();
        this.router.navigate(['/jobs', created.id]);
      },
      error: err => {
        this.rerunningId = null;
        this.credits.refreshQuiet();
        this.rerunError = err.status === 402
          ? (err.error?.detail || 'Out of credits — a re-run costs one credit.')
          : (err.error?.detail || 'Could not start the re-run. Please try again.');
      }
    });
  }
}
