import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { Subscription, filter } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { CreditsService } from '../../services/credits.service';

/**
 * Application shell: the 248px rail + 60px header from the design spec.
 * Wraps the routed page content so every screen shares the same chrome.
 */
@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <div class="shell">
      <!-- Ambient gradient blobs (decorative, behind everything) -->
      <div class="blob blob-a" aria-hidden="true"></div>
      <div class="blob blob-b" aria-hidden="true"></div>

      <!-- ============ RAIL ============ -->
      <aside class="rail">
        <a class="brand" routerLink="/">
          <div class="brand-mark"><div class="brand-diamond"></div></div>
          <div class="brand-text">
            <span class="brand-name">CreateFlow</span>
            <span class="brand-sub">AI Studio</span>
          </div>
        </a>

        <a class="new-btn" routerLink="/create">
          <span class="new-btn-plus">+</span> New deliverable
        </a>

        <div class="rail-label">Workspace</div>
        <nav class="rail-nav">
          <a routerLink="/create" routerLinkActive="active" class="nav-item">
            <span class="nav-dot"></span>Create
          </a>
          <a routerLink="/" [routerLinkActive]="'active'" [routerLinkActiveOptions]="{ exact: true }" class="nav-item">
            <span class="nav-dot"></span>Active runs
          </a>
          <a routerLink="/library" routerLinkActive="active" class="nav-item">
            <span class="nav-dot"></span>Library
          </a>

          <!-- 'Assets' used to sit below this. It was removed rather than locked:
               per-job uploads already cover the need, and a shared asset pool would break
               the per-job provenance model in agents/video/attribution.py, which records
               where each asset came from for the video it was used in. -->
          <a routerLink="/brand-kit" routerLinkActive="active" class="nav-item">
            <span class="nav-dot"></span>Brand kit
          </a>
        </nav>

        <div class="rail-footer">
          <div class="credits" [class.credits-empty]="credits.isOutOfCredits()">
            <div class="credits-head">
              <span class="credits-label">Render credits</span>
              <span class="credits-value cf-mono" *ngIf="credits.credits() as c">
                {{ c.credits_remaining }}<span class="credits-total">/{{ c.credits_total }}</span>
              </span>
              <span class="credits-value cf-mono credits-total" *ngIf="!credits.isLoaded()">—</span>
            </div>
            <div class="credits-track">
              <div class="credits-fill" [style.width.%]="credits.usedFraction() * 100"></div>
            </div>
            <div class="credits-note" *ngIf="credits.credits() as c">
              <span class="credits-out" *ngIf="credits.isOutOfCredits()">Out of credits</span>
              <span *ngIf="!credits.isOutOfCredits()">{{ credits.resetsInLabel() }}</span>
              ·
              <a routerLink="/pricing">Upgrade</a>
            </div>
          </div>
          <div class="user">
            <div class="avatar">{{ initials }}</div>
            <div class="user-text">
              <span class="user-name" [title]="userEmail">{{ userEmail }}</span>
              <span class="user-plan">{{ planLabel }}</span>
            </div>
            <button
              type="button"
              class="logout"
              (click)="logout()"
              title="Log out"
              aria-label="Log out"
            >⏻</button>
          </div>
        </div>
      </aside>

      <!-- ============ MAIN ============ -->
      <main class="main">
        <header class="topbar">
          <div class="search">
            <span class="search-icon" aria-hidden="true"></span>
            <input placeholder="Search deliverables, prompts, assets" aria-label="Search" />
            <span class="kbd cf-mono">⌘K</span>
          </div>
          <div class="topbar-right">
            <div class="agents-pill">
              <span class="agents-dot"></span>
              <span class="cf-mono agents-text">5 agents online</span>
            </div>
            <a class="docs-btn" href="#" (click)="$event.preventDefault()">Docs</a>
          </div>
        </header>

        <div class="main-body">
          <ng-content></ng-content>
        </div>
      </main>
    </div>
  `,
  styles: [`
    .shell {
      min-height: 100vh;
      display: flex;
      background: var(--cf-bg);
      position: relative;
      overflow: hidden;
    }

    /* — Ambient blobs — */
    .blob {
      position: absolute;
      filter: blur(20px);
      pointer-events: none;
      z-index: 0;
    }
    .blob-a {
      top: -360px; left: 180px; width: 900px; height: 700px;
      background: radial-gradient(closest-side, rgba(124, 92, 255, .20), transparent);
      animation: cfDrift 22s ease-in-out infinite;
    }
    .blob-b {
      bottom: -420px; right: -160px; width: 900px; height: 800px;
      background: radial-gradient(closest-side, rgba(59, 130, 246, .16), transparent);
      animation: cfDrift 28s ease-in-out infinite reverse;
    }

    /* — Rail — */
    .rail {
      position: relative;
      z-index: 2;
      width: var(--cf-rail-w);
      flex: none;
      min-height: 100vh;
      border-right: 1px solid var(--cf-border);
      background: var(--cf-surface-rail);
      backdrop-filter: blur(18px);
      display: flex;
      flex-direction: column;
      padding: 22px 16px 18px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 11px;
      padding: 0 6px 22px;
      color: inherit;
    }
    .brand:hover { color: inherit; }
    .brand-mark {
      width: 32px; height: 32px;
      border-radius: 9px;
      background: var(--cf-accent-grad);
      display: grid;
      place-items: center;
      box-shadow: 0 6px 18px rgba(124, 92, 255, .42);
      flex: none;
    }
    .brand-diamond {
      width: 11px; height: 11px;
      background: #fff;
      transform: rotate(45deg);
      border-radius: 2px;
    }
    .brand-text { display: flex; flex-direction: column; gap: 2px; }
    .brand-name { font-size: 14.5px; font-weight: 600; letter-spacing: -.01em; }
    .brand-sub {
      font-family: var(--cf-font-mono);
      font-size: 9px;
      letter-spacing: .16em;
      color: var(--cf-text-dim);
      text-transform: uppercase;
    }

    .new-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      height: 38px;
      border-radius: 10px;
      background: var(--cf-accent-grad);
      color: #fff;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 8px 22px var(--cf-accent-glow);
      transition: transform .16s ease, box-shadow .16s ease;
    }
    .new-btn:hover {
      color: #fff;
      transform: translateY(-1px);
      box-shadow: 0 12px 28px rgba(92, 80, 255, .5);
    }
    .new-btn:active { transform: translateY(0); }
    .new-btn-plus { font-size: 15px; line-height: 1; margin-top: -1px; }

    .rail-label {
      font-family: var(--cf-font-mono);
      font-size: 9px;
      letter-spacing: .16em;
      color: var(--cf-text-faint);
      text-transform: uppercase;
      padding: 26px 8px 9px;
    }

    .rail-nav { display: flex; flex-direction: column; gap: 2px; }
    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      height: 34px;
      padding: 0 10px;
      border-radius: 9px;
      font-size: 13px;
      cursor: pointer;
      color: var(--cf-text-muted);
      transition: background .15s ease, color .15s ease;
    }
    .nav-item:hover { background: var(--cf-surface-card-hover); color: var(--cf-text); }
    .nav-item.active { color: var(--cf-text); background: var(--cf-accent-tint); }
    .nav-item-muted { color: var(--cf-text-muted); }
    .nav-dot {
      width: 5px; height: 5px;
      border-radius: 50%;
      background: currentColor;
      opacity: .7;
      flex: none;
    }
    .nav-dot.dim { opacity: .5; }

    .rail-footer {
      margin-top: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .credits {
      padding: 14px;
      border-radius: var(--cf-radius);
      border: 1px solid var(--cf-border-soft);
      background: linear-gradient(160deg, rgba(124, 92, 255, .14), rgba(59, 130, 246, .06));
    }
    .credits-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 9px;
    }
    .credits-label { font-size: 11.5px; color: var(--cf-text-2); }
    .credits-value { font-size: 11px; color: var(--cf-text); }
    .credits-total { color: var(--cf-text-dimmer); }
    .credits-track {
      height: 4px;
      border-radius: 99px;
      background: rgba(255, 255, 255, .09);
      overflow: hidden;
    }
    .credits-fill {
      /* Width is bound to the real balance; no default here, so an unloaded card shows
         an empty track rather than a plausible-looking 68%. */
      width: 0;
      height: 100%;
      border-radius: 99px;
      background: linear-gradient(90deg, #7C5CFF, #3B82F6);
      transition: width .3s ease;
    }
    .credits-note { font-size: 11px; color: var(--cf-text-dim); margin-top: 9px; }
    .credits-note a { color: var(--cf-text-2); text-decoration: none; border-bottom: 1px solid rgba(255,255,255,.18); }
    .credits-note a:hover { color: var(--cf-text); }

    /* Empty state: the card stops being a progress indicator and becomes a prompt. */
    .credits-empty {
      border-color: rgba(233, 108, 108, .38);
      background: linear-gradient(160deg, rgba(233, 108, 108, .16), rgba(233, 108, 108, .05));
    }
    .credits-empty .credits-fill { background: rgba(233, 108, 108, .55); }
    .credits-out { color: #F3A0A0; }

    .user { display: flex; align-items: center; gap: 10px; padding: 6px 4px; }
    .avatar {
      width: 28px; height: 28px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2A2A3A, #3E3E55);
      display: grid;
      place-items: center;
      font-size: 11px;
      font-weight: 600;
      color: #C9C9D8;
      flex: none;
    }
    .user-text { display: flex; flex-direction: column; min-width: 0; flex: 1; }
    .user-name {
      font-size: 12px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .user-plan { font-size: 10.5px; color: var(--cf-text-dimmer); }
    .logout {
      all: unset;
      flex: none;
      width: 26px;
      height: 26px;
      display: grid;
      place-items: center;
      border-radius: 7px;
      color: var(--cf-text-dimmer);
      font-size: 13px;
      cursor: pointer;
      transition: background .15s ease, color .15s ease;
    }
    .logout:hover { background: rgba(248, 113, 113, .14); color: var(--cf-err-soft); }
    .logout:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }

    /* — Main — */
    .main {
      position: relative;
      z-index: 2;
      flex: 1;
      min-width: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    .topbar {
      height: var(--cf-header-h);
      flex: none;
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 0 32px;
      border-bottom: 1px solid var(--cf-border);
      background: var(--cf-surface-header);
      backdrop-filter: blur(14px);
    }
    .search {
      display: flex;
      align-items: center;
      gap: 8px;
      height: 32px;
      padding: 0 12px;
      border-radius: 9px;
      border: 1px solid var(--cf-border-soft);
      background: rgba(255, 255, 255, .03);
      min-width: 280px;
    }
    .search-icon {
      width: 11px; height: 11px;
      border: 1.5px solid var(--cf-text-dimmer);
      border-radius: 50%;
      flex: none;
    }
    .search input {
      all: unset;
      flex: 1;
      min-width: 0;
      font-size: 12.5px;
      color: var(--cf-text);
    }
    .kbd {
      font-size: 10px;
      color: var(--cf-text-faint);
      border: 1px solid rgba(255, 255, 255, .09);
      border-radius: 4px;
      padding: 1px 5px;
      flex: none;
    }
    .topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
    .agents-pill {
      display: flex;
      align-items: center;
      gap: 7px;
      height: 30px;
      padding: 0 11px;
      border-radius: 99px;
      border: 1px solid rgba(52, 211, 153, .22);
      background: rgba(52, 211, 153, .08);
    }
    .agents-dot {
      width: 6px; height: 6px;
      border-radius: 50%;
      background: var(--cf-ok);
      animation: cfPulse 1.8s ease-in-out infinite;
    }
    .agents-text { font-size: 10.5px; color: var(--cf-ok-soft); }
    .docs-btn {
      height: 30px;
      padding: 0 12px;
      border-radius: 9px;
      border: 1px solid var(--cf-border-soft);
      display: flex;
      align-items: center;
      font-size: 12px;
      color: var(--cf-text-2);
      cursor: pointer;
      transition: background .15s ease;
    }
    .docs-btn:hover { background: var(--cf-surface-card-hover); color: var(--cf-text-2); }

    .main-body { flex: 1; min-height: 0; overflow: auto; }

    /* — Narrow screens: collapse the rail to icons-off, stack instead — */
    @media (max-width: 900px) {
      .shell { flex-direction: column; }
      .rail {
        width: 100%;
        min-height: 0;
        border-right: none;
        border-bottom: 1px solid var(--cf-border);
      }
      .rail-footer { display: none; }
      .rail-nav { flex-direction: row; flex-wrap: wrap; }
      .topbar { padding: 0 16px; }
      .search { min-width: 0; flex: 1; }
    }
  `]
})
export class AppShellComponent implements OnInit, OnDestroy {
  private navSub?: Subscription;

  // Public so the template can read the signals directly -- the card is a pure
  // projection of the service's state, with no local copy to fall out of date.
  constructor(
    private auth: AuthService,
    private router: Router,
    public credits: CreditsService
  ) {}

  ngOnInit(): void {
    this.credits.refreshQuiet();

    // Re-read on every navigation. A render finishes in the background, so without this
    // the card would keep showing the pre-render balance until a full page reload --
    // and the moment it matters most is right after a job completes.
    this.navSub = this.router.events
      .pipe(filter(e => e instanceof NavigationEnd))
      .subscribe(() => this.credits.refreshQuiet());
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
  }

  /** "Free plan" / "Pro plan", from the real balance rather than a fixed label. */
  get planLabel(): string {
    const plan = this.credits.credits()?.plan;
    if (!plan) return 'Plan —';
    return `${plan.charAt(0).toUpperCase()}${plan.slice(1)} plan`;
  }

  get userEmail(): string {
    return this.auth.user()?.email ?? 'Not signed in';
  }

  /** Two-letter avatar from the email's local part (e.g. mara.reyes -> MR). */
  get initials(): string {
    const email = this.auth.user()?.email;
    if (!email) return '—';
    const local = email.split('@')[0];
    const parts = local.split(/[._\-+]/).filter(Boolean);
    const letters = parts.length >= 2
      ? parts[0][0] + parts[1][0]
      : local.slice(0, 2);
    return letters.toUpperCase();
  }

  logout(): void {
    // Drop the cached balance too, so the next account to sign in on this browser never
    // sees the previous user's credits in the interval before its own fetch lands.
    this.credits.clear();
    this.auth.logout();
  }
}
