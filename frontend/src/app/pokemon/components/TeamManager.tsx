'use client';

import { useState } from 'react';

interface TeamManagerProps {
  label: string;
  team: any[];
  onChange: (team: any[]) => void;
}

export default function TeamManager({ label, team, onChange }: TeamManagerProps) {
  const [species, setSpecies] = useState('');
  const [level, setLevel] = useState(50);

  const addPokemon = () => {
    if (!species) return;

    const newPokemon = {
      species,
      name: species,
      level,
      ability: 'Default',
      item: 'None',
      moves: ['Tackle', 'Growl'],
      stats: { hp: 100, atk: 50, def: 50, spa: 50, spd: 50, spe: 50 },
    };

    onChange([...team, newPokemon]);
    setSpecies('');
  };

  const removePokemon = (index: number) => {
    onChange(team.filter((_, i) => i !== index));
  };

  return (
    <div className="mb-6">
      <h3 className="text-lg font-bold mb-3">{label}</h3>

      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={species}
          onChange={(e) => setSpecies(e.target.value)}
          placeholder="Species name"
          className="flex-1 px-3 py-2 border rounded"
        />
        <input
          type="number"
          value={level}
          onChange={(e) => setLevel(parseInt(e.target.value))}
          placeholder="Level"
          className="w-20 px-3 py-2 border rounded"
          min={1}
          max={100}
        />
        <button
          onClick={addPokemon}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Add
        </button>
      </div>

      <div className="space-y-2">
        {team.map((pokemon, index) => (
          <div key={index} className="flex justify-between items-center p-2 bg-gray-100 rounded">
            <span>{pokemon.name} (Lv. {pokemon.level})</span>
            <button
              onClick={() => removePokemon(index)}
              className="px-2 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {team.length === 0 && (
        <p className="text-gray-500 text-sm">No Pokemon added yet</p>
      )}
    </div>
  );
}
