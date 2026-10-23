from flask import Flask, render_template, jsonify, request, session
import secrets
import copy

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Constants
ROWS = 8
COLS = 8

# Piece classes
class Piece:
    def __init__(self, name, color, value):
        self.name = name
        self.color = color
        self.value = value * (1 if color == 'white' else -1)
        self.moves = []
        self.moved = False

    def add_move(self, move):
        self.moves.append(move)

    def clear_moves(self):
        self.moves = []

    def to_dict(self):
        return {
            'name': self.name,
            'color': self.color,
            'moved': self.moved
        }

class Pawn(Piece):
    def __init__(self, color):
        super().__init__('pawn', color, 1.0)
        self.dir = -1 if color == 'white' else 1
        self.en_passant = False

class Knight(Piece):
    def __init__(self, color):
        super().__init__('knight', color, 3.0)

class Bishop(Piece):
    def __init__(self, color):
        super().__init__('bishop', color, 3.001)

class Rook(Piece):
    def __init__(self, color):
        super().__init__('rook', color, 5.0)

class Queen(Piece):
    def __init__(self, color):
        super().__init__('queen', color, 9.0)

class King(Piece):
    def __init__(self, color):
        super().__init__('king', color, 10000.0)
        self.left_rook = None
        self.right_rook = None

# Square class
class Square:
    def __init__(self, row, col, piece=None):
        self.row = row
        self.col = col
        self.piece = piece

    def has_piece(self):
        return self.piece is not None

    def isempty(self):
        return not self.has_piece()

    def has_team_piece(self, color):
        return self.has_piece() and self.piece.color == color

    def has_enemy_piece(self, color):
        return self.has_piece() and self.piece.color != color

    def isempty_or_enemy(self, color):
        return self.isempty() or self.has_enemy_piece(color)

    @staticmethod
    def in_range(*args):
        for arg in args:
            if arg < 0 or arg > 7:
                return False
        return True

# Move class
class Move:
    def __init__(self, initial, final):
        self.initial = initial
        self.final = final

    def __eq__(self, other):
        return self.initial.row == other.initial.row and \
               self.initial.col == other.initial.col and \
               self.final.row == other.final.row and \
               self.final.col == other.final.col

# Board class
class Board:
    def __init__(self):
        self.squares = [[Square(row, col) for col in range(COLS)] for row in range(ROWS)]
        self.last_move = None
        self._add_pieces('white')
        self._add_pieces('black')

    def move(self, piece, move, testing=False):
        initial = move.initial
        final = move.final

        en_passant_empty = self.squares[final.row][final.col].isempty()

        # Update board
        self.squares[initial.row][initial.col].piece = None
        self.squares[final.row][final.col].piece = piece

        # Handle pawn special moves
        if isinstance(piece, Pawn):
            diff = final.col - initial.col
            if diff != 0 and en_passant_empty:
                self.squares[initial.row][initial.col + diff].piece = None
                self.squares[final.row][final.col].piece = piece
            else:
                self.check_promotion(piece, final)

        # Handle castling
        if isinstance(piece, King):
            if self.castling(initial, final) and not testing:
                diff = final.col - initial.col
                rook = piece.left_rook if (diff < 0) else piece.right_rook
                self.move(rook, rook.moves[-1])

        piece.moved = True
        piece.clear_moves()
        self.last_move = move

    def valid_move(self, piece, move):
        return move in piece.moves

    def check_promotion(self, piece, final):
        if final.row == 0 or final.row == 7:
            self.squares[final.row][final.col].piece = Queen(piece.color)

    def castling(self, initial, final):
        return abs(initial.col - final.col) == 2

    def set_true_en_passant(self, piece):
        if not isinstance(piece, Pawn):
            return

        for row in range(ROWS):
            for col in range(COLS):
                if isinstance(self.squares[row][col].piece, Pawn):
                    self.squares[row][col].piece.en_passant = False
        
        piece.en_passant = True

    def in_check(self, piece, move):
        temp_piece = copy.deepcopy(piece)
        temp_board = copy.deepcopy(self)
        temp_board.move(temp_piece, move, testing=True)
        
        for row in range(ROWS):
            for col in range(COLS):
                if temp_board.squares[row][col].has_enemy_piece(piece.color):
                    p = temp_board.squares[row][col].piece
                    temp_board.calc_moves(p, row, col, bool=False)
                    for m in p.moves:
                        if isinstance(m.final.piece, King):
                            return True
        
        return False

    def calc_moves(self, piece, row, col, bool=True):
        """Calculate all possible valid moves for a piece"""
        
        def pawn_moves():
            steps = 1 if piece.moved else 2
            start = row + piece.dir
            end = row + (piece.dir * (1 + steps))
            
            # Forward moves
            for move_row in range(start, end, piece.dir):
                if Square.in_range(move_row):
                    if self.squares[move_row][col].isempty():
                        initial = Square(row, col)
                        final = Square(move_row, col)
                        move = Move(initial, final)
                        if bool:
                            if not self.in_check(piece, move):
                                piece.add_move(move)
                        else:
                            piece.add_move(move)
                    else:
                        break
                else:
                    break

            # Diagonal captures
            move_row = row + piece.dir
            for move_col in [col-1, col+1]:
                if Square.in_range(move_row, move_col):
                    if self.squares[move_row][move_col].has_enemy_piece(piece.color):
                        initial = Square(row, col)
                        final_piece = self.squares[move_row][move_col].piece
                        final = Square(move_row, move_col, final_piece)
                        move = Move(initial, final)
                        if bool:
                            if not self.in_check(piece, move):
                                piece.add_move(move)
                        else:
                            piece.add_move(move)

            # En passant
            r = 3 if piece.color == 'white' else 4
            fr = 2 if piece.color == 'white' else 5
            for side in [-1, 1]:
                if Square.in_range(col+side) and row == r:
                    if self.squares[row][col+side].has_enemy_piece(piece.color):
                        p = self.squares[row][col+side].piece
                        if isinstance(p, Pawn) and p.en_passant:
                            initial = Square(row, col)
                            final = Square(fr, col+side, p)
                            move = Move(initial, final)
                            if bool:
                                if not self.in_check(piece, move):
                                    piece.add_move(move)
                            else:
                                piece.add_move(move)

        def knight_moves():
            possible_moves = [
                (row-2, col+1), (row-1, col+2), (row+1, col+2), (row+2, col+1),
                (row+2, col-1), (row+1, col-2), (row-1, col-2), (row-2, col-1),
            ]

            for move_row, move_col in possible_moves:
                if Square.in_range(move_row, move_col):
                    if self.squares[move_row][move_col].isempty_or_enemy(piece.color):
                        initial = Square(row, col)
                        final_piece = self.squares[move_row][move_col].piece
                        final = Square(move_row, move_col, final_piece)
                        move = Move(initial, final)
                        if bool:
                            if not self.in_check(piece, move):
                                piece.add_move(move)
                        else:
                            piece.add_move(move)

        def straightline_moves(incrs):
            for row_incr, col_incr in incrs:
                move_row = row + row_incr
                move_col = col + col_incr

                while True:
                    if Square.in_range(move_row, move_col):
                        initial = Square(row, col)
                        final_piece = self.squares[move_row][move_col].piece
                        final = Square(move_row, move_col, final_piece)
                        move = Move(initial, final)

                        if self.squares[move_row][move_col].isempty():
                            if bool:
                                if not self.in_check(piece, move):
                                    piece.add_move(move)
                            else:
                                piece.add_move(move)
                        elif self.squares[move_row][move_col].has_enemy_piece(piece.color):
                            if bool:
                                if not self.in_check(piece, move):
                                    piece.add_move(move)
                            else:
                                piece.add_move(move)
                            break
                        elif self.squares[move_row][move_col].has_team_piece(piece.color):
                            break
                    else:
                        break

                    move_row += row_incr
                    move_col += col_incr

        def king_moves():
            adjs = [
                (row-1, col+0), (row-1, col+1), (row+0, col+1), (row+1, col+1),
                (row+1, col+0), (row+1, col-1), (row+0, col-1), (row-1, col-1),
            ]

            for move_row, move_col in adjs:
                if Square.in_range(move_row, move_col):
                    if self.squares[move_row][move_col].isempty_or_enemy(piece.color):
                        initial = Square(row, col)
                        final = Square(move_row, move_col)
                        move = Move(initial, final)
                        if bool:
                            if not self.in_check(piece, move):
                                piece.add_move(move)
                        else:
                            piece.add_move(move)

            # Castling
            if not piece.moved:
                # Queen side
                left_rook = self.squares[row][0].piece
                if isinstance(left_rook, Rook) and not left_rook.moved:
                    for c in range(1, 4):
                        if self.squares[row][c].has_piece():
                            break
                        if c == 3:
                            piece.left_rook = left_rook
                            initial = Square(row, 0)
                            final = Square(row, 3)
                            moveR = Move(initial, final)
                            initial = Square(row, col)
                            final = Square(row, 2)
                            moveK = Move(initial, final)
                            if bool:
                                if not self.in_check(piece, moveK) and not self.in_check(left_rook, moveR):
                                    left_rook.add_move(moveR)
                                    piece.add_move(moveK)
                            else:
                                left_rook.add_move(moveR)
                                piece.add_move(moveK)

                # King side
                right_rook = self.squares[row][7].piece
                if isinstance(right_rook, Rook) and not right_rook.moved:
                    for c in range(5, 7):
                        if self.squares[row][c].has_piece():
                            break
                        if c == 6:
                            piece.right_rook = right_rook
                            initial = Square(row, 7)
                            final = Square(row, 5)
                            moveR = Move(initial, final)
                            initial = Square(row, col)
                            final = Square(row, 6)
                            moveK = Move(initial, final)
                            if bool:
                                if not self.in_check(piece, moveK) and not self.in_check(right_rook, moveR):
                                    right_rook.add_move(moveR)
                                    piece.add_move(moveK)
                            else:
                                right_rook.add_move(moveR)
                                piece.add_move(moveK)

        if isinstance(piece, Pawn):
            pawn_moves()
        elif isinstance(piece, Knight):
            knight_moves()
        elif isinstance(piece, Bishop):
            straightline_moves([(-1, 1), (-1, -1), (1, 1), (1, -1)])
        elif isinstance(piece, Rook):
            straightline_moves([(-1, 0), (0, 1), (1, 0), (0, -1)])
        elif isinstance(piece, Queen):
            straightline_moves([(-1, 1), (-1, -1), (1, 1), (1, -1), (-1, 0), (0, 1), (1, 0), (0, -1)])
        elif isinstance(piece, King):
            king_moves()

    def _add_pieces(self, color):
        row_pawn, row_other = (6, 7) if color == 'white' else (1, 0)

        # Pawns
        for col in range(COLS):
            self.squares[row_pawn][col].piece = Pawn(color)

        # Knights
        self.squares[row_other][1].piece = Knight(color)
        self.squares[row_other][6].piece = Knight(color)

        # Bishops
        self.squares[row_other][2].piece = Bishop(color)
        self.squares[row_other][5].piece = Bishop(color)

        # Rooks
        self.squares[row_other][0].piece = Rook(color)
        self.squares[row_other][7].piece = Rook(color)

        # Queen
        self.squares[row_other][3].piece = Queen(color)

        # King
        self.squares[row_other][4].piece = King(color)

    def to_dict(self):
        board_dict = []
        for row in range(ROWS):
            row_list = []
            for col in range(COLS):
                square = self.squares[row][col]
                if square.has_piece():
                    row_list.append(square.piece.to_dict())
                else:
                    row_list.append(None)
            board_dict.append(row_list)
        return board_dict

# Game state storage
games = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/new_game', methods=['POST'])
def new_game():
    game_id = secrets.token_hex(8)
    games[game_id] = {
        'board': Board(),
        'next_player': 'white',
        'selected': None
    }
    session['game_id'] = game_id
    return jsonify({'game_id': game_id, 'board': games[game_id]['board'].to_dict(), 'next_player': 'white'})

@app.route('/get_state', methods=['GET'])
def get_state():
    game_id = session.get('game_id')
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    return jsonify({
        'board': game['board'].to_dict(),
        'next_player': game['next_player'],
        'last_move': {
            'initial': {'row': game['board'].last_move.initial.row, 'col': game['board'].last_move.initial.col},
            'final': {'row': game['board'].last_move.final.row, 'col': game['board'].last_move.final.col}
        } if game['board'].last_move else None
    })

@app.route('/select_square', methods=['POST'])
def select_square():
    game_id = session.get('game_id')
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    data = request.json
    row, col = data['row'], data['col']
    game = games[game_id]
    board = game['board']
    square = board.squares[row][col]
    
    if square.has_piece() and square.piece.color == game['next_player']:
        piece = square.piece
        board.calc_moves(piece, row, col)
        game['selected'] = {'row': row, 'col': col, 'piece': piece}
        
        valid_moves = [{'row': m.final.row, 'col': m.final.col} for m in piece.moves]
        return jsonify({'valid_moves': valid_moves})
    
    return jsonify({'valid_moves': []})

@app.route('/make_move', methods=['POST'])
def make_move():
    game_id = session.get('game_id')
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    data = request.json
    game = games[game_id]
    
    if not game['selected']:
        return jsonify({'error': 'No piece selected'}), 400
    
    board = game['board']
    selected = game['selected']
    piece = selected['piece']
    
    initial = Square(selected['row'], selected['col'])
    final = Square(data['row'], data['col'])
    move = Move(initial, final)
    
    if board.valid_move(piece, move):
        captured = board.squares[data['row']][data['col']].has_piece()
        board.move(piece, move)
        
        # Check for en passant
        if isinstance(piece, Pawn):
            if abs(move.final.row - move.initial.row) == 2:
                board.set_true_en_passant(piece)
        
        game['next_player'] = 'black' if game['next_player'] == 'white' else 'white'
        game['selected'] = None
        
        return jsonify({
            'success': True,
            'board': board.to_dict(),
            'next_player': game['next_player'],
            'captured': captured
        })
    
    return jsonify({'error': 'Invalid move'}), 400

if __name__ == '__main__':
    app.run(debug=True)