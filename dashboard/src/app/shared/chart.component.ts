import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnChanges,
  OnDestroy,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import type { ChartConfiguration } from 'chart.js';

type ChartModule = typeof import('chart.js');

@Component({
  selector: 'app-chart',
  standalone: true,
  template: `<div class="relative h-[260px]"><canvas #canvas></canvas></div>`,
})
export class ChartComponent implements AfterViewInit, OnChanges, OnDestroy {
  @ViewChild('canvas') canvasRef!: ElementRef<HTMLCanvasElement>;
  @Input({ required: true }) config!: ChartConfiguration;

  private chart?: InstanceType<ChartModule['Chart']>;
  private chartModule?: ChartModule;

  ngAfterViewInit(): void {
    void this.render();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['config'] && !changes['config'].firstChange) {
      void this.render();
    }
  }

  ngOnDestroy(): void {
    this.chart?.destroy();
  }

  private async loadChartModule(): Promise<ChartModule> {
    if (!this.chartModule) {
      const mod = await import('chart.js');
      mod.Chart.register(...mod.registerables);
      this.chartModule = mod;
    }
    return this.chartModule;
  }

  private async render(): Promise<void> {
    if (!this.canvasRef?.nativeElement || !this.config) return;
    const { Chart } = await this.loadChartModule();
    this.chart?.destroy();
    this.chart = new Chart(this.canvasRef.nativeElement, this.config);
  }
}
