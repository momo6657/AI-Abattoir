'use client';

interface PokemonCardProps {
  pokemon: any;
  side?: 'ally' | 'opponent';
  compact?: boolean;
}

const TYPE_COLORS: Record<string, string> = {
  Fire: 'bg-red-500/15 text-red-200 border-red-400/25',
  Water: 'bg-sky-500/15 text-sky-200 border-sky-400/25',
  Grass: 'bg-emerald-500/15 text-emerald-200 border-emerald-400/25',
  Electric: 'bg-yellow-400/15 text-yellow-100 border-yellow-300/25',
  Ice: 'bg-cyan-300/15 text-cyan-100 border-cyan-200/25',
  Fighting: 'bg-orange-500/15 text-orange-100 border-orange-400/25',
  Poison: 'bg-fuchsia-500/15 text-fuchsia-100 border-fuchsia-400/25',
  Ground: 'bg-stone-500/20 text-stone-100 border-stone-300/25',
  Flying: 'bg-indigo-400/15 text-indigo-100 border-indigo-300/25',
  Psychic: 'bg-pink-500/15 text-pink-100 border-pink-400/25',
  Bug: 'bg-lime-500/15 text-lime-100 border-lime-400/25',
  Rock: 'bg-amber-700/20 text-amber-100 border-amber-500/25',
  Ghost: 'bg-violet-500/15 text-violet-100 border-violet-400/25',
  Dragon: 'bg-blue-500/15 text-blue-100 border-blue-400/25',
  Dark: 'bg-slate-500/25 text-slate-100 border-slate-400/25',
  Steel: 'bg-zinc-400/15 text-zinc-100 border-zinc-300/25',
  Fairy: 'bg-rose-400/15 text-rose-100 border-rose-300/25',
};

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export default function PokemonCard({ pokemon, side = 'ally', compact = false }: PokemonCardProps) {
  if (!pokemon) return null;

  const hpPercent = clampPercent(
    pokemon.hp_percent !== undefined
      ? Number(pokemon.hp_percent) * 100
      : Number(pokemon.current_hp || 0) / Math.max(1, Number(pokemon.max_hp || 1)) * 100
  );
  const hpColor = hpPercent > 50 ? 'bg-emerald-400' : hpPercent > 25 ? 'bg-amber-300' : 'bg-red-400';
  const borderTone = side === 'opponent' ? 'border-red-400/25' : 'border-sky-400/25';

  return (
    <article
      className={`rounded-lg border ${borderTone} bg-surface/90 p-4 shadow-sm shadow-black/30 ${
        pokemon.is_fainted ? 'opacity-55 grayscale' : ''
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="truncate text-base font-semibold text-white">
            {pokemon.name || pokemon.species}
          </h4>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(pokemon.types || ['Normal']).map((type: string) => (
              <span
                key={type}
                className={`rounded-md border px-2 py-0.5 text-xs font-medium ${
                  TYPE_COLORS[type] || 'border-border bg-surface-overlay text-gray-200'
                }`}
              >
                {type}
              </span>
            ))}
          </div>
        </div>
        <div className="shrink-0 text-right text-xs text-gray-400">
          <div>Lv. {pokemon.level || 50}</div>
          {pokemon.item && <div className="mt-1 max-w-28 truncate text-gray-300">{pokemon.item}</div>}
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="font-medium text-gray-300">HP</span>
          <span className="tabular-nums text-gray-400">
            {pokemon.current_hp ?? 0}/{pokemon.max_hp ?? 0}
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-black/35">
          <div
            className={`h-full rounded-full ${hpColor} transition-all duration-300`}
            style={{ width: `${hpPercent}%` }}
          />
        </div>
      </div>

      {!compact && (
        <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
          <span className="truncate">特性：{pokemon.ability || 'Unknown'}</span>
          {pokemon.status && (
            <span className="rounded bg-red-500/15 px-2 py-0.5 font-medium text-red-200">
              {pokemon.status}
            </span>
          )}
        </div>
      )}

      {pokemon.is_fainted && (
        <div className="mt-3 rounded-md border border-red-400/25 bg-red-500/10 px-2 py-1 text-center text-xs font-semibold text-red-200">
          已失去战斗能力
        </div>
      )}
    </article>
  );
}
