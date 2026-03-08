/**
 * Maps string icon identifiers to Lucide icon components.
 * Used by pages that consume centralized demo data (which stores
 * icon names as strings rather than component references).
 */
import {
  Search,
  Wrench,
  ShieldAlert,
  Users,
  Bug,
  Workflow,
  Terminal,
  Siren,
  Scan,
  Lock,
  DollarSign,
  AlertTriangle,
  FileCode,
  Server,
  Globe,
  Brain,
  GitPullRequest,
  RotateCcw,
  Shield,
  Activity,
  type LucideIcon,
} from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  search: Search,
  wrench: Wrench,
  "shield-alert": ShieldAlert,
  users: Users,
  bug: Bug,
  workflow: Workflow,
  terminal: Terminal,
  siren: Siren,
  scan: Scan,
  lock: Lock,
  "dollar-sign": DollarSign,
  "alert-triangle": AlertTriangle,
  "file-code": FileCode,
  server: Server,
  globe: Globe,
  brain: Brain,
  "git-pull-request": GitPullRequest,
  "rotate-ccw": RotateCcw,
  shield: Shield,
  activity: Activity,
};

/** Resolve a string icon name to a Lucide icon component. Falls back to Activity. */
export function resolveIcon(name: string): LucideIcon {
  return ICON_MAP[name] ?? Activity;
}
