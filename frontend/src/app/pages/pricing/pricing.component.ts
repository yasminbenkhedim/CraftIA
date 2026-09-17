import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { CreditsService } from '../../services/credits.service';

interface PlanRow {
  id: string;
  name: string;
  credits: number;
  blurb: string;
}

/**
 * Pricing placeholder.
 *
 * Allowances come from GET /api/me/plans rather than being retyped here, so the page can
 * never advertise a different number from the one the backend enforces. Prices are
 * deliberately absent: no payment provider is integrated, and a price next to a button
 * that does nothing is worse than no price at all.
 */
@Component({
  selector: 'app-pricing',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page">
      <div class="wrap">
        <header class="hero">
          <span class="eyebrow cf-mono">Plans</span>
          <h1 class="hero-title">Choose your render volume</h1>
          <p class="hero-sub">
            One credit delivers one finished video, deck or report. Credits are charged only
            when a render succeeds — a failed job never costs you one.
          </p>
        </header>

        <div class="notice">
          <span class="notice-badge cf-mono">Coming soon</span>
          Online payment isn’t live yet. Plans are listed so you can see what’s coming;
          to change yours today, get in touch and we’ll switch it over manually.
        </div>

        <div class="grid">
          <div
            class="plan"
            *ngFor="let p of plans()"
            [class.current]="p.id === currentPlan()"
          >
            <div class="plan-head">
              <span class="plan-name">{{ p.name }}</span>
              <span class="plan-badge cf-mono" *ngIf="p.id === currentPlan()">Current</span>
            </div>
            <div class="plan-credits cf-mono">
              {{ p.credits }}<span class="plan-credits-unit">/month</span>
            </div>
            <p class="plan-blurb">{{ p.blurb }}</p>
            <button type="button" class="plan-cta" disabled>
              {{ p.id === currentPlan() ? 'Your plan' : 'Payment coming soon' }}
            </button>
          </div>
        </div>

        <div class="foot">
          <a routerLink="/create" class="back">← Back to the studio</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .page { padding: 40px 32px 56px; }
    .wrap { max-width: 960px; margin: 0 auto; display: flex; flex-direction: column; gap: 26px; }

    .hero { display: flex; flex-direction: column; gap: 9px; }
    .eyebrow { font-size: 11px; color: var(--cf-text-dim); letter-spacing: .08em; text-transform: uppercase; }
    .hero-title { margin: 0; font-size: 34px; font-weight: 600; letter-spacing: -.025em; }
    .hero-sub { margin: 0; max-width: 620px; font-size: 13.5px; line-height: 1.6; color: var(--cf-text-2); }

    .notice {
      padding: 13px 15px;
      border-radius: var(--cf-radius);
      border: 1px solid var(--cf-border-soft);
      background: rgba(124, 92, 255, .08);
      font-size: 12.5px;
      line-height: 1.6;
      color: var(--cf-text-2);
    }
    .notice-badge {
      display: inline-block;
      margin-right: 9px;
      padding: 2px 7px;
      border-radius: 99px;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .06em;
      background: rgba(124, 92, 255, .22);
      color: var(--cf-accent-on-pill);
    }

    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; }
    .plan {
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 18px;
      border-radius: var(--cf-radius);
      border: 1px solid var(--cf-border-card);
      background: var(--cf-surface-card, rgba(255, 255, 255, .02));
    }
    .plan.current {
      border-color: rgba(146, 118, 255, .55);
      background: linear-gradient(160deg, rgba(124, 92, 255, .14), rgba(59, 130, 246, .05));
    }
    .plan-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .plan-name { font-size: 14px; font-weight: 600; }
    .plan-badge {
      font-size: 10px;
      padding: 2px 7px;
      border-radius: 99px;
      background: rgba(124, 92, 255, .22);
      color: var(--cf-accent-on-pill);
    }
    .plan-credits { font-size: 26px; letter-spacing: -.02em; }
    .plan-credits-unit { font-size: 12px; color: var(--cf-text-dimmer); margin-left: 3px; }
    .plan-blurb { margin: 0; font-size: 12px; line-height: 1.55; color: var(--cf-text-dim); flex: 1; }
    .plan-cta {
      all: unset;
      text-align: center;
      padding: 9px 0;
      border-radius: var(--cf-radius-sm);
      border: 1px solid var(--cf-border-card);
      font-size: 12px;
      color: var(--cf-text-dimmer);
      cursor: not-allowed;
    }

    .foot { padding-top: 4px; }
    .back { font-size: 12.5px; color: var(--cf-text-2); text-decoration: none; }
    .back:hover { color: var(--cf-text); }
  `]
})
export class PricingComponent implements OnInit {
  readonly plans = signal<PlanRow[]>([]);
  readonly currentPlan = signal<string>('');

  private readonly copy: Record<string, { name: string; blurb: string }> = {
    free: { name: 'Free', blurb: 'Enough to try a full project end to end — a PFE video or a short deck.' },
    starter: { name: 'Starter', blurb: 'For a semester of coursework, or a freelancer with a steady trickle of client work.' },
    pro: { name: 'Pro', blurb: 'For agencies and teams shipping content every week.' }
  };

  constructor(private credits: CreditsService) {}

  ngOnInit(): void {
    this.currentPlan.set(this.credits.credits()?.plan ?? '');
    this.credits.refresh().subscribe({
      next: c => this.currentPlan.set(c.plan),
      error: () => { /* the catalogue below still renders without a highlighted row */ }
    });

    this.credits.plans().subscribe({
      next: cat => this.plans.set(
        Object.entries(cat.plans).map(([id, credits]) => ({
          id,
          name: this.copy[id]?.name ?? id,
          credits,
          blurb: this.copy[id]?.blurb ?? ''
        }))
      ),
      error: () => this.plans.set([])
    });
  }
}
