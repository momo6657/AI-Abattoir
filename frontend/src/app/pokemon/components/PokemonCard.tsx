'use client';

interface PokemonCardProps {
  pokemon: any;
  isOpponent: boolean;
}

export default function PokemonCard({ pokemon, isOpponent }: PokemonCardProps) {
  if (!pokemon) return null;

  const hpPercent = pokemon.current_hp / pokemon.max_hp * 100;
  const hpColor = hpPercent > 50 ? 'bg-green-500' : hpPercent > 25 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className={`bg-white rounded-lg shadow-md p-4 border-2 ${pokemon.is_fainted ? 'border-gray-300 opacity-50' : 'border-blue-300'}`}>
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="font-bold text-lg">{pokemon.name || pokemon.species}</h4>
          <div className="flex gap-1 mt-1">
            {pokemon.types?.map((type: string) => (
              <span key={type} className="px-2 py-0.5 bg-gray-200 rounded text-xs font-semibold">
                {type}
              </span>
            ))}
          </div>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-600">Lv. {pokemon.level}</div>
          {pokemon.status && (
            <div className="mt-1 px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs font-semibold">
              {pokemon.status}
            </div>
          )}
        </div>
      </div>

      {/* HP Bar */}
      <div className="mt-3">
        <div className="flex justify-between text-sm mb-1">
          <span className="font-semibold">HP</span>
          <span className="text-gray-600">
            {pokemon.current_hp}/{pokemon.max_hp}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-300 ${hpColor}`}
            style={{ width: `${hpPercent}%` }}
          />
        </div>
      </div>

      {pokemon.is_fainted && (
        <div className="mt-2 text-center text-red-600 font-bold">
          FAINTED
        </div>
      )}
    </div>
  );
}
