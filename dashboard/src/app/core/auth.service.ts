import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { LoginResponse } from './models';
import { API_BASE } from './api.config';

const TOKEN_KEY = 'onevo_token';
const EMAIL_KEY = 'onevo_email';
const ROLE_KEY = 'onevo_role';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly email = signal<string | null>(localStorage.getItem(EMAIL_KEY));
  readonly role = signal<string | null>(localStorage.getItem(ROLE_KEY));

  constructor(private http: HttpClient) {}

  login(email: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>(`${API_BASE}/api/auth/login`, { email, password }).pipe(
      tap((res) => {
        localStorage.setItem(TOKEN_KEY, res.token);
        localStorage.setItem(EMAIL_KEY, res.email);
        localStorage.setItem(ROLE_KEY, res.role);
        this.email.set(res.email);
        this.role.set(res.role);
      })
    );
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(ROLE_KEY);
    this.email.set(null);
    this.role.set(null);
  }

  get token(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  get isAuthenticated(): boolean {
    return !!this.token;
  }
}
