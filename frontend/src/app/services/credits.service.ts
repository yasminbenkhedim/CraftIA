import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface Credits {
  plan: string;
  credits_remaining: number;
  credits_total: number;
  credits_reset_at: string | null;
  /**
   * Balance minus jobs already queued or running. The backend debits a credit only when
   * a job succeeds, so a render in flight has not been paid for yet — this is the number
   * that decides whether another job can start, and the one the Generate button reads.
   */
  credits_available: number;
  jobs_in_flight: number;
}

export interface PlanCatalogue {
  plans: Record<string, number>;
  default_plan: string;
}

@Injectable({ providedIn: 'root' })
export class CreditsService {
  private apiUrl = 'http://localhost:8000/api';

  /**
   * Shared reactive balance. One store rather than a copy per component: the sidebar card
   * and the Generate button must never disagree about whether the user can render.
   */
  private readonly _credits = signal<Credits | null>(null);
  readonly credits = this._credits.asReadonly();

  /** Null while the first fetch is in flight, so the UI can hold off instead of flashing 0. */
  readonly isLoaded = computed(() => this._credits() !== null);

  /** True only once a real answer has arrived and it says there is nothing left. */
  readonly isOutOfCredits = computed(() => {
    const c = this._credits();
    return c !== null && c.credits_available <= 0;
  });

  readonly usedFraction = computed(() => {
    const c = this._credits();
    if (!c || c.credits_total <= 0) return 0;
    return Math.min(1, Math.max(0, c.credits_remaining / c.credits_total));
  });

  constructor(private http: HttpClient) {}

  /** Fetches the balance and publishes it. Errors leave the last known value in place. */
  refresh(): Observable<Credits> {
    return this.http.get<Credits>(`${this.apiUrl}/me/credits`).pipe(
      tap(c => this._credits.set(c))
    );
  }

  /** Fire-and-forget refresh for callers that just need the number to catch up. */
  refreshQuiet(): void {
    this.refresh().subscribe({ error: () => { /* keep the stale value; the card just won't move */ } });
  }

  plans(): Observable<PlanCatalogue> {
    return this.http.get<PlanCatalogue>(`${this.apiUrl}/me/plans`);
  }

  clear(): void {
    this._credits.set(null);
  }

  /** "in 12 days" / "today" — the card shows when the allowance comes back. */
  resetsInLabel(): string {
    const c = this._credits();
    if (!c?.credits_reset_at) return '';
    // The API returns a naive UTC timestamp; append Z so it is not read as local time.
    const iso = c.credits_reset_at.endsWith('Z') ? c.credits_reset_at : `${c.credits_reset_at}Z`;
    const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
    if (!isFinite(days)) return '';
    if (days <= 0) return 'Resets today';
    return `Resets in ${days} day${days === 1 ? '' : 's'}`;
  }
}
