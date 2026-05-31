'use client';

import { useState, useEffect } from 'react';
import BattleField from './components/BattleField';
import TeamManager from './components/TeamManager';
import MoveSelector from './components/MoveSelector';

export default function PokemonBattlePage() {
  const [battleId, setBattleId] = useState<string | null>(null);
  const [battleState, setBattleState] = useState<any>(null);
  const [team1, setTeam1] = useState<any[]>([]);
  const [team2, setTeam2] = useState<any[]>([]);
  const [selectedPokemon, setSelectedPokemon] = useState<number | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [messages, setMessages] = useState<string[]>([]);

  useEffect(() => {
    if (battleId) {
      const websocket = new WebSocket(`ws://localhost:8000/ws/pokemon/battle/${battleId}`);

      websocket.onopen = () => {
        console.log('Connected to battle');
        addMessage('Connected to battle');
      };

      websocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      };

      websocket.onclose = () => {
        console.log('Disconnected from battle');
        addMessage('Disconnected from battle');
      };

      setWs(websocket);

      return () => {
        websocket.close();
      };
    }
  }, [battleId]);

  const handleWebSocketMessage = (data: any) => {
    switch (data.type) {
      case 'battle_state':
        setBattleState(data.state);
        break;
      case 'turn_complete':
        setBattleState(data.state);
        addMessage(`Turn ${data.turn} complete`);
        break;
      case 'battle_end':
        addMessage(`Battle ended! Winner: Player ${data.winner}`);
        break;
      case 'error':
        addMessage(`Error: ${data.message}`);
        break;
    }
  };

  const addMessage = (msg: string) => {
    setMessages(prev => [...prev, msg]);
  };

  const startBattle = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/pokemon/battles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          team1: team1,
          team2: team2,
        }),
      });
      const data = await response.json();
      setBattleId(data.battle_id);
      setBattleState(data.initial_state);
      addMessage('Battle started!');
    } catch (error) {
      addMessage(`Failed to start battle: ${error}`);
    }
  };

  const submitMove = (pokemonIndex: number, moveIndex: number) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'move',
        pokemon_index: pokemonIndex,
        move_index: moveIndex,
      }));
      addMessage(`Submitted move for Pokemon ${pokemonIndex}`);
    }
  };

  const submitSwitch = (fromIndex: number, toIndex: number) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'switch',
        from: fromIndex,
        to: toIndex,
      }));
      addMessage(`Switched Pokemon ${fromIndex} to ${toIndex}`);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-900 to-purple-900 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-8">Pokemon Battle</h1>

        {!battleId ? (
          <div className="bg-white rounded-lg shadow-xl p-6">
            <h2 className="text-2xl font-bold mb-4">Setup Battle</h2>
            <TeamManager
              label="Team 1"
              team={team1}
              onChange={setTeam1}
            />
            <TeamManager
              label="Team 2"
              team={team2}
              onChange={setTeam2}
            />
            <button
              onClick={startBattle}
              disabled={team1.length === 0 || team2.length === 0}
              className="mt-6 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              Start Battle
            </button>
          </div>
        ) : (
          <div className="space-y-6">
            <BattleField state={battleState} />

            {battleState && !battleState.winner && (
              <MoveSelector
                activePokemon={battleState.player1.active}
                onSelectMove={submitMove}
                onSelectSwitch={submitSwitch}
                bench={battleState.player1.bench}
              />
            )}

            <div className="bg-white rounded-lg shadow-xl p-6">
              <h3 className="text-xl font-bold mb-4">Battle Log</h3>
              <div className="max-h-64 overflow-y-auto space-y-2">
                {messages.map((msg, i) => (
                  <div key={i} className="text-sm text-gray-700">
                    {msg}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
