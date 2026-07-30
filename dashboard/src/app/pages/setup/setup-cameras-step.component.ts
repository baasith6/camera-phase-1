import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SetupContextService } from './setup-context.service';

@Component({
  selector: 'app-setup-cameras-step',
  standalone: true,
  imports: [FormsModule],
  template: `
    <ul class="need-list muted small">
      <li>Camera network addresses or video links from your installer</li>
      <li>One camera selected to draw zones in the next step</li>
    </ul>

    <div class="grid3">
      <div class="card">
        <h3>Your store</h3>
        @for (s of ctx.stores; track s.id) {
          <div class="row-item" [class.sel]="s.id === ctx.storeId" (click)="ctx.selectStore(s.id)">
            {{ s.name }}
          </div>
        }
        @if (ctx.auth.isAdmin()) {
          <div class="add-row">
            <input placeholder="New store name" [(ngModel)]="ctx.newStoreName" />
            <button (click)="ctx.addStore()">Add</button>
          </div>
        }
      </div>

      <div class="card">
        <div class="cam-list-header">
          <h3>Cameras</h3>
          @if (ctx.cameras.length) {
            <div>
              <button class="ghost small" (click)="ctx.toggleAllCameras()">
                {{ ctx.selectedCameraIds.size === ctx.cameras.length ? 'Clear all' : 'Select all' }}
              </button>
              @if (ctx.selectedCameraIds.size) {
                <button class="ghost small danger-text" (click)="ctx.removeSelectedCameras()">
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
          <div class="add-col">
            <div class="field-row">
              <label>Camera name</label>
              <input placeholder="e.g. Front counter" [(ngModel)]="ctx.newCamName" />
            </div>
            <div class="field-row">
              <label>Video link</label>
              <input placeholder="Paste the camera video address from your installer" [(ngModel)]="ctx.newCamUrl" />
            </div>
            <button type="button" class="link-toggle" (click)="ctx.showOnvifForm = !ctx.showOnvifForm">
              {{ ctx.showOnvifForm ? 'Hide advanced camera setup' : 'Advanced camera setup' }}
            </button>
            @if (ctx.showOnvifForm) {
              <div class="onvif-fields">
                <div class="field-row">
                  <label>Camera IP</label>
                  <input placeholder="192.168.1.64" [(ngModel)]="ctx.newOnvifHost" />
                </div>
                <div class="field-row">
                  <label>Port</label>
                  <input type="number" placeholder="80" [(ngModel)]="ctx.newOnvifPort" />
                </div>
              </div>
            }
            <button (click)="ctx.addCamera()" [disabled]="!ctx.newCamName">Add camera</button>
          </div>
        }
      </div>

      <div class="card">
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
      <div class="card cam-detail">
        <div class="cam-detail-header">
          <h3>{{ ctx.selectedCamera.name }}</h3>
          <div class="cam-actions">
            <button class="ghost small" (click)="ctx.startCameraEdit()">Edit</button>
            <button class="ghost small danger-text" (click)="ctx.removeCamera(ctx.selectedCamera!.id)">Remove</button>
            <button class="ghost small" (click)="ctx.testStream()" [disabled]="ctx.testingStream">
              {{ ctx.testingStream ? 'Testing…' : 'Test video' }}
            </button>
          </div>
        </div>

        @if (ctx.editingCamera) {
          <div class="edit-grid">
            <label>Name<input [(ngModel)]="ctx.editCamName" /></label>
            <label>Video link<input [(ngModel)]="ctx.editCamUrl" autocomplete="off" /></label>
            <div class="row">
              <button (click)="ctx.saveCameraEdit()" [disabled]="ctx.savingCamera">Save</button>
              <button class="ghost" (click)="ctx.editingCamera = false">Cancel</button>
            </div>
          </div>
        } @else {
          <div class="detail-row">
            <span class="dk">Status</span>
            <span class="badge" [class]="ctx.selectedCamera.status.toLowerCase()">{{ ctx.selectedCamera.status }}</span>
          </div>
          <div class="detail-row">
            <span class="dk">Video link</span>
            <span class="dv">{{ ctx.maskedRtsp(ctx.selectedCamera.rtspUrl) }}</span>
          </div>
        }

        @if (ctx.streamTestResult) {
          <div class="test-result" [class.ok]="ctx.streamTestResult.ok" [class.err]="!ctx.streamTestResult.ok">
            {{ ctx.streamTestResult.message }}
          </div>
        }
      </div>
    }
  `,
  styles: [`
    .need-list { margin: 0 0 12px; padding-left: 18px; }
    .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
    @media (max-width: 992px) { .grid3 { grid-template-columns: 1fr; } }
    .row-item { padding: .4rem .5rem; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .row-item:hover { background: var(--accent-soft); }
    .row-item.sel { background: var(--accent-soft); border-left: 2px solid var(--accent); }
    .add-row { display: flex; gap: .4rem; margin-top: .6rem; }
    .add-col { display: flex; flex-direction: column; gap: .4rem; margin-top: .75rem; }
    .field-row { display: flex; flex-direction: column; gap: .15rem; }
    .field-row label { font-size: .75rem; color: var(--text-muted); }
    .link-toggle { background: none; border: none; color: var(--accent); padding: 0; font-size: .85rem; cursor: pointer; text-align: left; }
    .onvif-fields { padding: .5rem 0; display: flex; flex-direction: column; gap: .4rem; }
    .cam-list-header { display: flex; justify-content: space-between; align-items: center; }
    .cam-list-header h3 { margin: 0; }
    .danger-text { color: var(--danger) !important; }
    .cam-detail { margin-top: 1rem; }
    .cam-detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .75rem; }
    .cam-detail-header h3 { margin: 0; }
    .cam-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .edit-grid { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: .7rem; }
    .edit-grid label { display: flex; flex-direction: column; gap: .25rem; font-size: .8rem; color: var(--text-muted); }
    .detail-row { display: flex; gap: 1rem; font-size: .85rem; margin-bottom: .3rem; }
    .dk { min-width: 100px; color: var(--text-muted); font-size: .8rem; }
    .dv { word-break: break-all; }
    .badge { padding: .18rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
    .badge.online, .badge.active { background: var(--success-soft); color: var(--success); }
    .test-result { margin-top: .75rem; padding: .5rem .75rem; border-radius: var(--radius-sm); font-size: .82rem; }
    .test-result.ok { background: var(--success-soft); color: var(--success); }
    .test-result.err { background: var(--danger-soft); color: var(--danger); }
    .small { font-size: .8rem; }
  `],
})
export class SetupCamerasStepComponent {
  readonly ctx = inject(SetupContextService);
}
