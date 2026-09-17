import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { JobService } from '../../services/job.service';
import { CreditsService } from '../../services/credits.service';
import { BrandKitService } from '../../services/brand-kit.service';
import { AgentType } from '../../models/job.model';

interface AgentCard {
  id: AgentType;
  name: string;
  desc: string;
  tags: string[];
  glyph: string;
  glyphRadius: string;
}

interface Starter {
  label: string;
  agent: AgentType;
  text: string;
}

interface LanguageOption {
  code: string;
  label: string;
  /**
   * Voice names shown in the Output panel, mirroring agents/video/language.py. Kept here
   * only so the panel can name the voice the render will actually use -- the backend
   * resolves the real voice + phonemiser pair itself and never trusts these strings.
   */
  kokoroVoice: string;
  edgeVoice: string;
}

interface VoiceOption {
  id: string;
  name: string;
  detail: string;
}

@Component({
  selector: 'app-create-job',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page">
      <div class="wrap">

        <!-- ============ HERO ============ -->
        <div class="hero">
          <span class="cf-eyebrow">New deliverable</span>
          <h1 class="hero-title">What are we making today?</h1>
          <p class="hero-sub">
            Pick an agent crew, describe the outcome, and drop in any brand material.
            CreateFlow orchestrates the rest.
          </p>
        </div>

        <!-- ============ 01 AGENT CREW ============ -->
        <section class="section">
          <div class="section-head">
            <span class="step-num cf-mono">01</span>
            <span class="section-title">Agent crew</span>
            <span class="section-note">— determines the pipeline that runs</span>
          </div>
          <div class="agent-grid">
            <div
              *ngFor="let a of agents"
              class="agent-card"
              [class.selected]="selectedAgent === a.id"
              role="radio"
              [attr.aria-checked]="selectedAgent === a.id"
              tabindex="0"
              (click)="selectedAgent = a.id"
              (keydown.enter)="selectedAgent = a.id"
              (keydown.space)="$event.preventDefault(); selectedAgent = a.id"
            >
              <div class="agent-top">
                <div class="agent-icon">
                  <div class="agent-glyph"
                       [style.background]="a.glyph"
                       [style.borderRadius]="a.glyphRadius"></div>
                </div>
                <div class="agent-radio">
                  <div class="agent-radio-dot"></div>
                </div>
              </div>
              <div class="agent-name">{{ a.name }}</div>
              <div class="agent-desc">{{ a.desc }}</div>
              <div class="agent-tags">
                <span class="tag cf-mono" *ngFor="let t of a.tags">{{ t }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- ============ 02 CREATIVE BRIEF ============ -->
        <section class="section">
          <div class="section-head">
            <span class="step-num cf-mono">02</span>
            <span class="section-title">Creative brief</span>
            <span class="char-count cf-mono">{{ prompt.length }} / {{ MAX_PROMPT }}</span>
          </div>
          <div class="brief">
            <textarea
              class="brief-input"
              rows="5"
              [maxlength]="MAX_PROMPT"
              [(ngModel)]="prompt"
              placeholder="A 45-second launch film for our AI research assistant. Confident, cinematic, minimal. Open on a dark studio product shot, cut to three benefit beats, close on the logo lockup."
              aria-label="Creative brief"
            ></textarea>
            <div class="brief-foot">
              <span class="starters-label cf-mono">Starters</span>
              <button
                type="button"
                class="starter"
                *ngFor="let s of starters"
                (click)="useStarter(s)"
              >{{ s.label }}</button>
            </div>
          </div>
        </section>

        <!-- ============ 03 SOURCE + 04 OUTPUT ============ -->
        <section class="split">
          <!-- 03 Source material -->
          <div class="col">
            <div class="section-head">
              <span class="step-num cf-mono">03</span>
              <span class="section-title">Source material</span>
              <span class="section-note" *ngIf="selectedAgent !== 'video'">— video agent only</span>
            </div>

            <div
              class="drop"
              [class.dragging]="isDragging"
              [class.disabled]="!uploadsAllowed"
              (dragover)="onDragOver($event)"
              (dragleave)="onDragLeave($event)"
              (drop)="onDrop($event)"
              (click)="uploadsAllowed && fileInput.click()"
              role="button"
              tabindex="0"
              (keydown.enter)="uploadsAllowed && fileInput.click()"
            >
              <input
                #fileInput
                type="file"
                class="hidden-input"
                multiple
                accept=".mp4,.mov,.webm,video/mp4,video/quicktime,video/webm"
                (change)="onFileInputChange($event)"
              />
              <div class="drop-icon">
                <div class="drop-plus"><div class="drop-plus-v"></div></div>
              </div>
              <div class="drop-title">{{ dropTitle }}</div>
              <div class="drop-hint">
                MP4, MOV or WEBM — up to {{ MAX_FILES }} files, {{ MAX_SIZE_MB }} MB each
              </div>
            </div>

            <div class="files" *ngIf="selectedFiles.length > 0">
              <div class="file" *ngFor="let f of selectedFiles; let i = index">
                <div class="file-thumb"></div>
                <div class="file-meta">
                  <div class="file-name" [title]="f.name">{{ f.name }}</div>
                  <div class="file-size cf-mono">{{ formatSize(f.size) }} · {{ f.type || 'video' }}</div>
                </div>
                <button
                  type="button"
                  class="file-remove"
                  [disabled]="isSubmitting"
                  (click)="removeFile(i); $event.stopPropagation()"
                  aria-label="Remove file"
                >×</button>
              </div>
            </div>

            <div class="warn" *ngIf="fileWarnings.length > 0">
              <div *ngFor="let w of fileWarnings">{{ w }}</div>
            </div>
          </div>

          <!-- 04 Output -->
          <div class="col">
            <div class="section-head">
              <span class="step-num cf-mono">04</span>
              <span class="section-title">Output</span>
            </div>
            <div class="output">
              <div class="field" *ngIf="isVideo">
                <span class="field-label">Aspect ratio</span>
                <div class="pills">
                  <button
                    type="button"
                    class="pill cf-mono"
                    *ngFor="let r of ratios"
                    [class.on]="aspectRatio === r"
                    (click)="aspectRatio = r"
                  >{{ r }}</button>
                </div>
              </div>

              <div class="field" *ngIf="isVideo">
                <span class="field-label">Target length</span>
                <div class="pills">
                  <button
                    type="button"
                    class="pill cf-mono"
                    *ngFor="let l of lengths"
                    [class.on]="targetLength === l.label"
                    (click)="targetLength = l.label"
                  >{{ l.label }}</button>
                </div>
              </div>

              <!-- Not video-only: a report's language decides what the LLM writes the
                   chapters in, and what the chrome (Table des matieres, Resume,
                   References) says. -->
              <div class="field">
                <span class="field-label">Language</span>
                <div class="pills">
                  <button
                    type="button"
                    class="pill"
                    *ngFor="let l of languages"
                    [class.on]="videoLanguage === l.code"
                    [attr.aria-pressed]="videoLanguage === l.code"
                    (click)="videoLanguage = l.code"
                  >{{ l.label }}</button>
                </div>
              </div>

              <!-- Only actionable once a kit exists; otherwise it points at the page
                   where one is made, rather than being an inert dead toggle. -->
              <div class="field brand-field" *ngIf="isVideo">
                <label class="cf-check" [class.disabled]="!brand.hasKit()">
                  <input
                    type="checkbox"
                    [(ngModel)]="useBrandKit"
                    [disabled]="!brand.hasKit()" />
                  <span class="cf-check-box" aria-hidden="true"></span>
                  <span class="brand-text">
                    <span class="brand-name">Use my brand kit</span>
                    <span class="brand-detail cf-mono">{{ brandDetail }}</span>
                  </span>
                </label>
                <span class="brand-swatches" *ngIf="brand.kit() as k">
                  <span class="brand-dot" [style.background]="k.primary_color" title="Primary"></span>
                  <span class="brand-dot" [style.background]="k.secondary_color" title="Secondary"></span>
                  <span class="brand-dot" [style.background]="k.accent_color" title="Accent"></span>
                </span>
                <a routerLink="/brand-kit" class="brand-link">{{ brand.hasKit() ? 'Edit' : 'Set up' }}</a>
              </div>

              <div class="voice-row" *ngIf="isVideo">
                <div class="voice-text">
                  <span class="voice-name">Narration voice</span>
                  <span class="voice-detail cf-mono">{{ activeVoiceDetail }}</span>
                </div>
                <button type="button" class="voice-change" (click)="cycleVoice()">Change</button>
              </div>

              <!-- PFE cover page. Optional: anything left blank renders as a bracketed
                   placeholder in the PDF ("[Nom de l'etudiant]"), so the student can see
                   exactly which blanks remain rather than the generator inventing a name. -->
              <div class="cover" *ngIf="isReport">
                <div class="cover-head">
                  <span class="field-label">Cover page</span>
                  <span class="cover-note">Optional — blanks show as placeholders</span>
                </div>
                <input class="cover-input" type="text" maxlength="160"
                       [(ngModel)]="coverStudentName" [placeholder]="coverPlaceholders.student" />
                <input class="cover-input" type="text" maxlength="160"
                       [(ngModel)]="coverUniversity" [placeholder]="coverPlaceholders.university" />
                <div class="cover-row">
                  <input class="cover-input" type="text" maxlength="160"
                         [(ngModel)]="coverSupervisor" [placeholder]="coverPlaceholders.supervisor" />
                  <input class="cover-input" type="text" maxlength="160"
                         [(ngModel)]="coverAcademicYear" [placeholder]="coverPlaceholders.year" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- ============ OUT OF CREDITS ============ -->
        <div class="nocredits" *ngIf="credits.isOutOfCredits()">
          <div class="nocredits-text">
            <span class="nocredits-title">{{ outOfCreditsTitle }}</span>
            <span class="nocredits-sub">{{ outOfCreditsDetail }}</span>
          </div>
          <a routerLink="/pricing" class="nocredits-cta">See plans</a>
        </div>

        <!-- ============ GENERATE BAR ============ -->
        <div class="genbar">
          <div class="genbar-text">
            <span class="genbar-summary">{{ summaryLine }}</span>
            <span class="genbar-est cf-mono">{{ estimateLine }}</span>
          </div>
          <button
            type="button"
            class="generate"
            [disabled]="isSubmitting || !prompt.trim() || credits.isOutOfCredits()"
            [title]="credits.isOutOfCredits() ? outOfCreditsTitle : ''"
            (click)="onSubmit()"
          >
            <ng-container *ngIf="!isSubmitting">
              Generate
              <span class="generate-kbd cf-mono">⌘⏎</span>
            </ng-container>
            <ng-container *ngIf="isSubmitting">
              <span class="spinner"></span>{{ submitStatus }}
            </ng-container>
          </button>
        </div>

        <div class="error" *ngIf="errorMessage">⚠️ {{ errorMessage }}</div>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 40px 32px 56px; }
    .wrap {
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 30px;
    }

    /* — Hero — */
    .hero { display: flex; flex-direction: column; gap: 9px; }
    .hero-title {
      margin: 0;
      font-size: 34px;
      font-weight: 600;
      letter-spacing: -.025em;
      line-height: 1.1;
      color: var(--cf-text);
    }
    .hero-sub {
      margin: 0;
      font-size: 14.5px;
      color: var(--cf-text-muted);
      max-width: 560px;
      text-wrap: pretty;
    }

    /* — Section scaffolding — */
    .section { display: flex; flex-direction: column; gap: 13px; }
    .section-head { display: flex; align-items: baseline; gap: 10px; }
    .step-num { font-size: 10px; color: var(--cf-text-faint); }
    .section-title { font-size: 13.5px; font-weight: 600; }
    .section-note { font-size: 12px; color: var(--cf-text-dimmer); }
    .char-count { margin-left: auto; font-size: 10.5px; color: var(--cf-text-dimmer); }

    /* — 01 Agent cards — */
    .agent-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 13px;
    }
    .agent-card {
      position: relative;
      padding: 17px 16px 15px;
      border-radius: var(--cf-radius-lg);
      cursor: pointer;
      overflow: hidden;
      border: 1px solid var(--cf-border-card);
      background: var(--cf-surface-card);
      box-shadow: 0 1px 0 rgba(255, 255, 255, .02);
      transition: transform .18s cubic-bezier(.2, .7, .3, 1), border-color .18s ease, box-shadow .18s ease, background .18s ease;
    }
    .agent-card:hover { transform: translateY(-3px); }
    .agent-card:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }
    .agent-card.selected {
      border-color: var(--cf-border-accent);
      background: linear-gradient(160deg, rgba(124, 92, 255, .17), rgba(59, 130, 246, .07));
      box-shadow: 0 14px 34px rgba(92, 80, 255, .26);
    }
    .agent-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 13px;
    }
    .agent-icon {
      width: 34px; height: 34px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      background: rgba(255, 255, 255, .04);
      border: 1px solid rgba(255, 255, 255, .08);
      transition: background .18s ease;
    }
    .agent-card.selected .agent-icon { background: rgba(255, 255, 255, .08); }
    .agent-glyph { width: 12px; height: 12px; }
    .agent-radio {
      width: 17px; height: 17px;
      border-radius: 50%;
      border: 1.5px solid rgba(255, 255, 255, .18);
      display: grid;
      place-items: center;
      flex: none;
      transition: border-color .18s ease;
    }
    .agent-card.selected .agent-radio { border-color: var(--cf-accent-ring); }
    .agent-radio-dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: var(--cf-accent-grad);
      opacity: 0;
      transition: opacity .18s ease;
    }
    .agent-card.selected .agent-radio-dot { opacity: 1; }
    .agent-name { font-size: 14px; font-weight: 600; margin-bottom: 5px; }
    .agent-desc {
      font-size: 12.3px;
      line-height: 1.5;
      color: var(--cf-text-muted);
      min-height: 37px;
      text-wrap: pretty;
    }
    .agent-tags { display: flex; gap: 6px; margin-top: 12px; flex-wrap: wrap; }
    .tag {
      font-size: 9.5px;
      letter-spacing: .06em;
      padding: 3px 7px;
      border-radius: 5px;
      background: rgba(255, 255, 255, .05);
      color: var(--cf-text-3);
    }

    /* — 02 Brief — */
    .brief {
      border-radius: var(--cf-radius-lg);
      border: 1px solid var(--cf-border-card);
      background: var(--cf-surface-input);
      overflow: hidden;
    }
    .brief-input {
      width: 100%;
      display: block;
      padding: 17px 18px;
      background: transparent;
      border: none;
      outline: none;
      resize: none;
      color: var(--cf-text);
      font-size: 14px;
      line-height: 1.6;
    }
    .brief-foot {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 11px 14px;
      border-top: 1px solid var(--cf-border);
      background: rgba(255, 255, 255, .015);
      flex-wrap: wrap;
    }
    .starters-label {
      font-size: 9.5px;
      letter-spacing: .14em;
      color: var(--cf-text-faint);
      text-transform: uppercase;
    }
    .starter {
      all: unset;
      font-size: 11.5px;
      padding: 5px 10px;
      border-radius: 99px;
      border: 1px solid var(--cf-border-card);
      color: var(--cf-text-2);
      cursor: pointer;
      transition: all .15s ease;
    }
    .starter:hover {
      border-color: rgba(124, 92, 255, .55);
      color: var(--cf-accent-on-pill);
      background: rgba(124, 92, 255, .1);
    }
    .starter:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }

    /* — 03 / 04 split — */
    .split {
      display: grid;
      grid-template-columns: 1.35fr 1fr;
      gap: 13px;
      align-items: start;
    }
    .col { display: flex; flex-direction: column; gap: 13px; }

    /* — Dropzone — */
    .drop {
      border-radius: var(--cf-radius-lg);
      border: 1.5px dashed var(--cf-border-strong);
      background: rgba(255, 255, 255, .018);
      padding: 26px 20px;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      transition: all .18s ease;
      text-align: center;
    }
    .drop:hover:not(.disabled) { border-color: rgba(124, 92, 255, .45); }
    .drop.dragging {
      border-color: var(--cf-accent-ring);
      background: rgba(124, 92, 255, .12);
    }
    .drop.disabled { opacity: .45; cursor: not-allowed; }
    .drop:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }
    .hidden-input { display: none; }
    .drop-icon {
      width: 40px; height: 40px;
      border-radius: var(--cf-radius);
      background: rgba(124, 92, 255, .14);
      border: 1px solid rgba(124, 92, 255, .28);
      display: grid;
      place-items: center;
    }
    .drop-plus {
      width: 13px; height: 2px;
      background: var(--cf-accent-soft);
      position: relative;
      border-radius: 2px;
    }
    .drop-plus-v {
      position: absolute;
      left: 5.5px; top: -5.5px;
      width: 2px; height: 13px;
      background: var(--cf-accent-soft);
      border-radius: 2px;
    }
    .drop-title { font-size: 13px; font-weight: 500; }
    .drop-hint { font-size: 11.5px; color: var(--cf-text-dim); }

    /* — File list — */
    .files { display: flex; flex-direction: column; gap: 7px; }
    .file {
      display: flex;
      align-items: center;
      gap: 11px;
      padding: 10px 12px;
      border-radius: 11px;
      border: 1px solid var(--cf-border-soft);
      background: rgba(255, 255, 255, .025);
    }
    .file-thumb {
      width: 30px; height: 22px;
      border-radius: 5px;
      background: linear-gradient(135deg, rgba(124, 92, 255, .4), rgba(59, 130, 246, .3));
      flex: none;
    }
    .file-meta { flex: 1; min-width: 0; }
    .file-name {
      font-size: 12.5px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .file-size { font-size: 10px; color: var(--cf-text-dimmer); }
    .file-remove {
      all: unset;
      font-size: 14px;
      color: var(--cf-text-dimmer);
      cursor: pointer;
      padding: 0 4px;
      transition: color .15s ease;
    }
    .file-remove:hover:not(:disabled) { color: var(--cf-text); }
    .file-remove:disabled { opacity: .4; cursor: not-allowed; }

    .warn {
      display: flex;
      flex-direction: column;
      gap: 5px;
      padding: 10px 12px;
      border-radius: 11px;
      border: 1px solid rgba(240, 163, 78, .28);
      background: rgba(240, 163, 78, .08);
      color: var(--cf-warn-soft);
      font-size: 11.5px;
    }

    /* — 04 Output panel — */
    .output {
      border-radius: var(--cf-radius-lg);
      border: 1px solid var(--cf-border-card);
      background: var(--cf-surface-card);
      padding: 15px 15px 16px;
      display: flex;
      flex-direction: column;
      gap: 15px;
    }
    .field { display: flex; flex-direction: column; gap: 8px; }
    .field-label { font-size: 11.5px; color: var(--cf-text-muted); }
    .pills { display: flex; gap: 6px; }
    .pill {
      all: unset;
      flex: 1;
      text-align: center;
      font-size: 11px;
      padding: 7px 0;
      border-radius: var(--cf-radius-sm);
      cursor: pointer;
      transition: all .15s ease;
      border: 1px solid var(--cf-border-card);
      background: transparent;
      color: var(--cf-text-muted);
    }
    .pill:hover { border-color: rgba(124, 92, 255, .4); color: var(--cf-text-2); }
    .pill.on {
      border-color: rgba(146, 118, 255, .6);
      background: rgba(124, 92, 255, .16);
      color: var(--cf-accent-on-pill);
    }
    .pill:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }

    .voice-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding-top: 2px;
    }
    .voice-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .voice-name { font-size: 12.5px; }
    .voice-detail { font-size: 10.5px; color: var(--cf-text-dimmer); }
    .voice-change {
      all: unset;
      font-size: 11.5px;
      color: var(--cf-accent-link);
      cursor: pointer;
      flex: none;
    }
    .voice-change:hover { color: var(--cf-accent-link-hover); }
    .voice-change:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }

    /* — Generate bar — */
    .genbar {
      position: sticky;
      bottom: -8px;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 14px 16px;
      border-radius: var(--cf-radius-xl);
      border: 1px solid var(--cf-border-card);
      background: var(--cf-surface-sticky);
      backdrop-filter: blur(16px);
      box-shadow: 0 18px 40px rgba(0, 0, 0, .45);
    }
    .genbar-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .genbar-summary { font-size: 12.5px; color: var(--cf-text-2); }
    .genbar-est { font-size: 10.5px; color: var(--cf-text-dimmer); }
    .generate {
      all: unset;
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: 9px;
      height: 44px;
      padding: 0 22px;
      border-radius: var(--cf-radius);
      background: var(--cf-accent-grad);
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 10px 28px rgba(92, 80, 255, .4);
      transition: transform .16s ease, box-shadow .16s ease, opacity .16s ease;
      flex: none;
    }
    .generate:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 16px 34px rgba(92, 80, 255, .55);
    }
    .generate:active:not(:disabled) { transform: translateY(0); }
    .generate:disabled { opacity: .5; cursor: not-allowed; }
    .generate:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
    .generate-kbd {
      font-size: 10.5px;
      opacity: .75;
      border-left: 1px solid rgba(255, 255, 255, .3);
      padding-left: 9px;
    }
    .spinner {
      width: 15px; height: 15px;
      border: 2px solid rgba(255, 255, 255, .35);
      border-top-color: #fff;
      border-radius: 50%;
      animation: cfSpin .8s linear infinite;
      flex: none;
    }

    .cover { display: flex; flex-direction: column; gap: 7px; padding-top: 3px; }
    .cover-head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
    .cover-note { font-size: 10px; color: var(--cf-text-dimmer); }
    .cover-row { display: flex; gap: 7px; }
    .cover-row .cover-input { flex: 1; min-width: 0; }
    .cover-input {
      all: unset; box-sizing: border-box; width: 100%; height: 32px; padding: 0 10px;
      border-radius: var(--cf-radius-sm); border: 1px solid var(--cf-border-card);
      background: rgba(255, 255, 255, .02); font-size: 12px; color: var(--cf-text);
    }
    .cover-input::placeholder { color: var(--cf-text-dimmer); }
    .cover-input:focus { border-color: rgba(146, 118, 255, .5); background: rgba(124, 92, 255, .06); }

    .brand-field { flex-direction: row; align-items: center; gap: 10px; }
    .brand-text { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .brand-name { font-size: 12.5px; }
    .brand-detail { font-size: 10.5px; color: var(--cf-text-dimmer); }
    .brand-swatches { display: flex; gap: 3px; margin-left: auto; flex: none; }
    .brand-dot { width: 11px; height: 11px; border-radius: 50%; border: 1px solid rgba(255,255,255,.18); }
    .brand-link { flex: none; font-size: 11.5px; color: var(--cf-accent-link); text-decoration: none; }
    .brand-link:hover { color: var(--cf-accent-link-hover); }

    .nocredits {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 13px 15px;
      border-radius: var(--cf-radius);
      border: 1px solid rgba(233, 108, 108, .38);
      background: linear-gradient(160deg, rgba(233, 108, 108, .14), rgba(233, 108, 108, .04));
    }
    .nocredits-text { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
    .nocredits-title { font-size: 13px; font-weight: 600; color: #F3A0A0; }
    .nocredits-sub { font-size: 11.5px; color: var(--cf-text-2); }
    .nocredits-cta {
      flex-shrink: 0;
      padding: 8px 14px;
      border-radius: var(--cf-radius-sm);
      border: 1px solid rgba(233, 108, 108, .45);
      font-size: 12px;
      color: var(--cf-text);
      text-decoration: none;
    }
    .nocredits-cta:hover { background: rgba(233, 108, 108, .14); }

    .error {
      padding: 11px 14px;
      border-radius: var(--cf-radius);
      border: 1px solid rgba(248, 113, 113, .3);
      background: rgba(248, 113, 113, .1);
      color: var(--cf-err-soft);
      font-size: 12.5px;
    }

    /* — Responsive — */
    @media (max-width: 860px) {
      .page { padding: 28px 16px 48px; }
      .agent-grid { grid-template-columns: 1fr; }
      .split { grid-template-columns: 1fr; }
      .hero-title { font-size: 27px; }
      .genbar { flex-direction: column; align-items: stretch; }
      .generate { margin-left: 0; justify-content: center; }
    }
  `]
})
export class CreateJobComponent implements OnInit {
  readonly MAX_PROMPT = 2000;
  readonly MAX_FILES = 5;
  readonly MAX_SIZE_MB = 200;
  private readonly MAX_SIZE_BYTES = 200 * 1024 * 1024;
  private readonly ALLOWED_EXTENSIONS = ['.mp4', '.mov', '.webm'];

  selectedAgent: AgentType = 'video';
  prompt = '';
  isSubmitting = false;
  submitStatus = 'Dispatching…';
  errorMessage = '';

  selectedFiles: File[] = [];
  fileWarnings: string[] = [];
  isDragging = false;

  aspectRatio = '16:9';
  targetLength = '45s';
  voiceIndex = 0;
  videoLanguage = 'en';
  useBrandKit = false;

  // PFE cover fields. Empty means "not supplied": the server drops blank values so the
  // PDF keeps its bracketed placeholder rather than printing an empty line.
  coverStudentName = '';
  coverUniversity = '';
  coverSupervisor = '';
  coverAcademicYear = '';

  readonly ratios = ['16:9', '9:16', '1:1'];

  // The narration language. This drives the LLM's writing language, not just the voice:
  // picking Français makes the director and screenwriter author the script in French,
  // which is then read by the French voice and subtitled from that same French text.
  // Kokoro ships exactly one French voice, so 'fr' has no alternates to offer yet.
  readonly languages: LanguageOption[] = [
    { code: 'en', label: 'English', kokoroVoice: 'Heart', edgeVoice: 'Jenny' },
    { code: 'fr', label: 'Français', kokoroVoice: 'Siwis', edgeVoice: 'Denise' }
  ];
  readonly lengths = [
    { label: '15s', seconds: 15 },
    { label: '45s', seconds: 45 },
    { label: '90s', seconds: 90 }
  ];

  // Real engines available in the backend, not decorative labels.
  //
  // The first entry sends no tts_engine at all, which leaves TTS_ENGINE in the server's
  // .env authoritative. Defaulting to a concrete id here would silently pin every job to
  // that engine and make .env look like it was being ignored.
  // XTTS ('Claribel') and Piper ('Lessac') were removed at commercial remediation:
  // XTTS's weights are CPML (non-commercial) and Piper's engine is GPL-3.0.
  // See LICENSES.md R1 and R6. Kokoro is the server default set in .env.
  //
  // These pick the ENGINE; the Language pills pick which voice within that engine, so a
  // fixed voice name here would be wrong the moment the user selects Français.
  readonly voices: VoiceOption[] = [
    { id: '', name: 'Auto', detail: 'Server default' },
    { id: 'kokoro', name: 'Kokoro', detail: 'Kokoro-82M · local' },
    { id: 'edge', name: 'Edge', detail: 'Edge-TTS · cloud' }
  ];

  readonly agents: AgentCard[] = [
    {
      id: 'video',
      name: 'Video Montage',
      desc: 'Scripted explainer or launch film with TTS narration and stock cuts.',
      tags: ['MP4', '5 agents', 'TTS'],
      glyph: 'linear-gradient(135deg,#7C5CFF,#3B82F6)',
      glyphRadius: '3px'
    },
    {
      id: 'presentation',
      name: 'Presentation',
      desc: 'Branded slide deck with speaker notes, exported to .pptx or .pdf.',
      tags: ['PPTX', '3 agents'],
      glyph: 'linear-gradient(135deg,#F0A34E,#E96C6C)',
      glyphRadius: '3px'
    },
    {
      id: 'latex',
      name: 'Research Report',
      desc: 'Long-form technical write-up with citations, typeset to PDF.',
      tags: ['PDF', '4 agents'],
      glyph: 'linear-gradient(135deg,#34D399,#3B82F6)',
      glyphRadius: '50%'
    }
  ];

  readonly starters: Starter[] = [
    {
      label: 'Product launch film',
      agent: 'video',
      text: 'A 45-second launch film for our AI research assistant. Confident, cinematic, minimal — dark studio product shot, three benefit beats, logo lockup close.'
    },
    {
      label: 'Feature walkthrough',
      agent: 'video',
      text: 'A 60-second walkthrough of the new timeline editor: cold open on the problem, three UI beats with callouts, end on a CTA card.'
    },
    {
      label: 'Investor deck',
      agent: 'presentation',
      text: 'A 10-slide investor update deck covering traction, product velocity, unit economics, and the next two quarters of roadmap.'
    },
    {
      label: 'Technical report',
      agent: 'latex',
      text: 'A technical report on multi-agent orchestration for automated content generation, with architecture diagrams and citations.'
    }
  ];

  // Public: the template reads the shared signals straight off the service, so the
  // button state and the sidebar card can never disagree.
  constructor(
    private jobService: JobService,
    private router: Router,
    public credits: CreditsService,
    public brand: BrandKitService
  ) {}

  ngOnInit(): void {
    this.credits.refreshQuiet();
    // Decides whether the brand toggle is actionable, so it is fetched up front rather
    // than leaving the control disabled until the user navigates away and back.
    this.brand.refreshQuiet();
  }

  get brandDetail(): string {
    const kit = this.brand.kit();
    if (!kit?.has_brand_kit) return 'No kit saved yet';
    return kit.has_logo ? 'Palette, typeface & logo' : 'Palette & typeface · no logo';
  }

  /**
   * Two different reasons the button can be off, and they need different words: a user
   * with 0 remaining has to wait or upgrade, while a user whose only credit is tied up
   * in a running render just has to wait for it to land.
   */
  get outOfCreditsTitle(): string {
    const c = this.credits.credits();
    if (c && c.credits_remaining > 0 && c.jobs_in_flight > 0) return 'Credit reserved by a running job';
    return 'Out of credits';
  }

  get outOfCreditsDetail(): string {
    const c = this.credits.credits();
    if (!c) return '';
    if (c.credits_remaining > 0 && c.jobs_in_flight > 0) {
      const n = c.jobs_in_flight;
      return `${n} render${n === 1 ? '' : 's'} still running. Your last credit is committed until ${n === 1 ? 'it finishes' : 'they finish'} — a failed render gives it back.`;
    }
    const resets = this.credits.resetsInLabel().toLowerCase();
    return `You've used all ${c.credits_total} credits on the ${c.plan} plan.` + (resets ? ` ${resets.charAt(0).toUpperCase()}${resets.slice(1)}.` : '');
  }

  // ------------------------------------------------------------------
  // Derived state
  // ------------------------------------------------------------------

  get activeVoice(): VoiceOption {
    return this.voices[this.voiceIndex % this.voices.length];
  }

  get isVideo(): boolean {
    return this.selectedAgent === 'video';
  }

  /** The LaTeX report agent. 'latex' is the agent id; the UI calls it a Report. */
  get isReport(): boolean {
    return this.selectedAgent === 'latex';
  }

  /** Placeholders follow the chosen language, matching what the PDF will print. */
  get coverPlaceholders(): { student: string; university: string; supervisor: string; year: string } {
    return this.videoLanguage === 'fr'
      ? { student: "Nom de l'étudiant", university: 'Université / École',
          supervisor: "Nom de l'encadrant", year: 'Année universitaire' }
      : { student: 'Student name', university: 'University / School',
          supervisor: 'Supervisor', year: 'Academic year' };
  }

  get activeLanguage(): LanguageOption {
    return this.languages.find(l => l.code === this.videoLanguage) || this.languages[0];
  }

  /** Names the voice this job will actually be narrated by, for the chosen language. */
  get activeVoiceDetail(): string {
    const lang = this.activeLanguage;
    const voice = this.activeVoice.id === 'edge' ? lang.edgeVoice : lang.kokoroVoice;
    return `${voice} · ${this.activeVoice.detail}`;
  }

  /** Uploads only reach the video pipeline, so the zone is inert for other agents. */
  get uploadsAllowed(): boolean {
    return this.selectedAgent === 'video' && !this.isSubmitting;
  }

  get dropTitle(): string {
    if (this.selectedAgent !== 'video') return 'Available for the Video Montage crew';
    if (this.isDragging) return 'Release to attach';
    return 'Drop footage, stills, or a brand kit';
  }

  get selectedAgentName(): string {
    return (this.agents.find(a => a.id === this.selectedAgent) || this.agents[0]).name;
  }

  get targetSeconds(): number {
    return (this.lengths.find(l => l.label === this.targetLength) || this.lengths[1]).seconds;
  }

  get summaryLine(): string {
    if (this.selectedAgent !== 'video') return `${this.selectedAgentName} · default layout`;
    const voice = this.activeVoice.id ? `${this.activeVoice.name} voice` : 'default voice';
    return `${this.selectedAgentName} · ${this.activeLanguage.label} · ${this.aspectRatio} · ${this.targetLength} · ${voice}`;
  }

  get estimateLine(): string {
    if (this.selectedAgent !== 'video') return 'est. under 1 min';
    // Rendering runs roughly 4-5x the target length once media fetch is included.
    const mins = Math.max(1, Math.round((this.targetSeconds * 4.5) / 60));
    const files = this.selectedFiles.length;
    return `est. ~${mins} min${mins > 1 ? 's' : ''}${files ? ` · ${files} upload${files > 1 ? 's' : ''}` : ''}`;
  }

  useStarter(s: Starter) {
    this.prompt = s.text;
    this.selectedAgent = s.agent;
  }

  cycleVoice() {
    this.voiceIndex = (this.voiceIndex + 1) % this.voices.length;
  }

  // ------------------------------------------------------------------
  // Dropzone
  // ------------------------------------------------------------------

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    if (this.uploadsAllowed && this.selectedFiles.length < this.MAX_FILES) {
      this.isDragging = true;
    }
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging = false;
    if (!this.uploadsAllowed) return;
    const dropped = event.dataTransfer?.files;
    if (dropped && dropped.length > 0) {
      this.addFiles(Array.from(dropped));
    }
  }

  onFileInputChange(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.addFiles(Array.from(input.files));
    }
    // Reset so re-picking the same file still fires a change event.
    input.value = '';
  }

  /** Validates and appends files, reporting every rejection reason to the user. */
  private addFiles(files: File[]) {
    this.fileWarnings = [];

    for (const file of files) {
      if (this.selectedFiles.length >= this.MAX_FILES) {
        this.fileWarnings.push(`Only ${this.MAX_FILES} files allowed — "${file.name}" was skipped.`);
        continue;
      }

      const dot = file.name.lastIndexOf('.');
      const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : '';
      if (!this.ALLOWED_EXTENSIONS.includes(ext)) {
        this.fileWarnings.push(`"${file.name}" is not a supported video type (${this.ALLOWED_EXTENSIONS.join(', ')}).`);
        continue;
      }

      if (file.size > this.MAX_SIZE_BYTES) {
        this.fileWarnings.push(`"${file.name}" is ${this.formatSize(file.size)} — the limit is ${this.MAX_SIZE_MB} MB.`);
        continue;
      }

      const duplicate = this.selectedFiles.some(f => f.name === file.name && f.size === file.size);
      if (duplicate) {
        this.fileWarnings.push(`"${file.name}" is already in the list.`);
        continue;
      }

      this.selectedFiles.push(file);
    }
  }

  removeFile(index: number) {
    this.selectedFiles.splice(index, 1);
    this.fileWarnings = [];
  }

  formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ------------------------------------------------------------------
  // Submit
  // ------------------------------------------------------------------

  /**
   * The settings for this job.
   *
   * Video and report share `language` and nothing else, so they are built separately --
   * sending aspect_ratio with a report, or a cover name with a video, would store
   * settings the agent has no use for and make a re-run replay them.
   */
  private buildOptions(): Record<string, unknown> | undefined {
    if (this.isVideo) {
      return {
        aspect_ratio: this.aspectRatio,
        target_duration_seconds: this.targetSeconds,
        language: this.videoLanguage,
        // Sent only when a kit actually exists, so a stale toggle can never ask the
        // server to apply one that was deleted in another tab.
        use_brand_kit: this.useBrandKit && this.brand.hasKit() ? true : undefined,
        // Omitted entirely for 'Auto' so the server's TTS_ENGINE stays in charge.
        tts_engine: this.activeVoice.id || undefined
      };
    }
    if (this.isReport) {
      return {
        language: this.videoLanguage,
        // undefined rather than '' so the server keeps the PDF's placeholder.
        student_name: this.coverStudentName.trim() || undefined,
        university: this.coverUniversity.trim() || undefined,
        supervisor: this.coverSupervisor.trim() || undefined,
        academic_year: this.coverAcademicYear.trim() || undefined
      };
    }
    return undefined;
  }

  onSubmit() {
    if (!this.prompt.trim() || this.isSubmitting) return;

    const hasUploads = this.selectedAgent === 'video' && this.selectedFiles.length > 0;

    this.isSubmitting = true;
    this.errorMessage = '';
    this.submitStatus = hasUploads ? 'Creating job…' : 'Dispatching…';

    // With uploads we must defer the workflow: the pipeline would otherwise start
    // before the files land and generate the video without them.
    this.jobService.createJob({
      prompt: this.prompt,
      agent_type: this.selectedAgent,
      defer_start: hasUploads,
      video_options: this.buildOptions()
    }).subscribe({
      next: (job) => {
        // The new job is in flight, so a credit is now committed even though the balance
        // has not moved yet. Re-read so the sidebar and the button reflect that before
        // the user can come back and submit again.
        this.credits.refreshQuiet();
        if (!hasUploads) {
          this.isSubmitting = false;
          this.router.navigate(['/jobs', job.id]);
          return;
        }
        this.uploadThenStart(job.id);
      },
      error: (err) => {
        this.isSubmitting = false;
        if (err.status === 402) {
          // The server is the authority on the balance: sync to it rather than guessing,
          // so the button locks for the same reason the request was refused.
          this.credits.refreshQuiet();
          this.errorMessage = err.error?.detail
            || 'You are out of render credits. They reset monthly, or you can change plan.';
          return;
        }
        this.errorMessage = err.error?.detail || 'Failed to submit generation request. Please check backend connection.';
      }
    });
  }

  /** Uploads the selected clips, then releases the deferred job. */
  private uploadThenStart(jobId: string) {
    this.submitStatus = `Uploading ${this.selectedFiles.length} file(s)…`;

    this.jobService.uploadJobMedia(jobId, this.selectedFiles).subscribe({
      next: () => {
        this.submitStatus = 'Starting generation…';
        this.jobService.startJob(jobId).subscribe({
          next: () => {
            this.isSubmitting = false;
            this.router.navigate(['/jobs', jobId]);
          },
          error: (err) => {
            this.isSubmitting = false;
            this.errorMessage = err.error?.detail
              || 'Your files uploaded, but the job failed to start. Open the job and retry.';
          }
        });
      },
      error: (err) => {
        // The job exists but is deferred, so nothing is silently running without media.
        this.isSubmitting = false;
        this.errorMessage = err.error?.detail
          || 'Upload failed. Please check the file sizes and try again.';
      }
    });
  }
}
