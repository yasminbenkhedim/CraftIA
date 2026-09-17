import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { BrandKitService, FontOption } from '../../services/brand-kit.service';

/**
 * Brand kit settings.
 *
 * Scoped to what actually reaches a rendered frame: three colours, one typeface, one
 * logo. The live preview is the point of the page — a hex field tells you nothing about
 * whether a palette works on a title card, so the card is rendered from the same values
 * the renderer will use.
 */
@Component({
  selector: 'app-brand-kit',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="bk">
      <header class="bk-head">
        <div class="bk-titles">
          <span class="eyebrow cf-mono">Workspace</span>
          <h1>Brand kit</h1>
          <p class="bk-sub">
            Saved once, applied to every video you tick “Use my brand kit” on — instead of
            the AI picking new colours for each one.
          </p>
        </div>
      </header>

      <div class="cf-loading" *ngIf="isLoading">
        <div class="cf-spinner"></div>
        <p>Loading your brand kit…</p>
      </div>

      <div class="cols" *ngIf="!isLoading">
        <!-- ============ settings ============ -->
        <section class="panel">
          <div class="field">
            <span class="field-label">Logo</span>
            <div class="logo-row">
              <div class="logo-box" [class.empty]="!logoSrc()">
                <img *ngIf="logoSrc() as src" [src]="src" alt="Your brand logo" />
                <span *ngIf="!logoSrc()" class="logo-empty cf-mono">No logo</span>
              </div>
              <div class="logo-actions">
                <input
                  #logoInput
                  type="file"
                  class="hidden-input"
                  accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                  (change)="onLogoSelected($event)" />
                <button type="button" class="cf-btn-ghost" (click)="logoInput.click()" [disabled]="isUploading">
                  {{ isUploading ? 'Uploading…' : (logoSrc() ? 'Replace' : 'Upload logo') }}
                </button>
                <button type="button" class="link-danger" *ngIf="logoSrc()" (click)="removeLogo()" [disabled]="isUploading">
                  Remove
                </button>
                <span class="hint">PNG, JPG or WEBP · up to 4 MB · transparent PNG works best</span>
              </div>
            </div>
          </div>

          <div class="field">
            <span class="field-label">Colours</span>
            <div class="swatches">
              <label class="swatch" *ngFor="let c of colorFields">
                <input type="color" [ngModel]="valueOf(c.key)" (ngModelChange)="setColor(c.key, $event)" [attr.aria-label]="c.label" />
                <span class="swatch-chip" [style.background]="valueOf(c.key)"></span>
                <span class="swatch-meta">
                  <span class="swatch-name">{{ c.label }}</span>
                  <input
                    class="swatch-hex cf-mono"
                    type="text"
                    [ngModel]="valueOf(c.key)"
                    (ngModelChange)="setColor(c.key, $event)"
                    spellcheck="false"
                    maxlength="7"
                    [attr.aria-label]="c.label + ' hex value'" />
                </span>
                <span class="swatch-role">{{ c.role }}</span>
              </label>
            </div>
          </div>

          <div class="field">
            <span class="field-label">Typeface</span>
            <select class="select" [(ngModel)]="fontChoice">
              <option *ngFor="let f of fonts()" [value]="f.id">{{ f.label }}</option>
            </select>
            <span class="hint">{{ activeFontNote }}</span>
          </div>

          <div class="actions">
            <button type="button" class="cf-btn-primary" (click)="save()" [disabled]="isSaving || !isDirty">
              {{ isSaving ? 'Saving…' : (isDirty ? 'Save brand kit' : 'Saved') }}
            </button>
            <a routerLink="/create" class="secondary">Use it on a video →</a>
          </div>

          <div class="notice ok" *ngIf="savedMessage">{{ savedMessage }}</div>
          <div class="notice err" *ngIf="errorMessage">⚠️ {{ errorMessage }}</div>
        </section>

        <!-- ============ live preview ============ -->
        <section class="panel preview-panel">
          <div class="preview-head">
            <span class="field-label">Live preview</span>
            <span class="hint">A title card, drawn from these exact values</span>
          </div>

          <div class="preview" [style.background]="previewBackground">
            <img *ngIf="logoSrc() as src" class="preview-logo" [src]="src" alt="" />

            <div class="preview-body">
              <span class="preview-eyebrow" [style.color]="accentColor">YOUR BRAND</span>
              <span class="preview-title" [style.fontFamily]="previewFontStack" [style.fontWeight]="previewFontWeight">
                Comment l'IA transforme votre travail
              </span>
              <span class="preview-sub" [style.fontFamily]="previewFontStack">
                Une vidéo générée avec votre identité visuelle.
              </span>
            </div>

            <div class="preview-rule" [style.background]="accentColor"></div>
            <div class="preview-caption" [style.fontFamily]="previewFontStack">
              Découvrez comment transformer vos idées en contenu.
            </div>
          </div>

          <p class="preview-note">
            The logo is stamped top-right on every frame. Your primary and secondary colours
            replace the palette the AI Director would otherwise invent per video.
          </p>
        </section>
      </div>
    </div>
  `,
  styles: [`
    .bk { display: flex; flex-direction: column; gap: 22px; max-width: 1180px; margin: 0 auto; padding: 28px 32px 56px; }

    .bk-titles { display: flex; flex-direction: column; gap: 7px; }
    .eyebrow { font-size: 10.5px; color: var(--cf-text-dim); letter-spacing: .09em; text-transform: uppercase; }
    .bk-titles h1 { margin: 0; font-size: 26px; font-weight: 600; letter-spacing: -.022em; }
    .bk-sub { margin: 0; max-width: 560px; font-size: 12.5px; line-height: 1.6; color: var(--cf-text-muted); }

    .cols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
    @media (max-width: 900px) { .cols { grid-template-columns: 1fr; } }

    .panel {
      display: flex; flex-direction: column; gap: 20px;
      padding: 20px; border-radius: var(--cf-radius);
      border: 1px solid var(--cf-border-card); background: rgba(16, 16, 23, .72);
    }

    .field { display: flex; flex-direction: column; gap: 9px; }
    .field-label { font-size: 11.5px; color: var(--cf-text-2); }
    .hint { font-size: 11px; line-height: 1.5; color: var(--cf-text-dimmer); }

    /* — logo — */
    .hidden-input { display: none; }
    .logo-row { display: flex; gap: 14px; align-items: flex-start; }
    .logo-box {
      width: 108px; height: 76px; flex: none; border-radius: var(--cf-radius-sm);
      border: 1px solid var(--cf-border-card); background: rgba(255, 255, 255, .03);
      display: grid; place-items: center; overflow: hidden; padding: 8px;
    }
    .logo-box.empty { border-style: dashed; }
    .logo-box img { max-width: 100%; max-height: 100%; object-fit: contain; }
    .logo-empty { font-size: 10px; color: var(--cf-text-dimmer); }
    .logo-actions { display: flex; flex-direction: column; gap: 8px; align-items: flex-start; }
    .link-danger { all: unset; cursor: pointer; font-size: 11.5px; color: var(--cf-err-soft); }
    .link-danger:hover { text-decoration: underline; }

    /* — colours — */
    .swatches { display: flex; flex-direction: column; gap: 8px; }
    .swatch {
      position: relative; display: flex; align-items: center; gap: 11px;
      padding: 9px 11px; border-radius: var(--cf-radius-sm);
      border: 1px solid var(--cf-border-card); background: rgba(255, 255, 255, .02);
      cursor: pointer;
    }
    .swatch:hover { border-color: rgba(146, 118, 255, .35); }
    /* The native picker sits invisibly over its chip, so clicking the colour opens it. */
    .swatch input[type="color"] {
      position: absolute; left: 11px; top: 50%; transform: translateY(-50%);
      width: 30px; height: 30px; opacity: 0; cursor: pointer; border: none; padding: 0;
    }
    .swatch-chip {
      width: 30px; height: 30px; flex: none; border-radius: 7px;
      border: 1px solid rgba(255, 255, 255, .16);
    }
    .swatch-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
    .swatch-name { font-size: 12.5px; }
    .swatch-hex {
      all: unset; width: 74px; font-size: 11px; color: var(--cf-text-dimmer);
      border-bottom: 1px solid transparent; cursor: text;
    }
    .swatch-hex:focus { color: var(--cf-text); border-bottom-color: var(--cf-accent-ring); }
    .swatch-role { margin-left: auto; font-size: 10.5px; color: var(--cf-text-dimmer); text-align: right; }

    /* — typeface — */
    .select {
      all: unset; box-sizing: border-box; width: 100%; height: 36px; padding: 0 11px;
      border-radius: var(--cf-radius-sm); border: 1px solid var(--cf-border-card);
      background: rgba(255, 255, 255, .02); color: var(--cf-text); font-size: 12.5px; cursor: pointer;
    }
    .select:focus-visible { outline: 2px solid var(--cf-accent-ring); outline-offset: 2px; }
    .select option { background: #14141B; color: var(--cf-text); }

    .actions { display: flex; align-items: center; gap: 14px; margin-top: 2px; }
    .secondary { font-size: 12.5px; color: var(--cf-accent-link); text-decoration: none; }
    .secondary:hover { color: var(--cf-accent-link-hover); }

    .notice { padding: 9px 12px; border-radius: var(--cf-radius-sm); font-size: 12px; line-height: 1.5; }
    .notice.ok { border: 1px solid rgba(52, 211, 153, .3); background: rgba(52, 211, 153, .1); color: var(--cf-ok-soft); }
    .notice.err { border: 1px solid rgba(248, 113, 113, .3); background: rgba(248, 113, 113, .1); color: var(--cf-err-soft); }

    /* — preview — */
    .preview-panel { position: sticky; top: 20px; }
    .preview-head { display: flex; flex-direction: column; gap: 4px; }
    .preview {
      position: relative; aspect-ratio: 16 / 9; border-radius: var(--cf-radius-sm);
      overflow: hidden; padding: 26px 28px; display: flex; flex-direction: column; justify-content: center;
      border: 1px solid rgba(255, 255, 255, .09);
    }
    .preview-logo { position: absolute; right: 4%; top: 7%; width: 12%; object-fit: contain; opacity: .88; }
    .preview-body { display: flex; flex-direction: column; gap: 8px; max-width: 82%; }
    .preview-eyebrow { font-size: 10px; letter-spacing: .16em; font-weight: 600; }
    .preview-title { font-size: 25px; line-height: 1.15; letter-spacing: -.02em; color: #fff; }
    .preview-sub { font-size: 12px; color: rgba(255, 255, 255, .74); }
    .preview-rule { position: absolute; left: 0; right: 0; bottom: 46px; height: 2px; opacity: .85; }
    .preview-caption {
      position: absolute; left: 0; right: 0; bottom: 14px; text-align: center;
      font-size: 12px; color: rgba(255, 255, 255, .9);
      text-shadow: 0 1px 6px rgba(0, 0, 0, .8);
    }
    .preview-note { margin: 0; font-size: 11px; line-height: 1.55; color: var(--cf-text-dimmer); }

    @media (max-width: 860px) { .bk { padding: 22px 16px 48px; } .preview-panel { position: static; } }
  `]
})
export class BrandKitComponent implements OnInit {
  isLoading = true;
  isSaving = false;
  isUploading = false;
  savedMessage = '';
  errorMessage = '';

  primaryColor = '#0f172a';
  secondaryColor = '#38bdf8';
  accentColor = '#7c5cff';
  fontChoice = 'dejavu_sans';

  readonly fonts = signal<FontOption[]>([]);
  /** Bumped after a logo upload so the <img> refetches instead of showing the cached one. */
  private logoVersion = 0;
  private saved = { primary: '', secondary: '', accent: '', font: '' };

  readonly colorFields = [
    { key: 'primary' as const, label: 'Primary', role: 'Backgrounds' },
    { key: 'secondary' as const, label: 'Secondary', role: 'Supporting tone' },
    { key: 'accent' as const, label: 'Accent', role: 'Highlights & rules' }
  ];

  constructor(public brand: BrandKitService) {}

  ngOnInit(): void {
    this.brand.fonts().subscribe({
      next: f => this.fonts.set(f),
      // A one-option fallback is better than an empty dropdown that cannot be submitted.
      error: () => this.fonts.set([{ id: 'dejavu_sans', label: 'DejaVu Sans', note: '' }])
    });

    this.brand.refresh().subscribe({
      next: kit => {
        this.primaryColor = kit.primary_color;
        this.secondaryColor = kit.secondary_color;
        this.accentColor = kit.accent_color;
        this.fontChoice = kit.font_choice;
        this.snapshot();
        this.isLoading = false;
      },
      error: err => {
        this.isLoading = false;
        this.errorMessage = err.error?.detail || 'Could not load your brand kit.';
      }
    });
  }

  // ------------------------------------------------------------------ state

  private snapshot(): void {
    this.saved = {
      primary: this.primaryColor,
      secondary: this.secondaryColor,
      accent: this.accentColor,
      font: this.fontChoice
    };
  }

  get isDirty(): boolean {
    return this.primaryColor !== this.saved.primary
      || this.secondaryColor !== this.saved.secondary
      || this.accentColor !== this.saved.accent
      || this.fontChoice !== this.saved.font;
  }

  valueOf(key: 'primary' | 'secondary' | 'accent'): string {
    if (key === 'primary') return this.primaryColor;
    if (key === 'secondary') return this.secondaryColor;
    return this.accentColor;
  }

  /**
   * Accepts partial input from the hex field without fighting the user.
   *
   * Typing "#0f1" is a valid state on the way to "#0f172a", so the value is stored as
   * typed and only validated on save — clamping mid-keystroke would make the field
   * impossible to edit.
   */
  setColor(key: 'primary' | 'secondary' | 'accent', value: string): void {
    const v = (value || '').trim();
    if (key === 'primary') this.primaryColor = v;
    else if (key === 'secondary') this.secondaryColor = v;
    else this.accentColor = v;
    this.savedMessage = '';
  }

  logoSrc(): string | null {
    return this.brand.logoSrc(this.logoVersion);
  }

  // ---------------------------------------------------------------- preview

  /** Primary into secondary, the same two-stop treatment the renderer's scenes use. */
  get previewBackground(): string {
    return `linear-gradient(140deg, ${this.safe(this.primaryColor, '#0f172a')} 0%, ${this.safe(this.secondaryColor, '#38bdf8')} 165%)`;
  }

  /**
   * The preview approximates the render font rather than matching it exactly: the
   * renderer draws with the bundled DejaVu TTF, which the browser does not have. A
   * generic sans is the honest stand-in — the preview is for colour and layout.
   */
  get previewFontStack(): string {
    return `"DejaVu Sans", "Verdana", "Bitstream Vera Sans", system-ui, sans-serif`;
  }

  get previewFontWeight(): number {
    return this.fontChoice === 'dejavu_sans_bold' ? 700 : 600;
  }

  get activeFontNote(): string {
    return this.fonts().find(f => f.id === this.fontChoice)?.note || '';
  }

  private safe(value: string, fallback: string): string {
    return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test((value || '').trim()) ? value.trim() : fallback;
  }

  // ---------------------------------------------------------------- actions

  save(): void {
    const bad = this.colorFields.find(c => !/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(this.valueOf(c.key).trim()));
    if (bad) {
      this.errorMessage = `${bad.label} is not a valid hex colour (use #RGB or #RRGGBB).`;
      return;
    }

    this.isSaving = true;
    this.errorMessage = '';
    this.savedMessage = '';
    this.brand.save({
      primary_color: this.primaryColor.trim(),
      secondary_color: this.secondaryColor.trim(),
      accent_color: this.accentColor.trim(),
      font_choice: this.fontChoice
    }).subscribe({
      next: kit => {
        this.isSaving = false;
        this.primaryColor = kit.primary_color;
        this.secondaryColor = kit.secondary_color;
        this.accentColor = kit.accent_color;
        this.fontChoice = kit.font_choice;
        this.snapshot();
        this.savedMessage = 'Brand kit saved. Tick “Use my brand kit” on the create page to apply it.';
      },
      error: err => {
        this.isSaving = false;
        this.errorMessage = err.error?.detail?.[0]?.msg || err.error?.detail || 'Could not save your brand kit.';
      }
    });
  }

  onLogoSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    // Cleared immediately so re-picking the same file still fires a change event.
    input.value = '';
    if (!file) return;

    this.isUploading = true;
    this.errorMessage = '';
    this.savedMessage = '';
    this.brand.uploadLogo(file).subscribe({
      next: () => {
        this.isUploading = false;
        this.logoVersion++;
        this.savedMessage = 'Logo uploaded. It will be stamped on the top-right of every frame.';
      },
      error: err => {
        this.isUploading = false;
        this.errorMessage = err.error?.detail || 'Could not upload that logo.';
      }
    });
  }

  removeLogo(): void {
    this.isUploading = true;
    this.brand.deleteLogo().subscribe({
      next: () => {
        this.isUploading = false;
        this.logoVersion++;
        this.savedMessage = 'Logo removed.';
      },
      error: err => {
        this.isUploading = false;
        this.errorMessage = err.error?.detail || 'Could not remove the logo.';
      }
    });
  }
}
