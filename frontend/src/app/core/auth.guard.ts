import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

/**
 * Blocks protected routes when there is no usable token, remembering the
 * attempted URL so the user is returned there after signing in.
 */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.hasValidToken()) {
    return true;
  }

  // Expired token still sitting in storage: clear it so the shell doesn't keep
  // showing a signed-in user.
  if (auth.token) {
    auth.logout(false);
  }

  return router.createUrlTree(['/login'], {
    queryParams: state.url && state.url !== '/' ? { returnUrl: state.url } : {}
  });
};

/** Keeps signed-in users off /login and /register. */
export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.hasValidToken() ? router.createUrlTree(['/create']) : true;
};
