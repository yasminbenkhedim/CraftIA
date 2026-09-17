import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { AppShellComponent } from './components/app-shell/app-shell.component';

/** Routes rendered full-bleed, without the sidebar/header chrome. */
const CHROMELESS_ROUTES = ['/login', '/register'];

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, AppShellComponent],
  template: `
    <ng-container *ngIf="showChrome(); else bare">
      <app-shell>
        <router-outlet></router-outlet>
      </app-shell>
    </ng-container>

    <ng-template #bare>
      <router-outlet></router-outlet>
    </ng-template>
  `
})
export class AppComponent {
  title = 'CreateFlow AI';

  /** False on the auth screens, which own the whole viewport. */
  readonly showChrome = signal(true);

  constructor(router: Router) {
    this.showChrome.set(!this.isChromeless(router.url));
    router.events
      .pipe(filter((e): e is NavigationEnd => e instanceof NavigationEnd))
      .subscribe(e => this.showChrome.set(!this.isChromeless(e.urlAfterRedirects)));
  }

  private isChromeless(url: string): boolean {
    const path = (url || '').split('?')[0];
    return CHROMELESS_ROUTES.some(r => path === r || path.startsWith(r + '/'));
  }
}
