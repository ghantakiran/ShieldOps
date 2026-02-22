import { type ReactNode } from "react";
import { usePermissions, type Resource, type Action } from "../hooks/usePermissions";
import { Lock } from "lucide-react";

interface PermissionGateProps {
  resource: Resource;
  action: Action;
  children: ReactNode;
  fallback?: ReactNode;
  showLock?: boolean;
}

/**
 * Conditionally renders children based on user permissions.
 * Shows fallback or nothing if user lacks the required permission.
 */
export function PermissionGate({
  resource,
  action,
  children,
  fallback,
  showLock = false,
}: PermissionGateProps) {
  const { can } = usePermissions();

  if (can(resource, action)) {
    return <>{children}</>;
  }

  if (fallback) {
    return <>{fallback}</>;
  }

  if (showLock) {
    return (
      <div
        className="inline-flex items-center gap-1 text-gray-500 text-sm"
        title="Insufficient permissions"
      >
        <Lock className="w-3.5 h-3.5" />
        <span>Restricted</span>
      </div>
    );
  }

  return null;
}

interface ConditionalActionProps {
  resource: Resource;
  action: Action;
  children: ReactNode;
  disabledTitle?: string;
}

/**
 * Renders children but disables interactive elements if user lacks permission.
 * Wraps the children in a div with pointer-events-none and reduced opacity.
 */
export function ConditionalAction({
  resource,
  action,
  children,
  disabledTitle = "You do not have permission to perform this action",
}: ConditionalActionProps) {
  const { can } = usePermissions();
  const allowed = can(resource, action);

  if (allowed) {
    return <>{children}</>;
  }

  return (
    <div
      className="opacity-40 pointer-events-none cursor-not-allowed"
      title={disabledTitle}
    >
      {children}
    </div>
  );
}
