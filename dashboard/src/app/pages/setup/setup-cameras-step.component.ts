import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-cameras-step',
  standalone: true,
  imports: [FormsModule],
  template: `
    <ul class="muted small m-0 mb-3 pl-[18px]">
      <li>Camera network addresses or video links from your installer</li>
      <li>One camera selected to draw zones in the next step</li>
    </ul>

    <div class="grid grid-cols-1 gap-4 min-[992px]:grid-cols-3">
      <div class="card !mb-0">
        <h3>Your store</h3>
        @for (s of ctx.stores; track s.id) {
          <div class="row-item" [class.sel]="s.id === ctx.storeId" (click)="ctx.selectStore(s.id)">
            {{ s.name }}
          </div>
        }
        @if (ctx.auth.isAdmin()) {
          <div class="mt-2.5 flex gap-1.5">
            <input placeholder="New store name" [(ngModel)]="ctx.newStoreName" />
            <button (click)="ctx.addStore()">Add</button>
          </div>
        }
      </div>

      <div class="card !mb-0">
        <div class="flex items-center justify-between">
          <h3 class="m-0">Cameras</h3>
          @if (ctx.cameras.length) {
            <div>
              <button class="ghost small" (click)="ctx.toggleAllCameras()">
                {{ ctx.selectedCameraIds.size === ctx.cameras.length ? 'Clear all' : 'Select all' }}
              </button>
              @if (ctx.selectedCameraIds.size) {
                <button class="ghost small !text-danger" (click)="ctx.removeSelectedCameras()">
                  Remove {{ ctx.selectedCameraIds.size }}
                </button>
              }
            </div>
          }
        </div>
        @if (!ctx.storeId) { <p class="muted">Select a store first.</p> }
        @for (c of ctx.cameras; track c.id) {
          <div class="row-item" [class.sel]="c.id === ctx.cameraId" (click)="ctx.selectCamera(c.id)">
            <input type="checkbox" [checked]="ctx.selectedCameraIds.has(c.id)"
                   (click)="$event.stopPropagation()" (change)="ctx.toggleCameraSelection(c.id)" />
            <div>
              <span>{{ c.name }}</span>
              <span class="muted small"> [{{ c.status }}]</span>
            </div>
          </div>
        }
        @if (ctx.storeId) {
          <div class="mt-3 flex flex-col gap-1.5">
            <div class="flex flex-col gap-0.5">
              <label class="text-xs">Camera name</label>
              <input placeholder="e.g. Front counter" [(ngModel)]="ctx.newCamName" />
            </div>
            <div class="flex flex-col gap-0.5">
              <label class="text-xs">Video link</label>
              <input placeholder="Paste the camera video address from your installer" [(ngModel)]="ctx.newCamUrl" />
            </div>
            <button type="button" class="cursor-pointer border-none !bg-transparent !p-0 text-left text-[0.85rem] !text-accent font-normal" (click)="ctx.showOnvifForm = !ctx.showOnvifForm">
              {{ ctx.showOnvifForm ? 'Hide advanced camera setup' : 'Advanced camera setup' }}
            </button>
            @if (ctx.showOnvifForm) {
              <div class="flex flex-col gap-1.5 py-2">
                <div class="flex flex-col gap-0.5">
                  <label class="text-xs">Camera IP</label>
                  <input placeholder="192.168.1.64" [(ngModel)]="ctx.newOnvifHost" />
                </div>
                <div class="flex flex-col gap-0.5">
                  <label class="text-xs">Port</label>
                  <input type="number" placeholder="80" [(ngModel)]="ctx.newOnvifPort" />
                </div>
              </div>
            }
            <button (click)="ctx.addCamera()" [disabled]="!ctx.newCamName">Add camera</button>
          </div>
        }
      </div>

      <div class="card !mb-0">
        <h3>Zones on this camera</h3>
        @if (!ctx.cameraId) { <p class="muted">Select a camera to see its zones.</p> }
        @for (z of ctx.zones; track z.id) {
          <div class="row-item">
            {{ z.name }} <span class="muted small">[{{ z.zoneType }}]</span>
            <button class="ghost small" (click)="ctx.deleteZone(z.id)">×</button>
          </div>
        }
      </div>
    </div>

    @if (ctx.selectedCamera) {
      <div class="card mt-4 !mb-0">
        <div class="mb-3 flex items-center justify-between">
          <h3 class="m-0">{{ ctx.selectedCamera.name }}</h3>
          <div class="flex flex-wrap gap-2">
            <button class="ghost small" (click)="ctx.startCameraEdit()">Edit</button>
            <button class="ghost small !text-danger" (click)="ctx.removeCamera(ctx.selectedCamera!.id)">Remove</button>
            <button class="ghost small" (click)="ctx.testStream()" [disabled]="ctx.testingStream">
              {{ ctx.testingStream ? 'Testing…' : 'Test video' }}
            </button>
          </div>
        </div>

        @if (ctx.editingCamera) {
          <div class="grid grid-cols-[repeat(2,minmax(220px,1fr))] gap-3">
            <label class="flex flex-col gap-1 text-[0.8rem]">Name<input [(ngModel)]="ctx.editCamName" /></label>
            <label class="flex flex-col gap-1 text-[0.8rem]">Video link<input [(ngModel)]="ctx.editCamUrl" autocomplete="off" /></label>
            <div class="flex gap-2">
              <button (click)="ctx.saveCameraEdit()" [disabled]="ctx.savingCamera">Save</button>
              <button class="ghost" (click)="ctx.editingCamera = false">Cancel</button>
            </div>
          </div>
        } @else {
          <div class="mb-1 flex gap-4 text-[0.85rem]">
            <span class="min-w-[100px] text-[0.8rem] text-ink-muted">Status</span>
            <span class="badge" [class]="ctx.selectedCamera.status.toLowerCase()">{{ ctx.selectedCamera.status }}</span>
          </div>
          <div class="mb-1 flex gap-4 text-[0.85rem]">
            <span class="min-w-[100px] text-[0.8rem] text-ink-muted">Video link</span>
            <span class="break-all">{{ ctx.maskedRtsp(ctx.selectedCamera.rtspUrl) }}</span>
          </div>
        }

        @if (ctx.streamTestResult) {
          <div [class]="ctx.streamTestResult.ok
                 ? 'mt-3 rounded-ctl bg-success-soft px-3 py-2 text-[0.82rem] text-success'
                 : 'mt-3 rounded-ctl bg-danger-soft px-3 py-2 text-[0.82rem] text-danger'">
            {{ ctx.streamTestResult.message }}
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .row-item { padding: .4rem .5rem; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .row-item:hover { background: var(--accent-soft); }
    .row-item.sel { background: var(--accent-soft); border-left: 2px solid var(--accent); }
  `],
})
export class SetupCamerasStepComponent {
  readonly ctx = inject(SetupContextService);
}
