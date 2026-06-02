'use client';

import PokemonCard from './PokemonCard';

interface BattleFieldProps {
  state: any;
}

function FieldSide({ title, subtitle, pokemon, side }: { title: string; subtitle: string; pokemon: any[]; side: 'ally' | 'opponent' }) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold uppercase text-gray-300">{title}</h3>
          <p className="text-xs text-gray-500">{subtitle}</p>
        </div>
        <span className="rounded-md border border-border bg-black/20 px-2 py-1 text-xs text-gray-400">
          {pokemon?.filter((item) => !item?.is_fainted).length || 0} active
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {(pokemon || []).map((member, index) => (
          <PokemonCard key={`${member?.species || 'pokemon'}-${index}`} pokemon={member} side={side} />
        ))}
      </div>
      {(!pokemon || pokemon.length === 0) && (
        <div className="rounded-lg border border-dashed border-border bg-surface/60 p-6 text-center text-sm text-gray-500">
          等待出场宝可梦
        </div>
      )}
    </section>
  );
}

export default function BattleField({ state }: BattleFieldProps) {
  if (!state) {
    return (
      <div className="card p-8 text-center">
        <div className="mx-auto mb-3 h-2 w-28 rounded-full bg-surface-overlay" />
        <p className="text-sm text-gray-400">创建训练对战后会在这里显示实时场面。</p>
      </div>
    );
  }

  const player1Active = state.player1?.active || [];
  const player2Active = state.player2?.active || [];
  const player1Bench = state.player1?.bench || [];
  const player2Bench = state.player2?.bench || [];

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-[linear-gradient(160deg,rgba(34,197,94,0.14),rgba(14,165,233,0.08)_48%,rgba(15,23,42,0.72))] shadow-lg shadow-black/25">
      <div className="border-b border-white/10 bg-black/20 px-5 py-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase text-gray-400">Local VGC Simulation</p>
            <h2 className="text-xl font-semibold text-white">Turn {state.turn ?? 0}</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-md border border-border bg-surface/80 px-3 py-1 text-xs text-gray-300">
              Weather: {state.weather || 'none'}
            </span>
            <span className="rounded-md border border-border bg-surface/80 px-3 py-1 text-xs text-gray-300">
              Trick Room: {state.trick_room ? 'on' : 'off'}
            </span>
            <span className="rounded-md border border-border bg-surface/80 px-3 py-1 text-xs text-gray-300">
              Phase: {state.phase || 'battle'}
            </span>
          </div>
        </div>
      </div>

      <div className="space-y-6 p-5">
        <FieldSide
          title="对手场地"
          subtitle={`后备 ${player2Bench.length} 只`}
          pokemon={player2Active}
          side="opponent"
        />

        <div className="relative h-10">
          <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-white/15" />
          <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/15 bg-surface px-4 py-1 text-xs font-medium text-gray-400">
            battle line
          </div>
        </div>

        <FieldSide
          title="我方场地"
          subtitle={`后备 ${player1Bench.length} 只`}
          pokemon={player1Active}
          side="ally"
        />
      </div>

      {state.winner && (
        <div className="border-t border-amber-300/25 bg-amber-400/10 px-5 py-4 text-center">
          <h2 className="text-lg font-semibold text-amber-100">对战结束</h2>
          <p className="text-sm text-amber-200/80">胜者：Player {state.winner}</p>
        </div>
      )}
    </div>
  );
}
