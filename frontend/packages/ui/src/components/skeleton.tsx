/** Chargement : barres grises (pages d'état des maquettes) ; annoncé aux lecteurs d'écran. */
export function Skeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2 opacity-45">
      {["60%", "85%", "70%"].map((width) => (
        <div key={width} className="h-2 rounded-full bg-field" style={{ width }} />
      ))}
    </div>
  );
}
