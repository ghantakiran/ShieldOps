import { Shield } from "lucide-react";

export default function Footer() {
  return (
    <footer className="border-t border-gray-800 px-6 py-8">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <div className="flex items-center gap-2 text-gray-500">
          <Shield className="h-5 w-5" />
          <span className="text-sm">ShieldOps</span>
        </div>
        <p className="text-xs text-gray-600">
          &copy; {new Date().getFullYear()} ShieldOps. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
