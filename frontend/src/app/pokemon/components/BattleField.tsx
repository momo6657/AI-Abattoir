'use client';

import PokemonCard from './PokemonCard';

interface BattleFieldProps {
  state: any;
}

export default function BattleField({ state }: BattleFieldProps) {
  if (!state) {
    return (
      <div className="bg-white rounded-lg shadow-xl p-8 text-center">
        <p className="text-gray-500">Waiting for battle to start...</p>
      </div>
    );
  }

  const { player1, player2, turn, weather, trick_room } = state;

  return (
    <div className="bg-gradient-to-br from-green-100 to-blue-100 rounded-lg shadow-xl p-8">
      <div className="flex justify-between items-center mb-6">
        <div className="text-lg font-bold text-gray-800">
          Turn {turn}
        </div>
        <div className="flex gap-4">
          {weather && weather !== 'none' && (
            <div className="px-3 py-1 bg-blue-200 rounded-full text-sm font-semibold">
              Weather: {weather}
            </div>
          )}
          {trick_room && (
            <div className="px-3 py-1 bg-purple-200 rounded-full text-sm font-semibold">
              Trick Room Active
            </div>
          )}
        </div>
      </div>

      <div className="space-y-8">
        {/* Player 2 (Opponent) */}
        <div>
          <h3 className="text-xl font-bold mb-4 text-gray-800">Opponent</h3>
          <div className="grid grid-cols-2 gap-4">
            {player2?.active?.map((pokemon: any, index: number) => (
              <PokemonCard key={index} pokemon={pokemon} isOpponent={true} />
            ))}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            Bench: {player2?.bench?.length || 0} Pokemon
          </div>
        </div>

        {/* Divider */}
        <div className="border-t-2 border-gray-300"></div>

        {/* Player 1 (You) */}
        <div>
          <h3 className="text-xl font-bold mb-4 text-gray-800">Your Team</h3>
          <div className="grid grid-cols-2 gap-4">
            {player1?.active?.map((pokemon: any, index: number) => (
              <PokemonCard key={index} pokemon={pokemon} isOpponent={false} />
            ))}
          </div>
          <div className="mt-2 text-sm text-gray-600">
            Bench: {player1?.bench?.length || 0} Pokemon
          </div>
        </div>
      </div>

      {state.winner && (
        <div className="mt-6 p-4 bg-yellow-100 border-2 border-yellow-400 rounded-lg text-center">
          <h2 className="text-2xl font-bold text-gray-800">
            Battle Ended!
          </h2>
          <p className="text-lg text-gray-700 mt-2">
            Winner: Player {state.winner}
          </p>
        </div>
      )}
    </div>
  );
}
