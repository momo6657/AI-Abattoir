'use client';

interface TeamManagerProps {
  label: string;
  team?: any;
  agent?: any;
  tone?: 'blue' | 'red';
}

const TONE_CLASS = {
  blue: 'border-sky-400/25 bg-sky-500/5',
  red: 'border-red-400/25 bg-red-500/5',
};

export default function TeamManager({ label, team, agent, tone = 'blue' }: TeamManagerProps) {
  const members = team?.pokemon_list || [];

  return (
    <section className={`rounded-lg border p-4 ${TONE_CLASS[tone]}`}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase text-gray-500">{label}</p>
          <h3 className="truncate text-lg font-semibold text-white">{agent?.name || '未创建智能体'}</h3>
          <p className="mt-1 truncate text-sm text-gray-400">{team?.name || '等待自动构建队伍'}</p>
        </div>
        <div className="shrink-0 rounded-md border border-border bg-black/20 px-2 py-1 text-xs text-gray-400">
          {team?.format || 'vgc2024'}
        </div>
      </div>

      {members.length > 0 ? (
        <div className="grid grid-cols-1 gap-3">
          {members.map((pokemon: any, index: number) => (
            <div key={`${pokemon.species}-${index}`} className="rounded-md border border-border bg-surface/75 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium text-gray-100">{pokemon.name || pokemon.species}</div>
                  <div className="mt-1 truncate text-xs text-gray-500">
                    {pokemon.ability || 'Ability unknown'} · {pokemon.item || 'No item'}
                  </div>
                </div>
                {pokemon.tera_type && (
                  <span className="rounded bg-surface-overlay px-2 py-1 text-xs text-gray-400">
                    Tera {pokemon.tera_type}
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(pokemon.moves || []).slice(0, 4).map((move: string) => (
                  <span key={move} className="rounded border border-border bg-black/20 px-2 py-0.5 text-xs text-gray-300">
                    {move}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-border p-5 text-center text-sm text-gray-500">
          点击“准备训练环境”后自动生成队伍。
        </div>
      )}
    </section>
  );
}
