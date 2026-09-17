import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
}

export interface CurrentUser {
  user_id: string;
  email: string;
  full_name?: string;
}

const TOKEN_KEY = 'access_token';
const USER_KEY = 'auth_user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private apiUrl = 'http://localhost:8000/api';

  /** Reactive session state so the shell can render the user without polling. */
  private readonly _user = signal<CurrentUser | null>(this.readStoredUser());
  readonly user = this._user.asReadonly();
  readonly isAuthenticated = computed(() => !!this._user());

  constructor(private http: HttpClient, private router: Router) {}

  // ------------------------------------------------------------------
  // Token access
  // ------------------------------------------------------------------

  get token(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      // localStorage can throw in private-browsing / blocked-cookie modes.
      return null;
    }
  }

  /**
   * True when a token exists AND its `exp` claim is still in the future.
   * Checking expiry client-side lets the guard bounce to /login immediately
   * instead of letting the user load a page that will 401 on its first request.
   */
  hasValidToken(): boolean {
    const token = this.token;
    if (!token) return false;

    const exp = this.tokenExpiry(token);
    if (exp === null) return true;   // Opaque token: let the server decide.
    return exp * 1000 > Date.now();
  }

  /** Reads the `exp` claim without a JWT library. Returns null if unreadable. */
  private tokenExpiry(token: string): number | null {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
      // base64url -> base64, then decode.
      const payload = JSON.parse(
        atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))
      );
      return typeof payload?.exp === 'number' ? payload.exp : null;
    } catch {
      return null;
    }
  }

  // ------------------------------------------------------------------
  // Auth operations
  // ------------------------------------------------------------------

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.apiUrl}/auth/login`, { email, password })
      .pipe(tap(res => this.persist(res)));
  }

  register(fullName: string, email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.apiUrl}/auth/register`, {
        email,
        password,
        full_name: fullName
      })
      .pipe(tap(res => this.persist(res)));
  }

  /** Clears the session. `redirect` is false when the interceptor already navigates. */
  logout(redirect = true): void {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      // Legacy key written by earlier builds — clear it so a stale value can't
      // resurrect a dead session.
      localStorage.removeItem('token');
    } catch {
      /* storage unavailable — in-memory state is still cleared below */
    }
    this._user.set(null);
    if (redirect) {
      this.router.navigate(['/login']);
    }
  }

  private persist(res: AuthResponse): void {
    const user: CurrentUser = { user_id: res.user_id, email: res.email };
    try {
      localStorage.setItem(TOKEN_KEY, res.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      /* storage unavailable — session still works for this tab via the signal */
    }
    this._user.set(user);
  }

  private readStoredUser(): CurrentUser | null {
    try {
      // Only trust the cached user if a token is actually present.
      if (!localStorage.getItem(TOKEN_KEY)) return null;
      const raw = localStorage.getItem(USER_KEY);
      return raw ? JSON.parse(raw) as CurrentUser : null;
    } catch {
      return null;
    }
  }
}
