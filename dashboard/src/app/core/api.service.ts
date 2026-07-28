import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE } from './api.config';
import { Alert, Camera, ClipDetail, ClipListItem, Connector, InstallerInfo, PipelineHealth, RiskConfig, SetupCodeResponse, Store, StoreOverview, UserAccount, Zone } from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // Stores
  listStores(): Observable<Store[]> { return this.http.get<Store[]>(`${API_BASE}/api/stores`); }
  listStoreOverview(): Observable<StoreOverview[]> {
    return this.http.get<StoreOverview[]>(`${API_BASE}/api/stores/overview`);
  }
  createStore(body: {
    name: string;
    organization?: string;
    notificationEmail?: string;
    alertVisibilityMode?: string;
  }): Observable<Store> {
    return this.http.post<Store>(`${API_BASE}/api/stores`, body);
  }
  updateStore(id: string, body: {
    name?: string;
    alertVisibilityMode?: string;
    notificationEmail?: string;
  }): Observable<Store> {
    return this.http.put<Store>(`${API_BASE}/api/stores/${id}`, body);
  }

  // Users (Admin)
  listUsers(storeId?: string): Observable<UserAccount[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<UserAccount[]>(`${API_BASE}/api/users${q}`);
  }
  createUser(body: {
    email: string;
    password: string;
    role: string;
    storeId?: string | null;
  }): Observable<UserAccount> {
    return this.http.post<UserAccount>(`${API_BASE}/api/users`, body);
  }

  // Cameras
  listCameras(storeId?: string): Observable<Camera[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<Camera[]>(`${API_BASE}/api/cameras${q}`);
  }
  getCamera(id: string): Observable<Camera> {
    return this.http.get<Camera>(`${API_BASE}/api/cameras/${id}`);
  }
  createCamera(storeId: string, name: string, rtspUrl: string,
               onvifHost?: string, onvifPort?: number): Observable<Camera> {
    return this.http.post<Camera>(`${API_BASE}/api/cameras`,
      { storeId, name, rtspUrl, onvifHost, onvifPort });
  }
  updateCamera(id: string, body: {
    name?: string; rtspUrl?: string; status?: string;
    onvifHost?: string; onvifPort?: number;
  }): Observable<Camera> {
    return this.http.put<Camera>(`${API_BASE}/api/cameras/${id}`, body);
  }
  testStream(id: string): Observable<any> {
    return this.http.post<any>(`${API_BASE}/api/cameras/${id}/test-stream`, {});
  }

  // Zones
  listZones(cameraId: string): Observable<Zone[]> {
    return this.http.get<Zone[]>(`${API_BASE}/api/zones?cameraId=${cameraId}`);
  }
  createZone(cameraId: string, name: string, zoneType: string, polygonJson: string): Observable<Zone> {
    return this.http.post<Zone>(`${API_BASE}/api/zones`, { cameraId, name, zoneType, polygonJson });
  }
  deleteZone(id: string): Observable<void> {
    return this.http.delete<void>(`${API_BASE}/api/zones/${id}`);
  }

  // Alerts
  listAlerts(storeId?: string, status?: string): Observable<Alert[]> {
    const params: string[] = [];
    if (storeId) params.push(`storeId=${storeId}`);
    if (status) params.push(`status=${status}`);
    const q = params.length ? `?${params.join('&')}` : '';
    return this.http.get<Alert[]>(`${API_BASE}/api/alerts${q}`);
  }
  getAlert(id: string): Observable<Alert> { return this.http.get<Alert>(`${API_BASE}/api/alerts/${id}`); }
  reviewAlert(id: string, action: string, reasonCode?: string, notes?: string): Observable<Alert> {
    return this.http.put<Alert>(`${API_BASE}/api/alerts/${id}/review`, { action, reasonCode, notes });
  }

  // Clips
  listClips(storeId?: string, cameraId?: string): Observable<ClipListItem[]> {
    const params: string[] = [];
    if (storeId) params.push(`storeId=${storeId}`);
    if (cameraId) params.push(`cameraId=${cameraId}`);
    const q = params.length ? `?${params.join('&')}` : '';
    return this.http.get<ClipListItem[]>(`${API_BASE}/api/clips${q}`);
  }
  getClip(id: string): Observable<ClipDetail> {
    return this.http.get<ClipDetail>(`${API_BASE}/api/clips/${id}`);
  }
  deleteClip(id: string): Observable<{ ok: boolean; clipId: string }> {
    return this.http.delete<{ ok: boolean; clipId: string }>(`${API_BASE}/api/clips/${id}`);
  }

  // Connectors / health
  listConnectors(storeId?: string): Observable<Connector[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<Connector[]>(`${API_BASE}/api/connectors${q}`);
  }

  getPipelineHealth(): Observable<PipelineHealth> {
    return this.http.get<PipelineHealth>(`${API_BASE}/api/health/pipeline`);
  }

  getInstallerInfo(): Observable<InstallerInfo> {
    return this.http.get<InstallerInfo>(`${API_BASE}/api/connectors/installer`);
  }

  downloadInstaller(path: string): Observable<Blob> {
    const url = path.startsWith('/') ? `${API_BASE}${path}` : path;
    return this.http.get(url, { responseType: 'blob' });
  }

  createSetupCode(storeId: string): Observable<SetupCodeResponse> {
    return this.http.post<SetupCodeResponse>(`${API_BASE}/api/connectors/setup-codes`, { storeId });
  }

  // Rule configs
  getRuleConfigs(storeId?: string): Observable<any[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<any[]>(`${API_BASE}/api/rule-configs${q}`);
  }
  upsertRuleConfig(config: RiskConfig, storeId?: string): Observable<any> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.put<any>(`${API_BASE}/api/rule-configs${q}`, config);
  }
}
