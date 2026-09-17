import { Routes } from '@angular/router';
import { HomeComponent } from './pages/home/home.component';
import { CreateJobComponent } from './pages/create-job/create-job.component';
import { JobDetailComponent } from './pages/job-detail/job-detail.component';
import { BrandKitComponent } from './pages/brand-kit/brand-kit.component';
import { LibraryComponent } from './pages/library/library.component';
import { PricingComponent } from './pages/pricing/pricing.component';
import { LoginComponent } from './pages/login/login.component';
import { RegisterComponent } from './pages/register/register.component';
import { authGuard, guestGuard } from './core/auth.guard';

export const routes: Routes = [
  // Public — signed-in users are bounced to /create by guestGuard.
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },

  // Protected
  { path: '', component: HomeComponent, canActivate: [authGuard] },
  { path: 'create', component: CreateJobComponent, canActivate: [authGuard] },
  // Finished work, as assets rather than as runs. The dashboard stays the process
  // view; this is the one that answers "where is the deck I made last month?".
  { path: 'library', component: LibraryComponent, canActivate: [authGuard] },
  { path: 'brand-kit', component: BrandKitComponent, canActivate: [authGuard] },
  { path: 'jobs/:id', component: JobDetailComponent, canActivate: [authGuard] },
  // Placeholder while no payment provider is integrated: it lists the plan
  // allowances and says plainly that checkout is not live yet.
  { path: 'pricing', component: PricingComponent, canActivate: [authGuard] },

  { path: '**', redirectTo: '' }
];
