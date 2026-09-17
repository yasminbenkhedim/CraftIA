import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Attaches the bearer token to every API request and turns a 401 into a clean
 * logout + redirect, so an expired token can never leave the app stuck on a
 * screen that silently fails.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const token = auth.token;

  // Never attach the token to the auth endpoints themselves: login/register are
  // public, and sending a stale token there just muddies the failure mode.
  const isAuthEndpoint = req.url.includes('/api/auth/login') || req.url.includes('/api/auth/register');

  const authorized = token && !isAuthEndpoint
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(authorized).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !isAuthEndpoint) {
        // The token is expired or invalid. Drop it and send the user to /login,
        // preserving where they were so they land back there after signing in.
        auth.logout(false);
        const returnUrl = router.url && !router.url.startsWith('/login')
          ? router.url
          : undefined;
        router.navigate(['/login'], returnUrl ? { queryParams: { returnUrl } } : {});
      }
      return throwError(() => err);
    })
  );
};
