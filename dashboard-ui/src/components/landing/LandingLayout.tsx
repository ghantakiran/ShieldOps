import { Outlet } from "react-router-dom";
import LandingNav from "./LandingNav";
import Footer from "./Footer";

export default function LandingLayout() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <LandingNav />
      <Outlet />
      <Footer />
    </div>
  );
}
