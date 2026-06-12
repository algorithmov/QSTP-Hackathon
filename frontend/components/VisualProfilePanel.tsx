import type { VisualProfile } from "@/types/route";

type VisualProfilePanelProps = {
  summary: string;
  profile: VisualProfile | null;
};

export function VisualProfilePanel({ summary, profile }: VisualProfilePanelProps) {
  return (
    <section className="rounded-md border border-line bg-white p-5 shadow-board">
      <h2 className="text-xl font-bold text-ink">Content signal</h2>
      <p className="mt-2 text-sm leading-6 text-muted">{summary}</p>
      {profile ? (
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Metric label="Type" value={profile.content_type} />
          <Metric label="Format" value={profile.format} />
          <Metric label="Aspect" value={profile.aspect_ratio} />
          <Metric label="Confidence" value={`${Math.round(profile.confidence * 100)}%`} />
          <Metric label="Motion" value={`${Math.round(profile.motion_level * 100)}%`} />
          <Metric label="Energy" value={`${Math.round(profile.energy_score * 100)}%`} />
          <Metric label="Faces" value={String(profile.face_count)} />
          <Metric label="Text language" value={profile.detected_text_language ?? "none"} />
        </dl>
      ) : (
        <p className="mt-4 text-sm text-muted">No visual profile returned.</p>
      )}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-paper px-3 py-2">
      <dt className="text-xs font-semibold text-muted">{label}</dt>
      <dd className="mt-1 truncate font-bold text-ink">{value}</dd>
    </div>
  );
}
