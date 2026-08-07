import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { BrandLogoComponent } from '../../shared/brand-logo.component';

@Component({
  selector: 'app-welcome',
  standalone: true,
  imports: [RouterLink, BrandLogoComponent],
  template: `
    <div class="flex min-h-screen flex-col items-center gap-8 bg-bg px-6 py-12">
      <header class="max-w-[560px] text-center">
        <app-brand-logo size="lg" class="mb-5 justify-center" />
        <h1 class="m-0 mb-3 text-[clamp(1.75rem,4vw,2.25rem)] font-semibold leading-tight">Retail loss prevention, powered by your cameras</h1>
        <p class="m-0 mb-3 text-[1.05rem] leading-[1.6] text-ink-muted">
          Connect in-store cameras to AI analysis and staff alerts — review suspicious activity quickly and confidently.
        </p>
        <p class="muted m-0 mb-7 text-[0.95rem]">Takes about 15 minutes to set up your first store.</p>
        <a class="inline-block rounded-ctl bg-accent px-5 py-2.5 text-[0.95rem] font-medium text-white no-underline hover:bg-accent-2 hover:text-white" routerLink="/login">Sign in</a>
      </header>

      <section class="card w-full max-w-[480px] !mb-0 !p-6">
        <h2 class="m-0 mb-4 text-[0.9rem] font-semibold uppercase tracking-[0.05em] text-ink-muted">Getting started</h2>
        <ol class="m-0 flex flex-col gap-4 pl-5 leading-normal">
          <li>
            <strong class="mb-1 block font-semibold">Account setup</strong>
            <span class="text-[0.9rem] text-ink-muted">Your onetix administrator creates your store and staff login.</span>
          </li>
          <li>
            <strong class="mb-1 block font-semibold">Download the Windows connector</strong>
            <span class="text-[0.9rem] text-ink-muted">After signing in, download the installer from Get started or Setup &amp; Zones.</span>
          </li>
          <li>
            <strong class="mb-1 block font-semibold">Install on the shop PC</strong>
            <span class="text-[0.9rem] text-ink-muted">Run the installer, enter your setup code, and add RTSP camera URLs.</span>
          </li>
        </ol>
      </section>

      <p class="muted text-[0.85rem]">Support: contact your onetix administrator</p>
    </div>
  `,
})
export class WelcomeComponent {}
