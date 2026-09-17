import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="auth-page">
      <div class="blob blob-a" aria-hidden="true"></div>
      <div class="blob blob-b" aria-hidden="true"></div>

      <div class="auth-card">
        <div class="brand">
          <div class="brand-mark"><div class="brand-diamond"></div></div>
          <div class="brand-text">
            <span class="brand-name">CreateFlow</span>
            <span class="brand-sub cf-mono">AI STUDIO</span>
          </div>
        </div>

        <div class="head">
          <h1 class="title">Welcome back</h1>
          <p class="sub">Sign in to pick up where your agents left off.</p>
        </div>

        <form class="form" (ngSubmit)="onSubmit()" #f="ngForm" novalidate>
          <label class="field">
            <span class="label">Email</span>
            <input
              type="email"
              name="email"
              autocomplete="email"
              [(ngModel)]="email"
              required
              placeholder="you@studio.com"
              [disabled]="isSubmitting"
            />
          </label>

          <label class="field">
            <span class="label">Password</span>
            <input
              type="password"
              name="password"
              autocomplete="current-password"
              [(ngModel)]="password"
              required
              placeholder="••••••••"
              [disabled]="isSubmitting"
            />
          </label>

          <div class="error" *ngIf="errorMessage">⚠️ {{ errorMessage }}</div>

          <button
            type="submit"
            class="submit"
            [disabled]="isSubmitting || !email.trim() || !password"
          >
            <ng-container *ngIf="!isSubmitting">Sign in</ng-container>
            <ng-container *ngIf="isSubmitting"><span class="spinner"></span>Signing in…</ng-container>
          </button>
        </form>

        <div class="foot">
          No account yet? <a routerLink="/register" [queryParams]="{ returnUrl: returnUrl }">Create one</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .auth-page {
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 40px 20px;
      position: relative;
      overflow: hidden;
      background: var(--cf-bg);
    }
    .blob { position: absolute; filter: blur(20px); pointer-events: none; z-index: 0; }
    .blob-a {
      top: -320px; left: 10%; width: 820px; height: 660px;
      background: radial-gradient(closest-side, rgba(124, 92, 255, .22), transparent);
      animation: cfDrift 22s ease-in-out infinite;
    }
    .blob-b {
      bottom: -380px; right: -120px; width: 820px; height: 720px;
      background: radial-gradient(closest-side, rgba(59, 130, 246, .18), transparent);
      animation: cfDrift 28s ease-in-out infinite reverse;
    }

    .auth-card {
      position: relative;
      z-index: 1;
      width: 100%;
      max-width: 400px;
      display: flex;
      flex-direction: column;
      gap: 24px;
      padding: 30px 28px 26px;
      border-radius: var(--cf-radius-xl);
      border: 1px solid var(--cf-border-card);
      background: linear-gradient(180deg, rgba(20, 20, 28, .92), rgba(14, 14, 20, .92));
      backdrop-filter: blur(16px);
      box-shadow: 0 24px 60px rgba(0, 0, 0, .5);
    }

    .brand { display: flex; align-items: center; gap: 11px; }
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
      font-size: 9px;
      letter-spacing: .16em;
      color: var(--cf-text-dim);
    }

    .head { display: flex; flex-direction: column; gap: 7px; }
    .title { margin: 0; font-size: 25px; font-weight: 600; letter-spacing: -.022em; }
    .sub { margin: 0; font-size: 13.5px; color: var(--cf-text-muted); }

    .form { display: flex; flex-direction: column; gap: 14px; }
    .field { display: flex; flex-direction: column; gap: 7px; }
    .label { font-size: 11.5px; color: var(--cf-text-muted); }
    .field input {
      height: 42px;
      padding: 0 13px;
      border-radius: 10px;
      border: 1px solid var(--cf-border-card);
      background: rgba(255, 255, 255, .028);
      color: var(--cf-text);
      font-size: 13.5px;
      outline: none;
      transition: border-color .15s ease, box-shadow .15s ease;
    }
    .field input:focus {
      border-color: rgba(146, 118, 255, .6);
      box-shadow: 0 0 0 3px rgba(124, 92, 255, .16);
    }
    .field input:disabled { opacity: .55; cursor: not-allowed; }

    .error {
      padding: 10px 12px;
      border-radius: 10px;
      border: 1px solid rgba(248, 113, 113, .3);
      background: rgba(248, 113, 113, .1);
      color: var(--cf-err-soft);
      font-size: 12.3px;
    }

    .submit {
      all: unset;
      margin-top: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 9px;
      height: 44px;
      border-radius: var(--cf-radius);
      background: var(--cf-accent-grad);
      color: #fff;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 10px 28px rgba(92, 80, 255, .38);
      transition: transform .16s ease, box-shadow .16s ease, opacity .16s ease;
    }
    .submit:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 16px 34px rgba(92, 80, 255, .5);
    }
    .submit:active:not(:disabled) { transform: translateY(0); }
    .submit:disabled { opacity: .5; cursor: not-allowed; }
    .submit:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }

    .spinner {
      width: 15px; height: 15px;
      border: 2px solid rgba(255, 255, 255, .35);
      border-top-color: #fff;
      border-radius: 50%;
      animation: cfSpin .8s linear infinite;
    }

    .foot {
      text-align: center;
      font-size: 12.5px;
      color: var(--cf-text-muted);
    }
  `]
})
export class LoginComponent {
  email = '';
  password = '';
  isSubmitting = false;
  errorMessage = '';
  returnUrl: string | undefined;

  constructor(
    private auth: AuthService,
    private router: Router,
    route: ActivatedRoute
  ) {
    this.returnUrl = route.snapshot.queryParamMap.get('returnUrl') || undefined;
  }

  onSubmit() {
    if (this.isSubmitting || !this.email.trim() || !this.password) return;

    this.isSubmitting = true;
    this.errorMessage = '';

    this.auth.login(this.email.trim(), this.password).subscribe({
      next: () => {
        this.isSubmitting = false;
        this.router.navigateByUrl(this.returnUrl || '/create');
      },
      error: (err) => {
        this.isSubmitting = false;
        this.errorMessage = err.status === 401
          ? 'Incorrect email or password.'
          : err.error?.detail || 'Could not sign in. Please check the backend connection.';
      }
    });
  }
}
