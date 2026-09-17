import { Component, OnInit, OnDestroy, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { Subscription, interval } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { JobService } from '../../services/job.service';
import { CreditsService } from '../../services/credits.service';
import { Job } from '../../models/job.model';
import { toPercent, jobPercent, jobStageLabel } from '../../models/progress.util';

type StageState = 'pending' | 'active' | 'done' | 'failed';

/**
 * One row of the visible pipeline.
 *
 * `start` / `end` are the backend progress percentages this stage spans, so the row
 * states are derived from the real number rather than tracked separately. They mirror
 * agents/video/progress.py: director 10, screenwriter 25, voiceover 45, footage 65,
 * compositing 85 (through the 97 finalizing checkpoint), complete 100.
 */
interface PipelineStage {
  key: string;
  name: string;
  detail: string;
  start: number;
  end: number;
}

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="jp">

      <div class="state-card cf-panel" *ngIf="isLoading">
        <div class="cf-spinner"></div>
        <span>Loading job…</span>
      </div>

      <div class="state-card cf-panel error" *ngIf="errorMessage && !isLoading">
        <span class="err-icon">⚠</span>
        <div>
          <h3>Could not load this job</h3>
          <p>{{ errorMessage }}</p>
        </div>
        <a routerLink="/" class="ghost-btn">Back to runs</a>
      </div>

      <ng-container *ngIf="job && !isLoading">

        <nav class="crumbs">
          <a routerLink="/">← Active runs</a>
          <span class="sep">/</span>
          <span class="mono">JOB-{{ job.id.substring(0, 8) }}</span>
        </nav>

        <!-- ===== job header card ===== -->
        <section class="job-card">
          <div class="job-card-wash" aria-hidden="true"></div>
          <div class="job-card-body">

            <div class="job-top">
              <div class="job-ident">
                <div class="badges">
                  <span class="badge badge-accent">{{ getAgentLabel(job.agent_type) }}</span>
                  <span class="badge mono">{{ job.status }}</span>
                </div>
                <h1>Crafting <span class="grad">{{ shortTitle }}</span></h1>
                <div class="meta">
                  <span>Started {{ startedAt | date:'mediumTime' }}</span>
                  <span class="dot">·</span>
                  <span class="mono">{{ elapsed }} elapsed</span>
                </div>
              </div>

              <div class="job-actions">
                <div class="cf-chip" [ngClass]="'cf-chip-' + chipTone">{{ job.status }}</div>
                <button
                  *ngIf="canDownload"
                  type="button"
                  class="cf-btn-primary"
                  (click)="downloadDeliverable(job)">
                  ↓ Download {{ getArtifactFilename(job) }}
                </button>
              </div>
            </div>

            <div class="prompt">
              <div class="prompt-rule" aria-hidden="true"></div>
              <div class="prompt-body">
                <span class="eyebrow">Job prompt</span>
                <p>{{ job.prompt }}</p>
              </div>
            </div>

            <!-- ===== overall progress ===== -->
            <div class="overall">
              <div class="overall-head">
                <div class="overall-titles">
                  <span class="headline">{{ headline }}</span>
                  <span class="sub">Stage {{ displayStageNumber }} of {{ stages.length }} · {{ stageLabel }}</span>
                </div>
                <span class="pct">{{ roundedProgress }}%</span>
              </div>

              <div
                class="cf-track"
                role="progressbar"
                [attr.aria-valuenow]="roundedProgress"
                aria-valuemin="0"
                aria-valuemax="100"
                [attr.aria-valuetext]="stageLabel">
                <div class="cf-fill" [class.cf-fill-ok]="isComplete" [class.cf-fill-err]="isFailed" [style.width.%]="barWidth">
                  <div class="cf-fill-stripe" *ngIf="isRunning" aria-hidden="true"></div>
                </div>
                <div class="cf-sheen" *ngIf="isRunning" aria-hidden="true"><span></span></div>
              </div>

              <div class="ticks">
                <div class="tick" *ngFor="let s of stages" [ngClass]="'tick-' + stateOf(s)"></div>
              </div>
            </div>
          </div>
        </section>

        <!-- ===== pipeline + deliverable ===== -->
        <div class="cols">

          <section class="cf-panel">
            <div class="cf-panel-head">
              <span class="cf-panel-title">Agent pipeline</span>
              <span class="mono panel-count">{{ doneCount }}/{{ stages.length }} complete</span>
            </div>

            <div class="rows">
              <div
                class="row"
                *ngFor="let s of stages; let i = index"
                [ngClass]="'row-' + stateOf(s)">

                <div class="row-icon">
                  <svg viewBox="0 0 20 20" width="20" height="20" fill="none" stroke="currentColor"
                       stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"
                       [ngSwitch]="s.key">
                    <g *ngSwitchCase="'director'">
                      <path d="M2 6.5h13.5v11H2z" /><path d="M15.5 10.5l3.5-2.5v7l-3.5-2.5z" />
                      <circle cx="6" cy="4" r="2" /><circle cx="11.5" cy="4" r="2" />
                    </g>
                    <g *ngSwitchCase="'writer'">
                      <path d="M13 3.5l3.5 3.5L7 16.5H3.5V13z" /><path d="M3 19h14" />
                    </g>
                    <g *ngSwitchCase="'voice'">
                      <path d="M10 3.5a2.5 2.5 0 0 1 2.5 2.5v4a2.5 2.5 0 0 1-5 0V6A2.5 2.5 0 0 1 10 3.5z" />
                      <path d="M5 10a5 5 0 0 0 10 0" /><path d="M10 15v3" />
                    </g>
                    <g *ngSwitchCase="'media'">
                      <path d="M3 5h14v11H3z" /><path d="M3 12l4-4 3.5 3.5L14 8l3 3" />
                      <circle cx="7.5" cy="8" r="1.3" />
                    </g>
                    <g *ngSwitchCase="'compositing'">
                      <path d="M3 3.5h7v7H3z" /><path d="M10 9.5h7v7h-7z" /><path d="M3.5 13.5h4v4h-4z" />
                    </g>
                    <g *ngSwitchDefault>
                      <path d="M10 2.5l7 4v7l-7 4-7-4v-7z" /><path d="M3 6.5l7 4 7-4M10 10.5v7" />
                    </g>
                  </svg>

                  <span class="check" *ngIf="stateOf(s) === 'done'" aria-hidden="true"></span>
                </div>

                <div class="row-body">
                  <div class="row-head">
                    <span class="row-name">{{ s.name }}</span>
                    <span class="tag mono">{{ stateOf(s) }}</span>
                    <span class="row-time mono">{{ stageTime(s) }}</span>
                  </div>
                  <div class="row-detail">{{ s.detail }}</div>

                  <div class="row-bar" *ngIf="stateOf(s) === 'active'">
                    <div class="row-bar-fill" [style.width.%]="stageFraction(s)"></div>
                  </div>

                  <div class="eq" *ngIf="stateOf(s) === 'active'" aria-hidden="true">
                    <span *ngFor="let b of eqBars; let bi = index" [style.animation-delay.s]="bi * 0.09"></span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <aside class="cf-panel deliverable">
            <div class="cf-panel-head">
              <span class="cf-panel-title">Deliverable</span>
            </div>

            <div class="preview" [class.preview-done]="isComplete">
              <div class="preview-grid" aria-hidden="true"></div>
              <div class="preview-wash" aria-hidden="true"></div>
              <div class="cf-sheen preview-sheen" *ngIf="isRunning" aria-hidden="true"><span></span></div>

              <div class="preview-center">
                <div class="cf-spinner" *ngIf="isRunning"></div>
                <div class="preview-tick" *ngIf="isComplete" aria-hidden="true"></div>
                <div class="preview-cross" *ngIf="isFailed" aria-hidden="true">!</div>
                <span class="mono preview-label">{{ previewLabel }}</span>
              </div>
            </div>

            <dl class="facts">
              <div><dt class="mono">Agent</dt><dd>{{ getAgentLabel(job.agent_type) }}</dd></div>
              <div><dt class="mono">Progress</dt><dd>{{ roundedProgress }}%</dd></div>
              <div><dt class="mono">Started</dt><dd>{{ startedAt | date:'shortTime' }}</dd></div>
              <div><dt class="mono">{{ job.completed_at ? 'Finished' : 'Elapsed' }}</dt>
                   <dd>{{ job.completed_at ? (finishedAt | date:'shortTime') : elapsed }}</dd></div>
            </dl>

            <button
              *ngIf="canDownload"
              type="button"
              class="cf-btn-primary dl-btn-block"
              (click)="downloadDeliverable(job)">
              ↓ Download {{ getArtifactFilename(job) }}
            </button>

            <p class="fail-note" *ngIf="isFailed">{{ job.stage_label || job.current_step }}</p>
          </aside>
        </div>
      </ng-container>
    </div>
  `,
  styles: [`
    .jp {
      display: flex;
      flex-direction: column;
      gap: 20px;
      max-width: 1180px;
      margin: 0 auto;
      padding: 30px 32px 52px;
    }

    .mono { font-family: var(--cf-font-mono); }

    .eyebrow {
      font-family: var(--cf-font-mono);
      font-size: 9.5px;
      letter-spacing: .16em;
      text-transform: uppercase;
      color: var(--cf-text-faint);
    }

    /* — loading / error — */
    .state-card {
      display: flex; align-items: center; gap: 14px; padding: 22px 24px;
      color: var(--cf-text-2); font-size: 13.5px;
    }
    .state-card.error { border-color: rgba(248, 113, 113, .25); background: rgba(248, 113, 113, .06); }
    .state-card h3 { margin: 0 0 4px; font-size: 14px; color: var(--cf-text); }
    .state-card p { margin: 0; font-size: 12.5px; color: var(--cf-text-muted); }
    .err-icon { font-size: 20px; color: var(--cf-err-soft); }
    .ghost-btn {
      margin-left: auto; height: 34px; padding: 0 14px; border-radius: 10px;
      border: 1px solid var(--cf-border-strong); display: inline-flex; align-items: center;
      font-size: 12.5px; color: var(--cf-text-2);
    }
    .ghost-btn:hover { background: rgba(255, 255, 255, .06); color: var(--cf-text); }
    .state-card .cf-spinner { width: 20px; height: 20px; }

    /* — breadcrumb — */
    .crumbs { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--cf-text-muted); }
    .crumbs a { color: inherit; transition: color .15s ease; }
    .crumbs a:hover { color: var(--cf-text); }
    .crumbs .sep { color: #3E3E4C; }
    .crumbs .mono { font-size: 11.5px; color: var(--cf-text-2); }

    /* — job header card — */
    .job-card {
      position: relative; overflow: hidden;
      border-radius: 18px;
      border: 1px solid var(--cf-border-card);
      background: linear-gradient(150deg, rgba(28, 22, 52, .72), rgba(14, 14, 22, .82) 58%, rgba(12, 18, 32, .78));
      padding: 22px 24px 20px;
    }
    .job-card-wash {
      position: absolute; inset: 0; pointer-events: none;
      background: radial-gradient(closest-side at 12% 0%, rgba(124, 92, 255, .22), transparent 70%);
    }
    .job-card-body { position: relative; display: flex; flex-direction: column; gap: 18px; }

    .job-top { display: flex; align-items: flex-start; gap: 18px; flex-wrap: wrap; }
    .job-ident { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
    .badges { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
    .badge {
      font-family: var(--cf-font-mono); font-size: 9.5px; letter-spacing: .14em;
      text-transform: uppercase; padding: 5px 10px; border-radius: 6px;
      border: 1px solid var(--cf-border-card); background: rgba(255, 255, 255, .03); color: var(--cf-text-3);
    }
    .badge-accent {
      border-color: rgba(146, 118, 255, .4);
      background: rgba(124, 92, 255, .16);
      color: var(--cf-accent-link-hover);
    }
    .job-ident h1 {
      margin: 0; font-size: 30px; font-weight: 600; letter-spacing: -.026em; line-height: 1.12;
    }
    .grad {
      background: linear-gradient(100deg, #C6BCFF, #8FB6FF);
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }
    .meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--cf-text-muted); }
    .meta .mono { font-size: 11.5px; color: var(--cf-text-2); }
    .meta .dot { color: #3E3E4C; }

    .job-actions { margin-left: auto; display: flex; flex-direction: column; align-items: flex-end; gap: 12px; }

    .dl-btn-block { width: 100%; margin-top: 12px; }

    /* — prompt — */
    .prompt {
      display: flex; gap: 14px; padding: 15px 17px; border-radius: 13px;
      border: 1px solid var(--cf-border-soft); background: rgba(8, 8, 14, .5);
    }
    .prompt-rule { width: 2px; flex: none; border-radius: 2px; background: linear-gradient(180deg, #7C5CFF, #3B82F6); }
    .prompt-body { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
    .prompt-body p {
      margin: 0; font-size: 13.6px; line-height: 1.62; color: #C4C4D2;
      overflow-wrap: anywhere;
    }

    /* — overall progress — */
    .overall { display: flex; flex-direction: column; gap: 11px; }
    .overall-head { display: flex; align-items: flex-end; gap: 14px; flex-wrap: wrap; }
    .overall-titles { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .headline { font-size: 13.5px; font-weight: 600; }
    .sub { font-size: 12px; color: var(--cf-text-dim); }
    .pct {
      margin-left: auto; font-size: 30px; font-weight: 600; letter-spacing: -.03em; line-height: 1;
      background: linear-gradient(100deg, #C6BCFF, #8FB6FF);
      -webkit-background-clip: text; background-clip: text; color: transparent;
    }

    .ticks { display: flex; gap: 5px; }
    .tick { flex: 1; height: 3px; border-radius: 99px; background: rgba(255, 255, 255, .08); transition: background .4s ease; }
    .tick-active { background: rgba(146, 118, 255, .85); }
    .tick-done { background: var(--cf-ok); }
    .tick-failed { background: var(--cf-err); }

    /* — two-column body — */
    .cols { display: grid; grid-template-columns: 1.45fr 1fr; gap: 16px; align-items: start; }
    @media (max-width: 1000px) { .cols { grid-template-columns: 1fr; } }

    .panel-count { font-size: 10.5px; color: var(--cf-text-dimmer); }

    /* — pipeline rows — */
    .rows { display: flex; flex-direction: column; gap: 7px; }
    .row {
      position: relative; display: grid; grid-template-columns: 44px 1fr; gap: 14px;
      padding: 13px 14px; border-radius: 13px;
      border: 1px solid var(--cf-border); background: rgba(255, 255, 255, .018);
      transition: border-color .35s ease, background .35s ease;
    }
    .row-active {
      border-color: rgba(146, 118, 255, .5);
      animation: cfRowGlow 2.4s ease-in-out infinite;
    }
    .row-done { border-color: rgba(52, 211, 153, .16); background: rgba(52, 211, 153, .045); }
    .row-failed { border-color: rgba(248, 113, 113, .35); background: rgba(248, 113, 113, .07); }

    .row-icon {
      position: relative; width: 44px; height: 44px; border-radius: 12px;
      display: grid; place-items: center;
      border: 1px solid var(--cf-border-card); background: rgba(255, 255, 255, .035);
      color: #5E5E70; transition: all .35s ease;
    }
    .row-active .row-icon {
      border-color: rgba(146, 118, 255, .55); background: rgba(124, 92, 255, .2);
      color: var(--cf-accent-link-hover);
      animation: cfHalo 2s ease-in-out infinite;
    }
    .row-done .row-icon { border-color: rgba(52, 211, 153, .32); background: rgba(52, 211, 153, .1); color: var(--cf-ok); }
    .row-failed .row-icon { border-color: rgba(248, 113, 113, .4); background: rgba(248, 113, 113, .12); color: var(--cf-err-soft); }

    .check {
      position: absolute; right: -4px; bottom: -4px; width: 17px; height: 17px;
      border-radius: 50%; background: var(--cf-ok); border: 2px solid #0C0C13;
      display: grid; place-items: center;
    }
    .check::after {
      content: ''; width: 6px; height: 3px;
      border-left: 1.6px solid #062B20; border-bottom: 1.6px solid #062B20;
      transform: rotate(-45deg); margin-top: -1px;
    }

    .row-body { min-width: 0; display: flex; flex-direction: column; gap: 5px; }
    .row-head { display: flex; align-items: center; gap: 10px; }
    .row-name { font-size: 13.8px; font-weight: 600; color: var(--cf-text-dim); transition: color .35s ease; }
    .row-active .row-name, .row-done .row-name, .row-failed .row-name { color: var(--cf-text); }

    .tag {
      font-size: 9.5px; letter-spacing: .1em; text-transform: uppercase;
      padding: 2px 7px; border-radius: 5px;
      border: 1px solid var(--cf-border-card); background: rgba(255, 255, 255, .03);
      color: #63637A; transition: all .35s ease;
    }
    .row-active .tag { border-color: rgba(146, 118, 255, .45); background: rgba(124, 92, 255, .16); color: var(--cf-accent-link-hover); }
    .row-done .tag { border-color: rgba(52, 211, 153, .3); background: rgba(52, 211, 153, .1); color: var(--cf-ok-soft); }
    .row-failed .tag { border-color: rgba(248, 113, 113, .35); background: rgba(248, 113, 113, .12); color: var(--cf-err-soft); }

    .row-time { margin-left: auto; font-size: 10.5px; color: var(--cf-text-faintest); }
    .row-active .row-time { color: var(--cf-accent-link-hover); }
    .row-done .row-time { color: var(--cf-text-dimmer); }

    .row-detail { font-size: 12.2px; line-height: 1.5; color: #63637A; transition: color .35s ease; }
    .row-active .row-detail { color: var(--cf-text-2); }
    .row-done .row-detail { color: var(--cf-text-muted); }

    .row-bar { margin-top: 3px; height: 4px; border-radius: 99px; background: rgba(255, 255, 255, .07); overflow: hidden; }
    .row-bar-fill {
      height: 100%; border-radius: 99px;
      background: linear-gradient(90deg, #7C5CFF, #3B82F6);
      box-shadow: 0 0 10px rgba(124, 92, 255, .55);
      transition: width .6s ease;
    }

    /* Activity indicator on the running stage — motion only, no data claimed. */
    .eq { display: flex; align-items: flex-end; gap: 3px; height: 12px; margin-top: 4px; }
    .eq span {
      width: 3px; height: 100%; border-radius: 2px; transform-origin: bottom;
      background: linear-gradient(180deg, rgba(198, 188, 255, .9), rgba(124, 92, 255, .35));
      animation: cfBars 1.05s ease-in-out infinite;
    }

    /* — deliverable panel — */
    .preview {
      position: relative; aspect-ratio: 16 / 9; border-radius: 13px; overflow: hidden;
      border: 1px solid var(--cf-border-soft);
      background: linear-gradient(140deg, #141225, #1D1533 55%, #101A28);
    }
    .preview-done { background: linear-gradient(140deg, #0F2019, #12281F 55%, #0E1C2A); }
    .preview-grid {
      position: absolute; inset: 0;
      background-image: repeating-linear-gradient(118deg, rgba(255, 255, 255, .045) 0 1px, transparent 1px 13px);
    }
    .preview-wash {
      position: absolute; inset: 0;
      background: radial-gradient(closest-side at 62% 44%, rgba(124, 92, 255, .3), transparent);
    }
    .preview-sheen span { width: 34%; animation: cfShimmer 3s ease-in-out infinite; }
    .preview-center {
      position: absolute; inset: 0; display: flex; flex-direction: column;
      align-items: center; justify-content: center; gap: 13px;
    }
    .preview-label {
      font-size: 10.5px; letter-spacing: .12em; text-transform: uppercase; color: var(--cf-text-2);
    }
    .preview-tick {
      width: 44px; height: 44px; border-radius: 50%; background: rgba(52, 211, 153, .16);
      border: 2px solid var(--cf-ok); display: grid; place-items: center;
      animation: cfRise .35s ease both;
    }
    .preview-tick::after {
      content: ''; width: 14px; height: 7px;
      border-left: 2.2px solid var(--cf-ok); border-bottom: 2.2px solid var(--cf-ok);
      transform: rotate(-45deg); margin-top: -3px;
    }
    .preview-cross {
      width: 44px; height: 44px; border-radius: 50%; background: rgba(248, 113, 113, .16);
      border: 2px solid var(--cf-err); display: grid; place-items: center;
      color: var(--cf-err-soft); font-size: 22px; font-weight: 700;
    }

    .facts { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin: 14px 0 0; }
    .facts > div {
      padding: 11px 12px; border-radius: 12px; border: 1px solid var(--cf-border-soft);
      background: linear-gradient(160deg, rgba(255, 255, 255, .035), rgba(255, 255, 255, .01));
    }
    .facts dt { font-size: 9px; letter-spacing: .14em; text-transform: uppercase; color: var(--cf-text-dimmer); }
    .facts dd { margin: 6px 0 0; font-size: 14.5px; font-weight: 600; letter-spacing: -.02em; }

    .fail-note {
      margin: 12px 0 0; font-size: 12.2px; line-height: 1.5; color: var(--cf-err-soft);
      overflow-wrap: anywhere;
    }
  `]
})
export class JobDetailComponent implements OnInit, OnDestroy {
  job: Job | null = null;
  isLoading = true;
  errorMessage = '';
  private pollSub?: Subscription;

  /** Eased width of the bar. Stages arrive as jumps (10 -> 25 -> 45); this catches up to
   *  each one over a few frames so the bar slides instead of snapping. */
  displayProgress = 0;
  private targetProgress = 0;
  private rafId?: number;
  /** False until the first server response has been rendered. */
  private hasPainted = false;

  /** Ticks once a second so "elapsed" advances even between polls. */
  private clockSub?: Subscription;

  readonly eqBars = [0, 1, 2, 3, 4];

  /**
   * The six visible stages. Thresholds mirror the backend's progress table, so a stage
   * lights up exactly when the server reports that phase -- nothing is simulated here.
   */
  readonly stages: PipelineStage[] = [
    { key: 'director',    name: 'AI Director',      start: 10,  end: 25,  detail: 'Planning the shot list, scene count and duration budget.' },
    { key: 'writer',      name: 'Screenwriter',     start: 25,  end: 45,  detail: 'Writing the narration and on-screen titles for each beat.' },
    { key: 'voice',       name: 'Voice Generation', start: 45,  end: 65,  detail: 'Synthesising narration and measuring real scene timings.' },
    { key: 'media',       name: 'Media Collection', start: 65,  end: 85,  detail: 'Fetching and ranking stock footage for every scene.' },
    { key: 'compositing', name: 'Compositing',      start: 85,  end: 100, detail: 'Assembling scenes, captions and the mixed soundtrack.' },
    { key: 'complete',    name: 'Complete',         start: 100, end: 100, detail: 'Master encoded, decoded end to end and validated.' }
  ];

  constructor(
    private route: ActivatedRoute,
    private jobService: JobService,
    private credits: CreditsService,
    private zone: NgZone
  ) {}

  // ---------------------------------------------------------------- progress

  /** Guarded width for the bar, unrounded so the ease stays smooth sub-pixel. */
  get barWidth(): number {
    return toPercent(this.displayProgress);
  }

  get roundedProgress(): number {
    return Math.round(this.barWidth);
  }

  get stageLabel(): string {
    // Reports the queued state from the animated value, not the raw field, so the label
    // stops saying "Queued..." at the same moment the bar starts moving.
    return this.roundedProgress === 0 ? jobStageLabel(this.job) : (this.job?.stage_label || this.job?.current_step || '');
  }

  /** Reads the server's percentage and starts easing toward it. */
  private applyJob(job: Job): void {
    this.job = job;
    this.isLoading = false;
    this.targetProgress = jobPercent(job);

    // The ease exists to show progress *advancing*; on first paint there is nothing to
    // advance from. Animating 0 -> 100 when opening a finished job leaves the header
    // reading "Pipeline complete" while the bar and the stage rows are still climbing
    // through the earlier stages. Snap instead, then ease every later update.
    if (!this.hasPainted) {
      this.hasPainted = true;
      this.displayProgress = this.targetProgress;
      return;
    }
    this.startAnimation();
  }

  private startAnimation(): void {
    if (this.rafId !== undefined) {
      return;
    }
    // Outside Angular: this ticks ~60x/s and would trigger change detection on every
    // frame. Re-entry happens only when the eased value actually changes.
    this.zone.runOutsideAngular(() => {
      const step = () => {
        // Self-heal: if displayProgress was ever poisoned, restart the ease from a real
        // number instead of propagating NaN forward.
        if (!Number.isFinite(this.displayProgress)) {
          this.displayProgress = 0;
        }
        const delta = this.targetProgress - this.displayProgress;
        if (!Number.isFinite(delta) || Math.abs(delta) < 0.1) {
          this.displayProgress = this.targetProgress;
          this.rafId = undefined;
          this.zone.run(() => {});
          return;
        }
        // Exponential ease: fast at the start of a jump, gentle as it lands.
        this.displayProgress += delta * 0.08;
        this.rafId = requestAnimationFrame(step);
        this.zone.run(() => {});
      };
      this.rafId = requestAnimationFrame(step);
    });
  }

  // ------------------------------------------------------------------ status

  get isRunning(): boolean {
    return this.job?.status === 'RUNNING' || this.job?.status === 'QUEUED';
  }

  get isComplete(): boolean {
    return this.job?.status === 'COMPLETED';
  }

  get isFailed(): boolean {
    return this.job?.status === 'FAILED';
  }

  get chipTone(): string {
    if (this.isComplete) return 'ok';
    if (this.isFailed) return 'err';
    if (this.job?.status === 'RUNNING') return 'run';
    return 'idle';
  }

  /** The download button appears only once the server has a validated artifact. */
  get canDownload(): boolean {
    return this.isComplete && !!this.job?.artifact_path;
  }

  // ------------------------------------------------------------------ stages

  /**
   * Maps the reported percentage onto one row's state.
   *
   * Driven by the eased value rather than the raw field so a row lights up in step with
   * the bar reaching it, instead of a frame ahead of the fill.
   */
  stateOf(s: PipelineStage): StageState {
    const p = this.roundedProgress;
    if (this.isFailed && p >= s.start && p < s.end) {
      return 'failed';
    }
    if (s.start === s.end) {
      // The terminal row: done only once the server actually says COMPLETED, so a
      // rounding artefact at 99.6% cannot show a green check on an unfinished job.
      return this.isComplete ? 'done' : 'pending';
    }
    if (p >= s.end) return 'done';
    if (p >= s.start) return 'active';
    return 'pending';
  }

  /** How far through its own range the active stage is, for the in-row bar. */
  stageFraction(s: PipelineStage): number {
    const span = s.end - s.start;
    if (span <= 0) return 0;
    return toPercent(((this.roundedProgress - s.start) / span) * 100);
  }

  stageTime(s: PipelineStage): string {
    const state = this.stateOf(s);
    if (state === 'done') return '✓';
    if (state === 'failed') return 'failed';
    if (state === 'active') return Math.round(this.stageFraction(s)) + '%';
    return '—';
  }

  get doneCount(): number {
    return this.stages.filter(s => this.stateOf(s) === 'done').length;
  }

  get activeStage(): PipelineStage | undefined {
    return this.stages.find(s => this.stateOf(s) === 'active' || this.stateOf(s) === 'failed');
  }

  /** 1-based index for "Stage N of 6", clamped so a finished job reads 6. */
  get displayStageNumber(): number {
    if (this.isComplete) return this.stages.length;
    const active = this.activeStage;
    return active ? this.stages.indexOf(active) + 1 : Math.max(1, this.doneCount + 1);
  }

  get headline(): string {
    if (this.isComplete) return 'Pipeline complete — artifact validated';
    if (this.isFailed) return 'Run failed';
    const active = this.activeStage;
    return active ? `${active.name} is working` : 'Queued';
  }

  get previewLabel(): string {
    if (this.isComplete) return 'master ready';
    if (this.isFailed) return 'run failed';
    return this.activeStage?.name || 'starting';
  }

  // ------------------------------------------------------------------- times

  /**
   * The API sends naive UTC timestamps with no zone suffix, which `new Date()` would
   * read as local time and offset elapsed by the whole UTC offset.
   */
  private asUtc(value?: string | null): Date | null {
    if (!value) return null;
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
    const d = new Date(hasZone ? value : value + 'Z');
    return isNaN(d.getTime()) ? null : d;
  }

  get startedAt(): Date | null {
    return this.asUtc(this.job?.created_at);
  }

  get finishedAt(): Date | null {
    return this.asUtc(this.job?.completed_at);
  }

  get elapsed(): string {
    const start = this.startedAt;
    if (!start) return '—';
    const end = this.finishedAt ?? new Date();
    const secs = Math.max(0, Math.floor((end.getTime() - start.getTime()) / 1000));
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  get shortTitle(): string {
    if (this.job?.title) {
      return this.job.title;
    }
    // Fallback for jobs created before the server generated titles.
    const prompt = (this.job?.prompt || '').trim();
    if (!prompt) return 'your deliverable';
    // Storyboard jobs arrive as a JSON blob in `prompt`; show its title, not the JSON.
    if (prompt.startsWith('{')) {
      try {
        const parsed = JSON.parse(prompt);
        if (parsed?.title) return String(parsed.title).slice(0, 52);
      } catch {
        /* fall through to the plain-text path */
      }
    }
    const words = prompt.split(/\s+/).slice(0, 7).join(' ');
    return words.length < prompt.length ? words + '…' : words;
  }

  // ------------------------------------------------------------- lifecycle

  ngOnInit() {
    const jobId = this.route.snapshot.paramMap.get('id');
    if (!jobId) {
      this.isLoading = false;
      this.errorMessage = 'No Job ID provided.';
      return;
    }

    // Start status polling
    this.pollSub = interval(1000)
      .pipe(
        switchMap(() => this.jobService.getJob(jobId))
      )
      .subscribe({
        next: (job) => {
          this.applyJob(job);
          // Stop polling if completed or failed
          if (job.status === 'COMPLETED' || job.status === 'FAILED') {
            this.pollSub?.unsubscribe();
            this.clockSub?.unsubscribe();
            // The balance only moves at this moment -- a credit is debited on success and
            // released on failure -- so this is where the sidebar card has to catch up.
            this.credits.refreshQuiet();
          }
        },
        error: (err) => {
          this.isLoading = false;
          this.errorMessage = err.error?.detail || `Job #${jobId} not found.`;
          this.pollSub?.unsubscribe();
          this.clockSub?.unsubscribe();
        }
      });

    // Keeps the elapsed counter moving; polling alone would freeze it after the job ends,
    // which is correct, but a stalled poll should not freeze it mid-run.
    this.clockSub = interval(1000).subscribe(() => {});

    // Initial fetch
    this.jobService.getJob(jobId).subscribe({
      next: (job) => this.applyJob(job),
      error: (err) => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || `Job #${jobId} not found.`;
      }
    });
  }

  ngOnDestroy() {
    this.pollSub?.unsubscribe();
    this.clockSub?.unsubscribe();
    if (this.rafId !== undefined) {
      cancelAnimationFrame(this.rafId);
    }
  }

  getAgentLabel(agentType: string): string {
    switch (agentType) {
      case 'presentation': return 'Presentation Agent';
      case 'latex': return 'LaTeX Report Agent';
      case 'video': return 'Video Montage Agent';
      default: return agentType;
    }
  }

  getDownloadUrl(jobId: string): string {
    return this.jobService.getArtifactUrl(jobId);
  }

  getArtifactFilename(job: Job): string {
    if (job.agent_type === 'presentation') return 'presentation_demo.pptx';
    if (job.agent_type === 'latex') return 'report_demo.pdf';
    if (job.agent_type === 'video') return 'video_demo.mp4';
    return 'deliverable';
  }

  downloadDeliverable(job: Job) {
    this.jobService.downloadArtifact(job.id).subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = this.getArtifactFilename(job);
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        console.error('Artifact download error:', err);
        window.open(this.getDownloadUrl(job.id), '_blank');
      }
    });
  }
}
