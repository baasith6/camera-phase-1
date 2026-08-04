export interface LoginResponse { token: string; email: string; role: string; storeId?: string | null; }

export interface Store {
  id: string;
  name: string;
  organization: string;
  alertVisibilityMode: string;
  notificationEmail?: string | null;
}

export interface StoreOverview {
  id: string;
  name: string;
  alertVisibilityMode: string;
  notificationEmail?: string | null;
  cameraCount: number;
  connectorCount: number;
  onlineConnectorCount: number;
  pendingAlertCount: number;
  lastAlertAt?: string | null;
}

export interface UserAccount {
  id: string;
  email: string;
  role: string;
  storeId?: string | null;
  createdAt: string;
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

export interface AlertAiEvent {
  eventType: string;
  confidence: number;
  startTs: string;
  endTs: string;
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
  aiEvents?: AlertAiEvent[];
}

export interface AlertReview {
  id: string;
  alertId: string;
  action: string;
  reasonCode?: string;
  notes?: string;
  confirmedPatternsJson?: string | null;
  createdAt: string;
}

export interface TrainingPatternLabel {
  pattern: string;
  aiDetected: boolean;
  humanConfirmed: boolean;
  labelStatus: string;
}

export interface TrainingSampleItem {
  id: string;
  alertId: string;
  clipId: string;
  alertType: string;
  aiDetectedPatterns: string[];
  humanConfirmedPatterns: string[];
  positiveCount: number;
  hardNegativeCount: number;
  reviewOutcome: string;
  datasetStatus: string;
  includeInTraining: boolean;
  reviewerEmail: string;
  modelVersion: string;
  storeName: string;
  cameraName: string;
  createdAt: string;
  updatedAt: string;
}

export interface TrainingSampleDetail {
  id: string;
  alertId: string;
  clipId: string;
  alertType: string;
  labels: TrainingPatternLabel[];
  reviewOutcome: string;
  datasetStatus: string;
  includeInTraining: boolean;
  reviewerEmail: string;
  modelVersion: string;
  ruleVersion: string;
  storeName: string;
  cameraName: string;
  clipUrl?: string | null;
  editHistoryJson: string;
  createdAt: string;
  updatedAt: string;
}

export interface TrainingStats {
  total: number;
  ready: number;
  pending: number;
  excluded: number;
  clipIssues: number;
  positiveByPattern: Record<string, number>;
  hardNegativeByPattern: Record<string, number>;
  byModelVersion: Record<string, number>;
  byStore: Record<string, number>;
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
  adminHost?: string | null;
  adminPort?: number | null;
}

export interface InstallerInfo {
  version: string;
  fileName: string;
  sizeBytes: number;
  sha256: string;
  downloadPath: string;
}

export interface SetupCodeResponse {
  code: string;
  storeId: string;
  expiresAt: string;
}

export interface ClipListItem {
  id: string;
  cameraId: string;
  cameraName: string;
  storeId: string;
  storeName: string;
  status: string;
  durationSec: number;
  triggerReason: string;
  createdAt: string;
  analyzedAt?: string | null;
  eventCount: number;
  riskScore?: number | null;
  alertId?: string | null;
}

export interface ClipAiEvent {
  eventType: string;
  zoneName?: string | null;
  value: number;
  confidence: number;
  startTs: string;
  endTs: string;
  modelVersion: string;
}

export interface ClipDetail {
  id: string;
  cameraId: string;
  cameraName: string;
  storeId: string;
  storeName: string;
  status: string;
  durationSec: number;
  triggerReason: string;
  createdAt: string;
  analyzedAt?: string | null;
  clipUrl?: string | null;
  eventCount: number;
  riskScore?: number | null;
  riskDetails?: string | null;
  alertId?: string | null;
  modelVersion?: string | null;
  analysisNote?: string | null;
  aiEvents: ClipAiEvent[];
}

export interface PipelineHealth {
  redisQueueDepth: number;
  failedJobs: number;
}

export interface AnalyticsSummary {
  totalAlerts: number;
  pendingAlerts: number;
  highRiskAlerts: number;
  mediumRiskAlerts: number;
  falsePositives: number;
  totalClips: number;
  analyzedClips: number;
  alertsByType: Record<string, number>;
}

export interface ConnectorLogEntry {
  id: string;
  storeId: string;
  name: string;
  status: string;
  version: string;
  lastHeartbeat?: string | null;
  degradedReason?: string | null;
  uploadQueueDepth: number;
  diskFreePct: number;
}

export interface SystemLogs {
  connectors: ConnectorLogEntry[];
  redisQueueDepth: number;
  failedJobs: number;
  generatedAt: string;
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
