/** Auto-login for demo mode. */
import { DEMO_USER, DEMO_TOKEN } from "./config";
import { useAuthStore } from "../store/auth";

export function loginAsDemo(): void {
  localStorage.setItem("shieldops_demo", "true");
  localStorage.setItem("shieldops_token", DEMO_TOKEN);
  localStorage.setItem("shieldops_user", JSON.stringify(DEMO_USER));
  useAuthStore.getState().setAuth(DEMO_TOKEN, DEMO_USER);
}
