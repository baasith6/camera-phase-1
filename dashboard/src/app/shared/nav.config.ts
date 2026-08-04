export interface NavItem {
  label: string;
  route: string;
  icon: string;
  adminOnly?: boolean;
  badgeKey?: 'pending';
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

const MANAGER_SECTIONS: NavSection[] = [
  {
    label: 'Daily work',
    items: [
      { label: 'Review', route: '/app/alerts', icon: 'bell', badgeKey: 'pending' },
      { label: 'Clips', route: '/app/clips', icon: 'film' },
      { label: 'Overview', route: '/app/analytics', icon: 'chart' },
    ],
  },
  {
    label: 'Account',
    items: [
      { label: 'Settings', route: '/app/settings', icon: 'settings' },
      { label: 'Help', route: '/app/get-started', icon: 'clock' },
    ],
  },
];

const ADMIN_EXTRA_SECTIONS: NavSection[] = [
  {
    label: 'Configuration',
    items: [
      { label: 'Setup & Zones', route: '/app/setup', icon: 'camera' },
      { label: 'Admin', route: '/app/admin', icon: 'home', adminOnly: true },
    ],
  },
  {
    label: 'Advanced',
    items: [
      { label: 'Training', route: '/app/training', icon: 'flask', adminOnly: true },
      { label: 'Reports', route: '/app/reports', icon: 'file' },
      { label: 'Health', route: '/app/health', icon: 'pulse' },
      { label: 'Logs', route: '/app/logs', icon: 'list' },
      { label: 'Tuning', route: '/app/tuning', icon: 'sliders' },
    ],
  },
];

export function navSectionsForRole(isAdmin: boolean): NavSection[] {
  if (!isAdmin) return MANAGER_SECTIONS;
  return [
    MANAGER_SECTIONS[0],
    ...ADMIN_EXTRA_SECTIONS,
    MANAGER_SECTIONS[1],
  ];
}

/** @deprecated use navSectionsForRole */
export const NAV_SECTIONS = navSectionsForRole(true);
