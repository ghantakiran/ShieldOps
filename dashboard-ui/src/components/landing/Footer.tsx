import Logo from "../Logo";

export default function Footer() {
  return (
    <footer className="border-t border-gray-800 px-6 py-8">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <Logo size="sm" />
        <p className="text-xs text-gray-600">
          &copy; {new Date().getFullYear()} ShieldOps. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
