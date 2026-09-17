import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { AuthService } from './auth.service';

export interface BrandKit {
  has_brand_kit: boolean;
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: string;
  has_logo: boolean;
  /** Relative; the browser appends its own ?token= as it does for artifacts. */
  logo_url: string | null;
  updated_at: string | null;
}

export interface FontOption {
  id: string;
  label: string;
  note: string;
}

export interface BrandKitUpdate {
  primary_color: string;
  secondary_color: string;
  accent_color: string;
  font_choice: string;
}

@Injectable({ providedIn: 'root' })
export class BrandKitService {
  private apiUrl = 'http://localhost:8000/api';

  /**
   * Shared so the create page's "Use my brand kit" toggle and the brand-kit page agree.
   * Without one store, saving a kit would leave the toggle disabled until a reload.
   */
  private readonly _kit = signal<BrandKit | null>(null);
  readonly kit = this._kit.asReadonly();

  /** True only once a real answer has arrived and it says a kit exists. */
  readonly hasKit = computed(() => this._kit()?.has_brand_kit === true);
  readonly isLoaded = computed(() => this._kit() !== null);

  constructor(private http: HttpClient, private auth: AuthService) {}

  refresh(): Observable<BrandKit> {
    return this.http.get<BrandKit>(`${this.apiUrl}/me/brand-kit`).pipe(tap(k => this._kit.set(k)));
  }

  refreshQuiet(): void {
    this.refresh().subscribe({ error: () => { /* leave the last known value in place */ } });
  }

  save(update: BrandKitUpdate): Observable<BrandKit> {
    return this.http.put<BrandKit>(`${this.apiUrl}/me/brand-kit`, update).pipe(tap(k => this._kit.set(k)));
  }

  uploadLogo(file: File): Observable<BrandKit> {
    const form = new FormData();
    form.append('file', file, file.name);
    // No Content-Type header: the browser must set the multipart boundary itself.
    return this.http.post<BrandKit>(`${this.apiUrl}/me/brand-kit/logo`, form).pipe(tap(k => this._kit.set(k)));
  }

  deleteLogo(): Observable<BrandKit> {
    return this.http.delete<BrandKit>(`${this.apiUrl}/me/brand-kit/logo`).pipe(tap(k => this._kit.set(k)));
  }

  fonts(): Observable<FontOption[]> {
    return this.http.get<FontOption[]>(`${this.apiUrl}/me/brand-kit/fonts`);
  }

  /**
   * Absolute logo URL with the token in the query string.
   *
   * An <img> src cannot carry an Authorization header, so the interceptor never sees it —
   * the same reason artifact and thumbnail URLs are built this way. `cacheBust` forces a
   * reload after an upload, which would otherwise show the previous logo from cache.
   */
  logoSrc(cacheBust?: string | number): string | null {
    const kit = this._kit();
    if (!kit?.logo_url) return null;
    const token = this.auth.token ?? '';
    const bust = cacheBust ? `&v=${encodeURIComponent(String(cacheBust))}` : '';
    return `${this.apiUrl.replace(/\/api$/, '')}${kit.logo_url}?token=${encodeURIComponent(token)}${bust}`;
  }

  clear(): void {
    this._kit.set(null);
  }
}
