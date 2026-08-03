import { Component, OnInit, OnDestroy } from '@angular/core';
import { NavigationEnd, Router, RouterOutlet } from '@angular/router';
import { filter, Subscription } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `<router-outlet></router-outlet>`,
})
export class AppComponent implements OnInit, OnDestroy {
  private sub?: Subscription;

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.applyBodyClass(this.router.url);
    this.sub = this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe((e) => this.applyBodyClass((e as NavigationEnd).urlAfterRedirects));
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  private applyBodyClass(url: string): void {
    const locked = url.startsWith('/app');
    document.body.classList.toggle('shell-locked', locked);
  }
}
