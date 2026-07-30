export interface NavItem {
  label: string;
  route: string;
  icon: string;
  adminOnly?: boolean;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const NAV_SECTIONS: NavSection[] = [
  {
    label: 'Operations',
    items: [
      { label: 'Alerts', route: '/app/alerts', icon: 'bell' },
      { label: 'Clips', route: '/app/clips', icon: 'film' },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { label: 'Get started', route: '/app/get-started', icon: 'clock' },
      { label: 'Setup & Zones', route: '/app/setup', icon: 'camera' },
      { label: 'Tuning', route: '/app/tuning', icon: 'sliders' },
      { label: 'Admin', route: '/app/admin', icon: 'home', adminOnly: true },
    ],
  },
  {
    label: 'Insights',
    items: [
      { label: 'Overview', route: '/app/analytics', icon: 'chart' },
      { label: 'Reports', route: '/app/reports', icon: 'file' },
    ],
  },
  {
    label: 'System',
    items: [
      { label: 'Health', route: '/app/health', icon: 'pulse' },
      { label: 'Logs', route: '/app/logs', icon: 'list' },
      { label: 'Settings', route: '/app/settings', icon: 'settings' },
    ],
  },
];
