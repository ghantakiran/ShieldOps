import { useNavigate } from "react-router-dom";
import { X } from "lucide-react";

export default function DemoBanner() {
  const navigate = useNavigate();

  function handleExit() {
    localStorage.removeItem("shieldops_demo");
    localStorage.removeItem("shieldops_token");
    localStorage.removeItem("shieldops_user");
    navigate("/");
    window.location.reload();
  }

  return (
    <div className="flex items-center justify-center gap-3 bg-brand-600 px-4 py-1.5 text-xs font-medium text-white">
      <span>You're viewing a demo with sample data</span>
      <button
        onClick={handleExit}
        className="inline-flex items-center gap-1 rounded-md bg-white/20 px-2 py-0.5 text-xs font-medium text-white transition-colors hover:bg-white/30"
      >
        <X className="h-3 w-3" />
        Exit Demo
      </button>
    </div>
  );
}
