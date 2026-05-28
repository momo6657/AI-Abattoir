'use client';

import { useMemo } from 'react';

const PIECE_UNICODE: Record<string, Record<string, string>> = {
  white: { king: '♔', queen: '♕', rook: '♖', bishop: '♗', knight: '♘', pawn: '♙' },
  black: { king: '♚', queen: '♛', rook: '♜', bishop: '♝', knight: '♞', pawn: '♟' },
};

const FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

interface ChessBoardProps {
  board?: Record<string, [string, string]>;
  lastMove?: { from: string; to: string } | null;
  inCheck?: string | null;
  flipped?: boolean;
}

export default function ChessBoard({ board = {}, lastMove, inCheck, flipped = false }: ChessBoardProps) {
  const squares = useMemo(() => {
    const result = [];
    const ranks = flipped ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1];
    const files = flipped ? [...FILES].reverse() : FILES;

    for (const rank of ranks) {
      for (const file of files) {
        const square = `${file}${rank}`;
        const piece = board[square];
        const fileIdx = FILES.indexOf(file);
        const isLight = (fileIdx + rank) % 2 === 0;
        const isLastMove = lastMove && (square === lastMove.from || square === lastMove.to);
        const isKingInCheck = piece && piece[1] === 'king' && piece[0] === inCheck;

        result.push({ square, piece, isLight, isLastMove, isKingInCheck });
      }
    }
    return result;
  }, [board, lastMove, inCheck, flipped]);

  // 被吃棋子
  const captured = useMemo(() => {
    const initial: Record<string, number> = {
      'white-pawn': 8, 'white-rook': 2, 'white-knight': 2, 'white-bishop': 2, 'white-queen': 1, 'white-king': 1,
      'black-pawn': 8, 'black-rook': 2, 'black-knight': 2, 'black-bishop': 2, 'black-queen': 1, 'black-king': 1,
    };
    const current: Record<string, number> = {};
    for (const [, piece] of Object.entries(board)) {
      const key = `${piece[0]}-${piece[1]}`;
      current[key] = (current[key] || 0) + 1;
    }
    const whiteCaptured: string[] = [];
    const blackCaptured: string[] = [];
    for (const [key, count] of Object.entries(initial)) {
      const diff = count - (current[key] || 0);
      const [color, piece] = key.split('-');
      const symbol = PIECE_UNICODE[color]?.[piece] || '?';
      for (let i = 0; i < diff; i++) {
        if (color === 'white') whiteCaptured.push(symbol);
        else blackCaptured.push(symbol);
      }
    }
    return { white: whiteCaptured, black: blackCaptured };
  }, [board]);

  return (
    <div className="space-y-2">
      {/* 黑方被吃棋子 */}
      {captured.black.length > 0 && (
        <div className="flex gap-1 text-lg">
          {captured.black.map((s, i) => <span key={i} className="text-gray-600">{s}</span>)}
        </div>
      )}

      {/* 棋盘 */}
      <div className="inline-block border-2 border-gray-600 rounded overflow-hidden">
        <div className="grid grid-cols-8 gap-0" style={{ width: '320px', height: '320px' }}>
          {squares.map(({ square, piece, isLight, isLastMove, isKingInCheck }) => (
            <div
              key={square}
              className={`flex items-center justify-center text-2xl select-none cursor-default ${
                isKingInCheck ? 'bg-red-500' :
                isLastMove ? 'bg-yellow-600/70' :
                isLight ? 'bg-gray-200' : 'bg-gray-500'
              }`}
              style={{ width: '40px', height: '40px' }}
              title={square}
            >
              {piece && (
                <span className={piece[0] === 'white' ? 'text-white drop-shadow-lg' : 'text-gray-900'}>
                  {PIECE_UNICODE[piece[0]]?.[piece[1]] || '?'}
                </span>
              )}
            </div>
          ))}
        </div>
        <div className="flex justify-between px-1 mt-0.5" style={{ width: '320px' }}>
          {(flipped ? [...FILES].reverse() : FILES).map(f => (
            <span key={f} className="text-xs text-gray-400 w-10 text-center">{f}</span>
          ))}
        </div>
      </div>

      {/* 白方被吃棋子 */}
      {captured.white.length > 0 && (
        <div className="flex gap-1 text-lg">
          {captured.white.map((s, i) => <span key={i} className="text-gray-300">{s}</span>)}
        </div>
      )}
    </div>
  );
}