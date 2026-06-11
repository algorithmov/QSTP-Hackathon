'use client';
import { useState } from 'react';
import { uploadMedia } from '../lib/api';

const GOALS = [
  { value: 'applications', label: 'Applications' },
  { value: 'viewers', label: 'Viewers' },
  { value: 'sponsors', label: 'Sponsors' },
  { value: 'buzz', label: 'Buzz' },
] as const;

interface Props {
  onSubmit: (data: {
    content_text: string;
    goal: string;
    media_url?: string;
    topic_hint?: string;
  }) => void;
  loading: boolean;
}

export default function InputPanel({ onSubmit, loading }: Props) {
  const [contentText, setContentText] = useState('');
  const [goal, setGoal] = useState('');
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaUrl, setMediaUrl] = useState<string | undefined>();
  const [uploading, setUploading] = useState(false);

  const canSubmit = contentText.trim().length > 0 && goal !== '' && !loading && !uploading;

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setMediaFile(file);
    setUploading(true);
    try {
      const url = await uploadMedia(file);
      setMediaUrl(url);
    } catch {
      setMediaUrl(`uploads/${file.name}`);
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = () => {
    if (!canSubmit) return;
    onSubmit({ content_text: contentText, goal, media_url: mediaUrl });
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
      <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
      <textarea
        className="w-full h-24 px-3 py-2 border border-gray-300 rounded text-sm text-gray-900 resize-none focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50"
        placeholder="Describe your content or paste a caption..."
        value={contentText}
        onChange={e => setContentText(e.target.value)}
        disabled={loading}
      />

      <div className="mt-3">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Media file <span className="text-gray-400 font-normal">(optional)</span>
        </label>
        <div className="flex items-center gap-3">
          <input
            type="file"
            accept="video/*,image/*"
            onChange={handleFileChange}
            disabled={loading || uploading}
            className="text-sm text-gray-500 file:mr-3 file:py-1 file:px-3 file:rounded file:border file:border-gray-300 file:text-sm file:bg-white file:text-gray-700 hover:file:border-gray-400"
          />
          {uploading && <span className="text-xs text-gray-400">uploading...</span>}
          {!uploading && mediaFile && (
            <span className="text-xs text-green-600">{mediaFile.name}</span>
          )}
        </div>
      </div>

      <div className="mt-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">Goal</label>
        <div className="flex flex-wrap gap-2">
          {GOALS.map(g => (
            <button
              key={g.value}
              type="button"
              onClick={() => setGoal(g.value)}
              disabled={loading}
              className={`px-4 py-1.5 text-sm font-medium rounded border transition-colors ${
                goal === g.value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:border-blue-400 hover:text-blue-600'
              } disabled:opacity-50`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={!canSubmit}
        className="mt-5 px-6 py-2 bg-blue-600 text-white text-sm font-medium rounded hover:bg-blue-700 active:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? (
          <span className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
            Routing...
          </span>
        ) : (
          'Route it'
        )}
      </button>
    </div>
  );
}
