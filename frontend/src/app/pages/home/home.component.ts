import { Component, OnInit, HostListener } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Router } from '@angular/router';
import { JobService } from '../../services/job.service';
import { Job } from '../../models/job.model';
import { DeliverableCardComponent } from '../../components/deliverable-card/deliverable-card.component';

/** A filter pill above the deliverables grid. `match` is applied to the real job list. */
interface JobFilter {
  label: string;
  match: (j: Job) => boolean;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule, DeliverableCardComponent],
  template: `
    <div class="db">

      <!-- ===== hero ===== -->
      <section class="hero">
        <div class="hero-blob hero-blob-a" aria-hidden="true"></div>
        <div class="hero-blob hero-blob-b" aria-hidden="true"></div>
        <div class="hero-blob hero-blob-c" aria-hidden="true"></div>
        <div class="hero-grid" aria-hidden="true"></div>

        <div class="hero-body">
          <div class="hero-eyebrow">
            <span class="hero-eyebrow-dot"></span>
            <span class="mono">Multi-agent orchestration</span>
          </div>

          <h1>What will you <span class="grad">create</span> today?</h1>
          <p class="hero-sub">
            Describe the outcome. Specialised agents plan, write, source, voice, composite and render it for you.
          </p>

          <div class="hero-actions">
            <a routerLink="/create" class="cta">
              Generate New Deliverable
              <span class="cta-key mono">{{ shortcutHint }}</span>
            </a>
          </div>
        </div>
      </section>

      <!-- ===== stats ===== -->
      <section class="stats">
        <div class="stat">
          <div class="stat-glow" aria-hidden="true"></div>
          <div class="stat-row">
            <div class="stat-icon stat-icon-total">
              <svg viewBox="0 0 20 20" width="19" height="19" fill="none" stroke="currentColor"
                   stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M2.5 6.5h5l1.5 2h8.5v8.5h-15z" /><path d="M2.5 6.5V4h5" />
              </svg>
            </div>
            <div class="stat-text">
              <div class="stat-headline">
                <span class="stat-value">{{ jobs.length }}</span>
                <span class="stat-delta ok">{{ newThisWeekLabel }}</span>
              </div>
              <span class="stat-label">Total Jobs</span>
            </div>
          </div>
          <div class="stat-bar"><div class="stat-bar-fill bar-total" [style.width.%]="finishedShare"></div></div>
        </div>

        <div class="stat">
          <div class="stat-glow glow-ok" aria-hidden="true"></div>
          <div class="stat-row">
            <div class="stat-icon stat-icon-ok">
              <svg viewBox="0 0 20 20" width="19" height="19" fill="none" stroke="currentColor"
                   stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M3.5 10.5l4 4 9-9" />
              </svg>
            </div>
            <div class="stat-text">
              <div class="stat-headline">
                <span class="stat-value">{{ completedCount }}</span>
                <span class="stat-delta ok">{{ successRateLabel }}</span>
              </div>
              <span class="stat-label">Completed Deliverables</span>
            </div>
          </div>
          <div class="stat-bar"><div class="stat-bar-fill bar-ok" [style.width.%]="completedShare"></div></div>
        </div>

        <div class="stat">
          <div class="stat-glow glow-warn" aria-hidden="true"></div>
          <div class="stat-row">
            <div class="stat-icon stat-icon-warn">
              <svg viewBox="0 0 20 20" width="19" height="19" fill="none" stroke="currentColor"
                   stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M11 2.5L4 11.5h5l-1 6 7-9h-5z" />
              </svg>
            </div>
            <div class="stat-text">
              <div class="stat-headline">
                <span class="stat-value">{{ processingCount }}</span>
                <span class="stat-delta warn">{{ activeLabel }}</span>
              </div>
              <span class="stat-label">Active Processing</span>
            </div>
          </div>
          <div class="stat-bar"><div class="stat-bar-fill bar-warn" [style.width.%]="activeShare"></div></div>
        </div>
      </section>

      <!-- ===== recent deliverables ===== -->
      <section class="recent">
        <div class="recent-head">
          <div class="recent-titles">
            <h2>Recent deliverables</h2>
            <span class="recent-sub">{{ jobs.length }} {{ jobs.length === 1 ? 'job' : 'jobs' }} · {{ processingCount }} currently rendering</span>
          </div>

          <div class="recent-tools">
            <button
              type="button"
              class="cf-pill"
              *ngFor="let f of filters"
              [class.cf-pill-on]="activeFilter === f.label"
              (click)="activeFilter = f.label">
              {{ f.label }}<span class="mono pill-count">{{ countFor(f) }}</span>
            </button>

            <button type="button" class="cf-btn-ghost refresh" (click)="loadJobs()" [disabled]="isLoading">
              <span class="refresh-icon" [class.spinning]="isLoading">
                <svg viewBox="0 0 20 20" width="15" height="15" fill="none" stroke="currentColor"
                     stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M16.5 6.5a6.5 6.5 0 1 0 1.2 5.5" /><path d="M17.5 3v4h-4" />
                </svg>
              </span>
              Refresh
            </button>
          </div>
        </div>

        <div class="cf-loading" *ngIf="isLoading">
          <div class="cf-spinner"></div>
          <p>Loading jobs…</p>
        </div>

        <div class="cf-empty cf-panel" *ngIf="!isLoading && jobs.length === 0">
          <h3>No deliverables yet</h3>
          <p>Create your first presentation, report, or video montage.</p>
          <a routerLink="/create" class="cf-btn-primary">Create first deliverable</a>
        </div>

        <div class="cf-empty cf-panel" *ngIf="!isLoading && jobs.length > 0 && visibleJobs.length === 0">
          <h3>Nothing matches “{{ activeFilter }}”</h3>
          <p>Try another filter.</p>
        </div>

        <div class="grid" *ngIf="!isLoading && visibleJobs.length > 0">
          <app-deliverable-card
            *ngFor="let job of visibleJobs"
            [job]="job"
            variant="run"
            (download)="downloadArtifact($event)" />
        </div>
      </section>
    </div>
  `,
  styles: [`
    .db { display: flex; flex-direction: column; gap: 20px; max-width: 1180px; margin: 0 auto; padding: 28px 32px 56px; }
    .mono { font-family: var(--cf-font-mono); }
    .grad { background: linear-gradient(100deg, #C6BCFF, #8FB6FF 55%, #E0B4FF); -webkit-background-clip: text; background-clip: text; color: transparent; }

    /* — hero — */
    .hero {
      position: relative; overflow: hidden; border-radius: 20px;
      border: 1px solid var(--cf-border-card);
      background: linear-gradient(150deg, rgba(26, 20, 50, .8), rgba(12, 12, 20, .86) 55%, rgba(11, 18, 34, .8));
      padding: 52px 40px 46px;
    }
    .hero-blob { position: absolute; pointer-events: none; }
    .hero-blob-a {
      top: -180px; left: 6%; width: 520px; height: 420px; filter: blur(12px);
      background: radial-gradient(closest-side, rgba(124, 92, 255, .42), transparent);
      animation: cfBlobA 18s ease-in-out infinite;
    }
    .hero-blob-b {
      bottom: -240px; right: 2%; width: 560px; height: 460px; filter: blur(14px);
      background: radial-gradient(closest-side, rgba(59, 130, 246, .34), transparent);
      animation: cfBlobB 24s ease-in-out infinite;
    }
    .hero-blob-c {
      top: 20%; right: 32%; width: 340px; height: 300px; filter: blur(16px);
      background: radial-gradient(closest-side, rgba(217, 110, 255, .18), transparent);
      animation: cfBlobC 30s ease-in-out infinite;
    }
    .hero-grid {
      position: absolute; inset: 0; pointer-events: none;
      background-image:
        linear-gradient(rgba(255, 255, 255, .022) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, .022) 1px, transparent 1px);
      background-size: 46px 46px;
      -webkit-mask-image: radial-gradient(closest-side at 50% 40%, #000, transparent);
      mask-image: radial-gradient(closest-side at 50% 40%, #000, transparent);
    }
    .hero-body { position: relative; display: flex; flex-direction: column; align-items: center; gap: 20px; text-align: center; }
    .hero-eyebrow {
      display: flex; align-items: center; gap: 8px; height: 30px; padding: 0 13px; border-radius: 99px;
      border: 1px solid rgba(146, 118, 255, .35); background: var(--cf-accent-tint);
    }
    .hero-eyebrow .mono { font-size: 10px; letter-spacing: .15em; text-transform: uppercase; color: var(--cf-accent-link-hover); }
    .hero-eyebrow-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--cf-accent-link); animation: cfPulse 1.6s ease-in-out infinite; }
    .hero h1 { margin: 0; font-size: 52px; font-weight: 600; letter-spacing: -.036em; line-height: 1.06; max-width: 760px; text-wrap: balance; }
    .hero-sub { margin: 0; font-size: 15.5px; line-height: 1.6; color: var(--cf-text-3); max-width: 530px; text-wrap: pretty; }
    .hero-actions { display: flex; align-items: center; gap: 11px; margin-top: 6px; flex-wrap: wrap; justify-content: center; }
    .cta {
      display: flex; align-items: center; gap: 10px; height: 48px; padding: 0 26px; border-radius: 13px;
      background: var(--cf-accent-grad); color: #fff; font-size: 15px; font-weight: 600;
      box-shadow: 0 14px 34px rgba(92, 80, 255, .44);
      transition: transform .18s cubic-bezier(.2, .7, .3, 1), box-shadow .18s ease;
    }
    .cta:hover { color: #fff; transform: translateY(-2px); box-shadow: 0 20px 44px rgba(92, 80, 255, .6); }
    .cta:active { transform: translateY(0); }
    .cta-key { font-size: 11px; opacity: .75; border-left: 1px solid rgba(255, 255, 255, .3); padding-left: 10px; }
    @media (max-width: 760px) { .hero { padding: 38px 22px 34px; } .hero h1 { font-size: 36px; } }

    /* — stats — */
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 13px; }
    @media (max-width: 860px) { .stats { grid-template-columns: 1fr; } }
    .stat {
      position: relative; overflow: hidden; padding: 20px 21px; border-radius: 16px;
      border: 1px solid var(--cf-border-soft);
      background: linear-gradient(160deg, rgba(255, 255, 255, .04), rgba(255, 255, 255, .012));
      transition: transform .2s cubic-bezier(.2, .7, .3, 1), box-shadow .2s ease, border-color .2s ease;
    }
    .stat:hover { transform: translateY(-3px); border-color: rgba(146, 118, 255, .42); box-shadow: 0 18px 40px rgba(0, 0, 0, .45); }
    .stat-glow {
      position: absolute; top: -70px; right: -50px; width: 200px; height: 170px; pointer-events: none;
      background: radial-gradient(closest-side, rgba(124, 92, 255, .30), transparent);
      opacity: .45; transition: opacity .25s ease;
    }
    .stat:hover .stat-glow { opacity: 1; }
    .glow-ok { background: radial-gradient(closest-side, rgba(52, 211, 153, .24), transparent); }
    .glow-warn { background: radial-gradient(closest-side, rgba(240, 163, 78, .22), transparent); }
    .stat-row { position: relative; display: flex; align-items: center; gap: 15px; }
    .stat-icon { width: 42px; height: 42px; flex: none; border-radius: 12px; display: grid; place-items: center; border: 1px solid; }
    .stat-icon-total { border-color: rgba(146, 118, 255, .4); background: rgba(124, 92, 255, .16); color: var(--cf-accent-link-hover); }
    .stat-icon-ok { border-color: rgba(52, 211, 153, .34); background: rgba(52, 211, 153, .12); color: var(--cf-ok-soft); }
    .stat-icon-warn { border-color: rgba(240, 163, 78, .32); background: rgba(240, 163, 78, .12); color: var(--cf-warn); }
    .stat-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .stat-headline { display: flex; align-items: baseline; gap: 9px; }
    .stat-value { font-size: 32px; font-weight: 600; letter-spacing: -.03em; line-height: 1; font-variant-numeric: tabular-nums; }
    .stat-delta { font-size: 11.5px; }
    .stat-delta.ok { color: var(--cf-ok-soft); }
    .stat-delta.warn { color: var(--cf-warn-soft); }
    .stat-label { font-size: 12.5px; color: var(--cf-text-muted); }
    .stat-bar { position: relative; margin-top: 16px; height: 3px; border-radius: 99px; background: rgba(255, 255, 255, .06); overflow: hidden; }
    .stat-bar-fill { height: 100%; border-radius: 99px; transition: width .5s ease; }
    .bar-total { background: linear-gradient(90deg, #7C5CFF, #3B82F6); }
    .bar-ok { background: linear-gradient(90deg, #34D399, #3B82F6); }
    .bar-warn { background: linear-gradient(90deg, #F0A34E, #7C5CFF); }

    /* — recent — */
    .recent { display: flex; flex-direction: column; gap: 14px; }
    .recent-head { display: flex; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
    .recent-titles { display: flex; flex-direction: column; gap: 5px; }
    .recent h2 { margin: 0; font-size: 20px; font-weight: 600; letter-spacing: -.022em; }
    .recent-sub { font-size: 12.5px; color: var(--cf-text-dim); }
    .recent-tools { margin-left: auto; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }

    .pill-count { font-size: 10px; opacity: .6; }

    .refresh-icon { display: inline-grid; place-items: center; }
    .refresh-icon.spinning { animation: cfSpin .7s linear infinite; }

    /* — job cards —
       The card itself now lives in DeliverableCardComponent, shared with the Library.
       Only the grid that lays the cards out belongs to this page. */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
    @media (max-width: 620px) { .grid { grid-template-columns: 1fr; } }
  `]
})
export class HomeComponent implements OnInit {
  jobs: Job[] = [];
  isLoading = true;
  activeFilter = 'All';


  readonly filters: JobFilter[] = [
    { label: 'All',      match: () => true },
    { label: 'Video',    match: j => j.agent_type === 'video' },
    { label: 'Decks',    match: j => j.agent_type === 'presentation' },
    { label: 'Reports',  match: j => j.agent_type === 'latex' },
    { label: 'Running',  match: j => j.status === 'RUNNING' || j.status === 'QUEUED' }
  ];

  constructor(private jobService: JobService, private router: Router) {}

  ngOnInit() {
    this.loadJobs();
  }

  /** ⌘⏎ / Ctrl+⏎ opens the create page — the shortcut the hero button advertises. */
  @HostListener('document:keydown', ['$event'])
  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      this.router.navigate(['/create']);
    }
  }

  get shortcutHint(): string {
    const mac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || '');
    return mac ? '⌘⏎' : 'Ctrl ⏎';
  }

  loadJobs() {
    this.isLoading = true;
    this.jobService.listJobs().subscribe({
      next: (jobs) => {
        this.jobs = jobs;
        this.isLoading = false;
      },
      error: () => {
        this.isLoading = false;
      }
    });
  }

  // ------------------------------------------------------------------ counts

  get completedCount(): number {
    return this.jobs.filter(j => j.status === 'COMPLETED').length;
  }

  get processingCount(): number {
    return this.jobs.filter(j => j.status === 'RUNNING' || j.status === 'QUEUED').length;
  }

  get failedCount(): number {
    return this.jobs.filter(j => j.status === 'FAILED').length;
  }

  private get finishedCount(): number {
    return this.completedCount + this.failedCount;
  }

  /** Bars show each bucket's real share of the total, not a decorative width. */
  get finishedShare(): number { return this.share(this.finishedCount); }
  get completedShare(): number { return this.share(this.completedCount); }
  get activeShare(): number { return this.share(this.processingCount); }

  private share(n: number): number {
    return this.jobs.length ? Math.round((n / this.jobs.length) * 100) : 0;
  }

  get newThisWeekLabel(): string {
    const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
    const n = this.jobs.filter(j => {
      const d = this.createdAt(j);
      return d ? d.getTime() >= cutoff : false;
    }).length;
    return n ? `+${n} this week` : 'none this week';
  }

  /** Only meaningful over jobs that actually finished, so queued work can't skew it. */
  get successRateLabel(): string {
    if (!this.finishedCount) return 'no runs yet';
    return `${Math.round((this.completedCount / this.finishedCount) * 100)}% success`;
  }

  get activeLabel(): string {
    if (!this.processingCount) return 'idle';
    const queued = this.jobs.filter(j => j.status === 'QUEUED').length;
    return queued ? `${queued} queued` : 'in progress';
  }

  // ----------------------------------------------------------------- listing

  countFor(f: JobFilter): number {
    return this.jobs.filter(f.match).length;
  }

  get visibleJobs(): Job[] {
    const f = this.filters.find(x => x.label === this.activeFilter);
    return f ? this.jobs.filter(f.match) : this.jobs;
  }

  // Card presentation -- thumbnails, badges, titles, expiry -- now lives in
  // DeliverableCardComponent, shared with the Library. This page keeps only the data
  // it actually reasons about: the job list, the filters, and the stats above.

  /** The API sends naive UTC timestamps; `new Date()` would read them as local. */
  createdAt(job: Job): Date | null {
    const value = job.created_at;
    if (!value) return null;
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
    const d = new Date(hasZone ? value : value + 'Z');
    return isNaN(d.getTime()) ? null : d;
  }

  // ---------------------------------------------------------------- download

  getArtifactUrl(jobId: string): string {
    return this.jobService.getArtifactUrl(jobId);
  }

  /** Invoked by the card's (download) output, which has already stopped the event. */
  downloadArtifact(job: Job) {
    this.jobService.downloadArtifact(job.id).subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `deliverable_${job.id.substring(0, 8)}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error('Artifact download error:', err);
        window.open(this.getArtifactUrl(job.id), '_blank');
      }
    });
  }
}
