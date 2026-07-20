export interface LoginResponse { token: string; email: string; role: string; }

export interface Store {
  id: string;
  name: string;
  organization: string;
  alertVisibilityMode: string;
}

export interface Camera {
  id: string;
  storeId: string;
  name: string;
  rtspUrl: string;
  status: string;
  lastSeen?: string;
  // ONVIF metadata (populated after connector query)
  onvifHost?: string;
  onvifPort?: number;
  cameraManufacturer?: string;
  cameraModel?: string;
  cameraSerial?: string;
  cameraFirmware?: string;
}

export interface Zone {
  id: string;
  cameraId: string;
  name: string;
  zoneType: string;
  polygonJson: string;
}

export interface Alert {
  id: string;
  storeId: string;
  cameraId: string;
  zoneId?: string;
  clipId: string;
  alertType: string;
  riskLevel: string;
  riskScore: number;
  evidenceJson: string;
  status: string;
  clipUrl?: string;
  modelVersion: string;
  ruleVersion: string;
  createdAt: string;
  reviews?: AlertReview[];
}

export interface AlertReview {
  id: string;
  alertId: string;
  action: string;
  reasonCode?: string;
  notes?: string;
  createdAt: string;
}

export interface Connector {
  id: string;
  storeId: string;
  name: string;
  version: string;
  status: string;
  lastHeartbeat?: string;
  diskFreePct: number;
  uploadQueueDepth: number;
  degradedReason?: string;
  rtspReconnects?: number;
}

export interface RiskConfig {
  weights: { [k: string]: number };
  dwellThresholdSec: number;
  dwellMaxSec: number;
  repeatedHandlingThreshold: number;
  groupSizeThreshold: number;
  lowStaffStartHour: number;
  lowStaffEndHour: number;
  lowBand: number;
  mediumBand: number;
  highBand: number;
}
