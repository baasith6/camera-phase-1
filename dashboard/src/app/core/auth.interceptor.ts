import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

const TOKEN_KEY = 'onevo_token';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const router = inject(Router);
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
  }
  return next(req).pipe(
    catchError((err) => {
      if (err.status === 401 && !req.url.includes('/api/auth/login')) {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem('onevo_store_id');
        router.navigate(['/login']);
      }
      return throwError(() => err);
    }),
  );
};
