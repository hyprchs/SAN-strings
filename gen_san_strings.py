import chess
from typing import Literal, Set


_b = chess.Board.empty()
""" A blank `chess.Board` to use for generating moves. """


def _sign(x: int) -> Literal[-1, 0, 1]:
    """
    Get the sign of `x` as -1, 0, or 1.
    """
    return (x > 0) - (x < 0)


def _sliding_delta(s1: chess.Square, s2: chess.Square) -> int:
    """
    Get the delta of the index in `chess.SQUARES` required to move
    one step from `s1` toward `s2`. Raises `AssertionError` if `s1`
    and `s2` are not on the same file, rank, or diagonal.

    >>> delta(chess.C3, chess.F6)
    9
    >>> chess.C3 + 9 == chess.D4
    True
    """
    assert s1 != s2, "s1 and s2 must be different squares"

    x_delta = chess.square_file(s2) - chess.square_file(s1)
    y_delta = chess.square_rank(s2) - chess.square_rank(s1)

    assert 0 in (x_delta, y_delta) or abs(x_delta) == abs(y_delta), (
        "s1 and s2 must be on the same file, rank, or diagonal; got "
        f"{chess.square_name(s1)} and {chess.square_name(s2)}"
    )

    x_delta = _sign(x_delta)
    y_delta = _sign(y_delta)

    return y_delta * 8 + x_delta


def _extend_ray_from_towards(
    from_sq: chess.Square, towards_sq: chess.Square
) -> chess.Bitboard:
    """
    Get a `chess.Bitboard` of all the squares from (and including) `from_sq`
    toward `towards_sq` and continuing on to an edge of the board.

    >>> print(chess.SquareSet(_extend_ray_from_towards(chess.C3, chess.F6)))
    . . . . . . . 1
    . . . . . . 1 .
    . . . . . 1 . .
    . . . . 1 . . .
    . . . 1 . . . .
    . . 1 . . . . .
    . . . . . . . .
    . . . . . . . .
    """
    d = _sliding_delta(from_sq, towards_sq)
    return chess._sliding_attacks(from_sq, 0, [d]) | chess.BB_SQUARES[from_sq]


def get_pawn_sans(only_for_color: chess.Color | None = None) -> Set[str]:
    """
    Get all possible SAN strings for pawn moves. If `only_for_color` is
    specified, then only return pawn moves for that color; otherwise return
    pawn moves for both colors.
    """
    sans = set()

    PAWN_OCCUPIABLE = chess.SquareSet(chess.BB_ALL - chess.BB_BACKRANKS)

    w_pawn = chess.Piece.from_symbol("P")
    b_pawn = chess.Piece.from_symbol("p")

    def add_pawn_sans_for_color(color: chess.Color):
        _b.turn = color
        self_pawn = w_pawn if color == chess.WHITE else b_pawn
        other_pawn = b_pawn if color == chess.WHITE else w_pawn

        for from_square in PAWN_OCCUPIABLE:
            _b.clear_board()
            _b.set_piece_at(from_square, self_pawn)
            attacks = _b.attacks(from_square)

            # Set enemy pawns at the diagonal attacked squares
            for s in attacks:
                _b.set_piece_at(s, other_pawn)

            # Now forward moves and the diagonal captures are legal,
            # so we can just add all legal SAN moves
            for move in _b.legal_moves:
                sans.add(_b.san(move))

    if only_for_color in (chess.WHITE, None):
        add_pawn_sans_for_color(chess.WHITE)
    if only_for_color in (chess.BLACK, None):
        add_pawn_sans_for_color(chess.BLACK)

    return sans


def get_piece_sans(symbol: Literal["N", "B", "R", "Q"]) -> Set[str]:
    """
    Get all possible SAN strings for piece types that might require a
    discriminator—namely knights, bishops, rooks, and queens.
    """
    assert symbol in (
        "N",
        "B",
        "R",
        "Q",
    ), f'Invalid piece symbol {symbol}, must be in ("N", "B", "R", "Q")'

    sans = set()

    def add_sans(discriminator: str, to_square: chess.Square):
        """
        Add two SAN strings to `sans` for the given `discriminator` and `to_square`:
        one for a non-capturing move and one for a capturing move.
        """
        to_square_name = chess.square_name(to_square)
        for capture in ("", "x"):
            sans.add(f"{symbol}{discriminator}{capture}{to_square_name}")

    for to_square in chess.SQUARES:
        # We always add the un-discriminated move and capturing move
        add_sans("", to_square)

        """
        To really understand the code below, we need to understand the algorithm a human uses
        to determine whether a move from a `from_square` to a `to_square` might require a
        file, rank, and/or full-square discriminator.

        First we should consider that if moving from `from_square` to `to_square` is a legal
        move, then even if there is another piece of the same type and color on the ray which extends 
        from `to_square` to `from_square` and continues on to an edge of the board, moving that piece 
        to `to_square` would be illegal. If this piece falls between `from_square` and `to_square`,
        then the original move would not be legal, so we have a contradiction. If it is past 
        `from_square` (on the extension of the ray between the squares that continues to the edge of 
        the board), then it is not legal because it cannot jump over the piece at `from_square` to 
        reach `to_square`.

        This is important when considering disriminators because we are only interested in squares
        from which another `piece` can legally move to `to_square`, and those which might create 
        a situation where a rank, file, or full-square discriminator is necessary.

        With this in mind, the algorithm for determining whether we need a **file** discriminator
        is as follows:
          - Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
            of all the squares it can move to. These may all be considered possible `from_square`s.
          - Consider each `from_square` in `attacks`:
              - Assume the move from `from_square` to `to_square` is legal. Then we know that 
                no other `piece` on the ray from `to_square` to `from_square` is relevant because
                its move to `to_square` would be illegal. Therefore, we can subtract the bitmask 
                of that ray from `attacks` for the next step, creating a bitboard representing all
                the other possible locations of a `piece` that could legally move to `to_square` 
                given that a `piece` can legally move from `from_square` to `to_square`.
              - We also know that any squares in this bitmask which fall on the same file as
                `from_square` are not relevant for determining whether a file discriminator might be 
                required: if another `piece` were to occupy one of those squares, then its move to
                `to_square` would necessarily require a rank discriminator, not a file discriminator.
                Therefore we subtract the bitmask of all squares in `from_square`'s file from the 
                bitboard in the previous step as well.
              - We now have a bitboard of all squares from which a `piece` can legally move to 
                `to_square` (given that the move `piece` from `from_square` to `to_square` is legal)
                such that, if a `piece` really were to occupy any one of those squares, it has 
                potential to create a situation where a file discriminator is necessary. All that
                is left to do is check whether one or more files in this bitboard have any truthy bits.
                If so, then the `from_square` for this iteration can require a file discriminator.
        
        The algorithm for determining whether we need a **rank** discriminator is similar, but
        has some differences which account for the fact that a file discriminator is preferred
        over a rank discriminator when both can disambiguate the move:
          - Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
            of all the squares it can move to. These may all be considered possible `from_square`s.
          - Consider each `from_square` in `attacks`:
              - Subtract the extended ray from `to_square` towards `from_square` from `attacks`
                by the same logic as above.
              - This time, we know that any squares that **do not** fall on the same file as 
                `from_square` are not relevant for determining whether a rank discriminator might be 
                required: if another `piece` were to occupy one of those squares, then its move to
                `to_square` would necessarily preference the file discriminator, not the rank discriminator.
                Therefore we use a logical AND between the bitboard from the previous step and the
                bitmask of all squares in `from_square`'s file.
              - By the same logic as above, all that is left to do is check whether one or more ranks
                in this bitboard have any truthy bits. If so, then the `from_square` for this 
                iteration can require a rank discriminator.
        
        Determining whether we need a **full-square** discriminator is actually the simplest:
          - Take an empty board and place a `piece` on `to_square`, then get a bitboard `attacks`
            of all the squares it can move to. These may all be considered possible `from_square`s.
          - Consider each `from_square` in `attacks`:
              - Subtract the extended ray from `to_square` towards `from_square` from `attacks`
                by the same logic as above.
              - A full-square discriminator is required when there is another `piece` on `from_square`'s
                same file and another one on its same rank that can both move to `to_square`. Therefore,
                can use a logical AND between `attacks` and the bitmask of all squares in `from_square`'s
                file, then do the same for its rank, and if both of these have truthy bits, then the
                `from_square` for this iteration can require a full-square discriminator.
        
        The logic for all three of these cases can be combined into a single loop, which is what
        happens in the code below.
        """

        piece = chess.Piece.from_symbol(symbol)
        is_sliding_piece = piece.piece_type != chess.KNIGHT

        _b.clear_board()
        _b.set_piece_at(to_square, piece)
        attacks = _b.attacks(to_square)
        bb_attacks = int(attacks)

        for from_square in attacks:
            from_square_file = chess.square_file(from_square)
            from_square_rank = chess.square_rank(from_square)

            if is_sliding_piece:
                bb_ray = _extend_ray_from_towards(to_square, from_square)

            bb_from_square_file = chess.BB_FILES[from_square_file]
            bb_from_square_rank = chess.BB_RANKS[from_square_rank]

            # File Discriminator
            bb = bb_attacks
            if is_sliding_piece:
                bb &= ~bb_ray
            else:
                bb &= ~chess.BB_SQUARES[from_square]
            bb &= ~bb_from_square_file

            if any(bb_file & bb for bb_file in chess.BB_FILES):
                discriminator = chess.FILE_NAMES[from_square_file]
                add_sans(discriminator, to_square)

            # Rank Discriminator
            bb = bb_attacks
            if is_sliding_piece:
                bb &= ~bb_ray
            else:
                bb &= ~chess.BB_SQUARES[from_square]
            bb &= bb_from_square_file

            if any(bb_rank & bb for bb_rank in chess.BB_RANKS):
                discriminator = chess.RANK_NAMES[from_square_rank]
                add_sans(discriminator, to_square)

            # Full-Square Discriminator
            bb = bb_attacks
            if is_sliding_piece:
                bb &= ~bb_ray
            else:
                bb &= ~chess.BB_SQUARES[from_square]

            if (bb & bb_from_square_file) and (bb & bb_from_square_rank):
                discriminator = chess.SQUARE_NAMES[from_square]
                add_sans(discriminator, to_square)

    return sans


def get_king_sans() -> Set[str]:
    """
    Get all possible SAN strings for king moves.
    """
    sans = set()

    for to_square in chess.SQUARES:
        # Add the capturing and non-capturing SANs
        to_square_name = chess.square_name(to_square)
        sans.add(f"K{to_square_name}")
        sans.add(f"Kx{to_square_name}")

    # Add castling moves
    sans.add("O-O")
    sans.add("O-O-O")

    return sans


def main():
    pawn_sans = get_pawn_sans()
    knight_sans = get_piece_sans("N")
    bishop_sans = get_piece_sans("B")
    rook_sans = get_piece_sans("R")
    queen_sans = get_piece_sans("Q")
    king_sans = get_king_sans()
    all_sans = (
        pawn_sans | knight_sans | bishop_sans | rook_sans | queen_sans | king_sans
    )

    def sort_key(s):
        return (len(s), s)

    all_sans = sorted(all_sans, key=sort_key)
    all_sans_with_symbols = sorted(
        [san + symbol for symbol in ("", "+", "#") for san in all_sans], key=sort_key
    )

    with open("san_strings.txt", "w") as f:
        f.write("\n".join(all_sans))

    with open("san_strings_with_symbols.txt", "w") as f:
        f.write("\n".join(all_sans_with_symbols))

    print("Done!")


if __name__ == "__main__":
    main()
