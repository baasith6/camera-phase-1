import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-welcome',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="welcome">
      <header class="hero">
        <div class="brand">onetix</div>
        <h1>Retail loss prevention, powered by your cameras</h1>
        <p class="lead">
          Connect in-store cameras to AI analysis and staff alerts — review suspicious activity quickly and confidently.
        </p>
        <a class="cta" routerLink="/login">Sign in to Staff Console</a>
      </header>

      <section class="steps card">
        <h2>Getting started</h2>
        <ol>
          <li>
            <strong>Account setup</strong>
            <span>Your onetix administrator creates your store and staff login.</span>
          </li>
          <li>
            <strong>Download the Windows connector</strong>
            <span>After signing in, download the installer from Get started or Setup &amp; Zones.</span>
          </li>
          <li>
            <strong>Install on the shop PC</strong>
            <span>Run the installer, enter your setup code, and add RTSP camera URLs.</span>
          </li>
        </ol>
      </section>

      <p class="footer muted">Support: contact your onetix administrator</p>
    </div>
  `,
  styles: [`
    .welcome {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px 24px;
      gap: 32px;
      background: var(--bg);
    }
    .hero { max-width: 560px; text-align: center; }
    .brand {
      font-weight: 700;
      font-size: 1.25rem;
      letter-spacing: -0.03em;
      color: var(--text);
      margin-bottom: 20px;
    }
    h1 {
      margin: 0 0 12px;
      font-size: clamp(1.75rem, 4vw, 2.25rem);
      line-height: 1.2;
      font-weight: 600;
    }
    .lead {
      color: var(--text-muted);
      margin: 0 0 28px;
      line-height: 1.6;
      font-size: 1.05rem;
    }
    .cta {
      display: inline-block;
      padding: 10px 20px;
      border-radius: var(--radius-sm);
      background: var(--accent);
      color: white;
      text-decoration: none;
      font-weight: 500;
      font-size: 0.95rem;
    }
    .cta:hover { background: var(--accent-2); color: white; }
    .steps {
      max-width: 480px;
      width: 100%;
      padding: 24px;
    }
    .steps h2 { margin: 0 0 16px; font-size: 0.9rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
    .steps ol {
      margin: 0;
      padding-left: 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .steps li { line-height: 1.5; }
    .steps li strong { display: block; margin-bottom: 4px; font-weight: 600; }
    .steps li span { color: var(--text-muted); font-size: 0.9rem; }
    .footer { font-size: 0.85rem; }
    .muted { color: var(--text-muted); }
  `],
})
export class WelcomeComponent {}
