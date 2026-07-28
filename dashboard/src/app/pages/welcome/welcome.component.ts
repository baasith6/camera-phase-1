import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-welcome',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="welcome">
      <header class="hero">
        <div class="brand"><span class="mark">◆</span> ONEVO</div>
        <h1>Retail loss prevention, powered by your cameras</h1>
        <p class="lead">
          ONEVO connects in-store cameras to AI analysis and staff alerts — so your team can
          review suspicious activity quickly and confidently.
        </p>
        <a class="cta" routerLink="/login">Sign in to Staff Console</a>
      </header>

      <section class="steps card">
        <h2>Getting started</h2>
        <ol>
          <li>
            <strong>Account setup</strong>
            <span>Your ONEVO administrator creates your store and staff login.</span>
          </li>
          <li>
            <strong>Download the Windows connector</strong>
            <span>After signing in, download the installer from <em>Get started</em> or <em>Setup &amp; Zones</em>.</span>
          </li>
          <li>
            <strong>Install on the shop PC</strong>
            <span>Run the installer as Administrator, enter your setup code, and add RTSP camera URLs.</span>
          </li>
        </ol>
        <p class="note muted">
          Installer download requires sign-in (Admin, Manager, or Installer role).
          Shop technicians need a setup code from your ONEVO admin.
        </p>
      </section>

      <section class="links">
        <a routerLink="/login">Staff sign in</a>
        <span class="sep">·</span>
        <span class="muted">Support: contact your ONEVO administrator</span>
      </section>
    </div>
  `,
  styles: [`
    .welcome {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 3rem 1.5rem 2rem;
      gap: 2rem;
    }
    .hero {
      max-width: 640px;
      text-align: center;
    }
    .brand {
      font-weight: 700;
      font-size: 1.5rem;
      letter-spacing: .04em;
      margin-bottom: 1.25rem;
      background: linear-gradient(120deg, var(--accent-2), var(--accent), #c4b5fd);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .mark { filter: drop-shadow(0 0 8px var(--accent-glow)); }
    h1 {
      margin: 0 0 .75rem;
      font-size: clamp(1.5rem, 4vw, 2rem);
      line-height: 1.25;
    }
    .lead {
      color: var(--text-muted);
      margin: 0 0 1.5rem;
      line-height: 1.6;
    }
    .cta {
      display: inline-block;
      padding: .65rem 1.25rem;
      border-radius: var(--radius-sm);
      background: var(--accent-soft);
      border: 1px solid var(--accent);
      color: var(--accent-2);
      text-decoration: none;
      font-weight: 600;
    }
    .cta:hover { background: rgba(139, 92, 246, .2); }
    .steps {
      max-width: 560px;
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.5rem;
    }
    .steps h2 { margin: 0 0 1rem; font-size: 1rem; }
    .steps ol {
      margin: 0;
      padding-left: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .steps li { line-height: 1.45; }
    .steps li strong { display: block; margin-bottom: .15rem; }
    .steps li span { color: var(--text-muted); font-size: .92rem; }
    .note { font-size: .85rem; margin: 1.25rem 0 0; }
    .muted { color: var(--text-muted); }
    .links {
      display: flex;
      align-items: center;
      gap: .5rem;
      flex-wrap: wrap;
      font-size: .88rem;
    }
    .links a { color: var(--accent-2); }
    .sep { color: var(--border-strong); }
  `],
})
export class WelcomeComponent {}
