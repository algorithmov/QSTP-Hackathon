'use client';
import { useState } from 'react';
import dynamic from 'next/dynamic';
import { routeContent } from '../lib/api';
import { RouteResponse } from '../lib/types';
import InputPanel from '../components/InputPanel';
import RouteBoard from '../components/RouteBoard';
import TrendTicker from '../components/TrendTicker';

const MenaMap = dynamic(() => import('../components/MenaMap'), { ssr: false });

type AppState = 'idle' | 'loading' | 'success' | 'error';

export default function Home() {
  const [state, setState] = useState<AppState>('idle');
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleSubmit = async (data: {
    content_text: string;
    goal: string;
    media_url?: string;
    topic_hint?: string;
  }) => {
    setState('loading');
    setErrorMsg('');
    try {
      const res = await routeContent(data);
      setResult(res);
      setState('success');
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Routing failed. Check that the backend is running.';
      setErrorMsg(msg);
      setState('error');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-5xl mx-auto flex items-baseline gap-3">
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Masar</h1>
          <span className="text-sm text-gray-400">Google Maps for your content</span>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-8">
        <InputPanel onSubmit={handleSubmit} loading={state === 'loading'} />

        {state === 'error' && (
          <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {errorMsg}
          </div>
        )}

        {state === 'success' && result && (
          <>
            <section>
              <div className="flex items-baseline gap-3 mb-3">
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
                  Route Board
                </h2>
                <p className="text-sm text-gray-500">{result.content_summary}</p>
              </div>
              <RouteBoard routes={result.routes} />
            </section>

            {result.trend_ticker.length > 0 && (
              <section>
                <TrendTicker items={result.trend_ticker} />
              </section>
            )}

            {result.map_data.length > 0 && (
              <section>
                <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
                  Interest Map
                </h2>
                <MenaMap mapData={result.map_data} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
