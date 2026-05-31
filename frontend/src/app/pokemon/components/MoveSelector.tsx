'use client';

interface MoveSelectorProps {
  activePokemon: any[];
  bench: any[];
  onSelectMove: (pokemonIndex: number, moveIndex: number) => void;
  onSelectSwitch: (fromIndex: number, toIndex: number) => void;
}

export default function MoveSelector({ activePokemon, bench, onSelectMove, onSelectSwitch }: MoveSelectorProps) {
  return (
    <div className="bg-white rounded-lg shadow-xl p-6">
      <h3 className="text-xl font-bold mb-4">Select Actions</h3>
      <div className="space-y-6">
        {activePokemon?.map((pokemon, idx) => (
          <div key={idx} className="border-b pb-4">
            <h4 className="font-bold text-lg mb-2">
              {pokemon?.name || pokemon?.species} (Position {idx})
            </h4>
            {pokemon?.moves ? (
              <div className="space-y-2">
                <div className="text-sm font-semibold text-gray-600">Moves:</div>
                <div className="grid grid-cols-2 gap-2">
                  {pokemon.moves.map((move: any, moveIdx: number) => (
                    <button
                      key={moveIdx}
                      onClick={() => onSelectMove(idx, moveIdx)}
                      className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
                    >
                      {move.name} ({move.type})
                    </button>
                  ))}
                </div>
                <div className="text-sm font-semibold text-gray-600 mt-3">Switch to:</div>
                <div className="grid grid-cols-3 gap-2">
                  {bench?.map((benchPokemon, benchIdx) => (
                    <button
                      key={benchIdx}
                      onClick={() => onSelectSwitch(idx, benchIdx)}
                      className="px-3 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition text-sm"
                    >
                      {benchPokemon?.name || benchPokemon?.species}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-gray-500">No moves available</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
