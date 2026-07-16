import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE } from './api.config';
import { Alert, Camera, Connector, RiskConfig, Store, Zone } from './models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // Stores
  listStores(): Observable<Store[]> { return this.http.get<Store[]>(`${API_BASE}/api/stores`); }
  createStore(name: string, organization?: string): Observable<Store> {
    return this.http.post<Store>(`${API_BASE}/api/stores`, { name, organization });
  }
  updateStore(id: string, body: { name?: string; alertVisibilityMode?: string }): Observable<Store> {
    return this.http.put<Store>(`${API_BASE}/api/stores/${id}`, body);
  }

  // Cameras
  listCameras(storeId?: string): Observable<Camera[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<Camera[]>(`${API_BASE}/api/cameras${q}`);
  }
  createCamera(storeId: string, name: string, rtspUrl: string): Observable<Camera> {
    return this.http.post<Camera>(`${API_BASE}/api/cameras`, { storeId, name, rtspUrl });
  }
  updateCamera(id: string, body: { name?: string; rtspUrl?: string; status?: string }): Observable<Camera> {
    return this.http.put<Camera>(`${API_BASE}/api/cameras/${id}`, body);
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

  // Connectors / health
  listConnectors(storeId?: string): Observable<Connector[]> {
    const q = storeId ? `?storeId=${storeId}` : '';
    return this.http.get<Connector[]>(`${API_BASE}/api/connectors${q}`);
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
