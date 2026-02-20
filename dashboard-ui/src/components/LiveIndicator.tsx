/**
 * A small pulsing green dot that indicates data is being live-updated.
 * Renders nothing when `active` is false.
 */
export default function LiveIndicator({ active = true }: { active?: boolean }) {
  if (!active) return null;

  return (
    <span className="relative flex h-2 w-2" title="Live updates active">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
    </span>
  );
}
