'use client';

interface MoveSelectorProps {
  activePokemon: any[];
  bench: any[];
  busy?: boolean;
  onAutoTurn: () => void;
}

function PlayIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 5v14l11-7-11-7z" />
    </svg>
  );
}

export default function MoveSelector({ activePokemon, bench, busy = false, onAutoTurn }: MoveSelectorProps) {
  const canMove = activePokemon?.some((pokemon) => !pokemon?.is_fainted);

  return (
    <aside className="card p-5">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">回合控制</h3>
          <p className="mt-1 text-sm text-gray-400">使用当前出场宝可梦的首个可用招式推进双方行动。</p>
        </div>
        <button
          onClick={onAutoTurn}
          disabled={busy || !canMove}
          className="btn-primary inline-flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <PlayIcon />
          推进一回合
        </button>
      </div>

      <div className="space-y-4">
        {(activePokemon || []).map((pokemon, idx) => (
          <div key={`${pokemon?.species || 'active'}-${idx}`} className="rounded-lg border border-border bg-surface/70 p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h4 className="truncate font-medium text-gray-100">{pokemon?.name || pokemon?.species}</h4>
              <span className="rounded-md bg-surface-overlay px-2 py-1 text-xs text-gray-400">
                slot {idx + 1}
              </span>
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(pokemon?.moves || []).slice(0, 4).map((move: any, moveIdx: number) => (
                <div key={`${move?.name || move}-${moveIdx}`} className="rounded-md border border-border bg-black/20 px-3 py-2">
                  <div className="truncate text-sm font-medium text-gray-100">
                    {typeof move === 'string' ? move : move?.name || 'Unknown Move'}
                  </div>
                  {typeof move !== 'string' && (
                    <div className="mt-1 flex justify-between text-xs text-gray-500">
                      <span>{move?.type || 'Normal'}</span>
                      <span>{move?.category || 'move'}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 rounded-lg border border-border bg-black/20 px-4 py-3 text-sm text-gray-400">
        后备可换入：{bench?.length ? bench.map((item) => item?.name || item?.species).join(', ') : '暂无'}
      </div>
    </aside>
  );
}
