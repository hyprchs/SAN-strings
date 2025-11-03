from __future__ import annotations

import math
from functools import cache
from typing import Literal

import chess

from san_strings.constants import (
    DIAGONAL_SLIDERS,
    ORTHOGONAL_SLIDERS,
    SLIDERS,
)


def is_diagonal_slider(piece_type: chess.PieceType) -> bool:
    return piece_type in DIAGONAL_SLIDERS


def is_orthogonal_slider(piece_type: chess.PieceType) -> bool:
    return piece_type in ORTHOGONAL_SLIDERS


def is_slider(piece_type: chess.PieceType) -> bool:
    return piece_type in SLIDERS


def ordinal(n: int) -> str:
    i = int(n)
    a = abs(i)
    suffix = (
        'th' if 11 <= (a % 100) <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(a % 10, 'th')
    )
    return f'{i}{suffix}'


def attacked_by_mask(b: chess.Board, color: chess.Color) -> int:
    """
    Return a bitboard of all squares attacked by `color` on `board`,
    using python-chess's precomputed attack tables and current occupancy.
    """
    occ = b.occupied
    us = b.occupied_co[color]

    pawns = b.pawns & us
    knights = b.knights & us
    bishops = b.bishops & us
    rooks = b.rooks & us
    queens = b.queens & us
    kings = b.kings & us

    attacks = chess.BB_EMPTY

    # Pawns
    for sq in chess.scan_forward(pawns):
        attacks |= chess.BB_PAWN_ATTACKS[color][sq]

    # Knights
    for sq in chess.scan_forward(knights):
        attacks |= chess.BB_KNIGHT_ATTACKS[sq]

    # Bishops + Queens (diagonals)
    sliders_diag = bishops | queens
    for sq in chess.scan_forward(sliders_diag):
        mask = chess.BB_DIAG_MASKS[sq] & occ
        attacks |= chess.BB_DIAG_ATTACKS[sq][mask]

    # Rooks + Queens (ranks/files)
    sliders_orth = rooks | queens
    for sq in chess.scan_forward(sliders_orth):
        rmask = chess.BB_RANK_MASKS[sq] & occ
        fmask = chess.BB_FILE_MASKS[sq] & occ
        attacks |= chess.BB_RANK_ATTACKS[sq][rmask]
        attacks |= chess.BB_FILE_ATTACKS[sq][fmask]

    # Kings
    for sq in chess.scan_forward(kings):
        attacks |= chess.BB_KING_ATTACKS[sq]

    return attacks


def get_occupied_and_attacked_by_us_them_masks(
    b: chess.Board,
    *,
    pov: chess.Color = chess.WHITE,
) -> tuple[chess.Bitboard, chess.Bitboard, chess.Bitboard]:
    """
    Get masks of squares that are occupied, squares attacked by us, and squares attacked by them, where we are `pov`.
    """
    occupied_mask = b.occupied
    attacked_by_us_mask = attacked_by_mask(b, pov)
    attacked_by_them_mask = attacked_by_mask(b, not pov)
    return occupied_mask, attacked_by_us_mask, attacked_by_them_mask


def _file_rank_sliding_deltas(s1: chess.Square, s2: chess.Square) -> tuple[int, int]:
    assert s1 != s2, 's1 and s2 must be different squares'

    file_delta = chess.square_file(s2) - chess.square_file(s1)
    rank_delta = chess.square_rank(s2) - chess.square_rank(s1)

    assert 0 in (file_delta, rank_delta) or abs(file_delta) == abs(rank_delta), (
        's1 and s2 must be on the same file, rank, or diagonal; got '
        f'{chess.square_name(s1)} and {chess.square_name(s2)}'
    )

    file_delta = int(math.copysign(1, file_delta)) if file_delta else 0
    rank_delta = int(math.copysign(1, rank_delta)) if rank_delta else 0

    return file_delta, rank_delta


def _file_rank_sliding_delta_to_square_delta(
    *, file_delta: int, rank_delta: int
) -> int:
    return rank_delta * 8 + file_delta


def _sliding_delta(s1: chess.Square, s2: chess.Square) -> int:
    """
    Get the delta of the index in `chess.SQUARES` required to move
    one step from `s1` toward `s2`. Raises `AssertionError` if `s1`
    and `s2` are not on the same file, rank, or diagonal.

    >>> _sliding_delta(chess.C3, chess.F6)
    9
    >>> chess.C3 + 9 == chess.D4
    True
    """
    file_delta, rank_delta = _file_rank_sliding_deltas(s1, s2)
    return _file_rank_sliding_delta_to_square_delta(
        file_delta=file_delta,
        rank_delta=rank_delta,
    )


def _sliding_away_delta(s1: chess.Square, s2: chess.Square) -> int:
    """
    Get the delta of the index in `chess.SQUARES` required to move
    one step from `s1` away from `s2`. Raises `AssertionError` if `s1`
    and `s2` are not on the same file, rank, or diagonal.

    >>> _sliding_away_delta(chess.D4, chess.F6)
    -9
    >>> chess.D4 + -9 == chess.C3
    True
    """
    file_delta, rank_delta = _file_rank_sliding_deltas(s1, s2)
    file_delta = -file_delta
    rank_delta = -rank_delta
    return _file_rank_sliding_delta_to_square_delta(
        file_delta=file_delta,
        rank_delta=rank_delta,
    )


def extend_ray(
    from_sq: chess.Square,
    towards_sq: chess.Square,
) -> chess.Bitboard:
    """
    Get a `chess.Bitboard` of all the squares from (and including) `from_sq`
    toward `towards_sq` and continuing on to an edge of the board.

    >>> print(chess.SquareSet(extend_ray(chess.C3, chess.F6)))
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
    # noinspection PyProtectedMember
    return chess._sliding_attacks(from_sq, 0, [d]) | chess.BB_SQUARES[from_sq]


def extend_ray_away(
    from_sq: chess.Square,
    away_from_sq: chess.Square,
) -> chess.Bitboard:
    """
    Get a `chess.Bitboard` of all the squares from (and including) `from_sq`
    in the opposite direction of `away_from_sq` and continuing on to an edge of the board.

    >>> print(chess.SquareSet(extend_ray(chess.D4, chess.F6)))
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . . . . . .
    . . . 1 . . . .
    . . 1 . . . . .
    . 1 . . . . . .
    1 . . . . . . .
    """
    d = _sliding_away_delta(from_sq, away_from_sq)
    # noinspection PyProtectedMember
    return chess._sliding_attacks(from_sq, 0, [d]) | chess.BB_SQUARES[from_sq]


def _assert_from_to_squares_different(move: chess.Move) -> None:
    if move.from_square == move.to_square:
        raise RuntimeError('Unexpected same-square move')


def is_diagonal_move(move: chess.Move) -> bool:
    return abs(
        chess.square_file(move.from_square) - chess.square_file(move.to_square)
    ) == abs(chess.square_rank(move.from_square) - chess.square_rank(move.to_square))


def is_orthogonal_move(move: chess.Move) -> bool:
    return chess.square_file(move.from_square) == chess.square_file(
        move.to_square
    ) or chess.square_rank(move.from_square) == chess.square_rank(move.to_square)


@cache
def file_rank_deltas(move: chess.Move) -> tuple[int, int]:
    df = chess.square_file(move.from_square) - chess.square_file(move.to_square)
    dr = chess.square_rank(move.from_square) - chess.square_rank(move.to_square)
    return df, dr


def can_be_pawn_move(
    move: chess.Move,
    *,
    enforce_is_capture_as: bool | None = None,
    enforce_is_promotion_as: bool | None = None,
) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)
    abs_df = abs(df)
    abs_dr = abs(dr)

    # First filter out definitely-invalid pawn-like moves.
    # Can only go straight forward or left/right by 1 square
    if abs_df not in (0, 1):
        return False

    # Can only push pawns 1 or 2 squares
    if abs_dr not in (1, 2):
        return False

    # When moving 2 squares, need to check for correct from/to ranks
    if abs_dr == 2:
        # Double push can only go straight
        if df != 0:
            return False

        from_rank = chess.square_rank(move.from_square)
        to_rank = chess.square_rank(move.to_square)
        if dr == 2:
            # Must be white pawn move
            if (from_rank, to_rank) != (1, 3):
                return False
        elif dr == -2:
            # Must be black pawn move
            if (from_rank, to_rank) != (6, 4):
                return False
        else:
            raise RuntimeError('Bad logic above')

    # Require correct file delta if we only want captures or only non-captures
    if enforce_is_capture_as is not None:
        assert abs_df in (0, 1)
        if enforce_is_capture_as != (abs_df == 1):
            return False

    if enforce_is_promotion_as is not None:
        to_rank = chess.square_rank(move.to_square)
        if enforce_is_promotion_as != (to_rank in (0, 7)):
            return False

    return True


def can_be_nbrq_move_by(piece_type: chess.PieceType, move: chess.Move) -> bool:
    """
    Return `True` if `move` could be made by the given `piece_type`. Only supports
    knight, bishop, rook, and queen; use other special functions for pawn/king.
    """
    if piece_type not in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        raise ValueError(
            'This function only supports KNIGHT, BISHOP, ROOK, QUEEN piece types; '
            'use other special functions for pawns/kings.'
        )

    match piece_type:
        case chess.KNIGHT:
            return can_be_knight_move(move)
        case chess.BISHOP:
            return can_be_bishop_move(move)
        case chess.ROOK:
            return can_be_rook_move(move)
        case chess.QUEEN:
            return can_be_queen_move(move)
        case _:
            raise RuntimeError('Bad logic above')


def can_be_knight_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)
    df = abs(df)
    dr = abs(dr)
    return (df == 1 and dr == 2) or (df == 2 and dr == 1)


def can_be_bishop_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_diagonal_move(move)


def can_be_rook_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_orthogonal_move(move)


def can_be_queen_move(move: chess.Move) -> bool:
    _assert_from_to_squares_different(move)
    return is_diagonal_move(move) or is_orthogonal_move(move)


def can_be_king_move(
    move: chess.Move,
    *,
    enforce_is_castling_as: Literal['kingside', 'queenside', False, None] = None,
) -> bool:
    _assert_from_to_squares_different(move)
    df, dr = file_rank_deltas(move)

    can_be_non_castling_move = max(abs(df), abs(dr)) == 1
    can_be_kingside_castling_move = (move.from_square, move.to_square) in (
        (chess.E1, chess.G1),
        (chess.E8, chess.G8),
    )
    can_be_queenside_castling_move = (move.from_square, move.to_square) in (
        (chess.E1, chess.C1),
        (chess.E8, chess.C8),
    )
    can_be_castling_move = (
        can_be_kingside_castling_move or can_be_queenside_castling_move
    )

    if enforce_is_castling_as is not None:
        if enforce_is_castling_as == 'kingside':
            return can_be_kingside_castling_move
        if enforce_is_castling_as == 'queenside':
            return can_be_queenside_castling_move
        if enforce_is_castling_as is False:
            return can_be_non_castling_move and not can_be_castling_move
        raise ValueError(
            f'Invalid `enforce_is_castling_as` option {enforce_is_castling_as}'
        )

    return can_be_non_castling_move or can_be_castling_move


def can_require_file_disambiguator(
    *,
    move: chess.Move,
    piece_type: chess.PieceType,
) -> bool:
    if piece_type == chess.PAWN:
        raise ValueError('Did not expect this function to be called for pawns')
    if piece_type == chess.KING:
        raise ValueError('Did not expect this function to be called for kings')

    b = chess.Board.empty()
    b.set_piece_at(move.to_square, chess.Piece(piece_type, chess.WHITE))

    # Get squares from which another `piece_type` can cause ambiguity.
    ambiguity_causing_squares = (
        b.attacks_mask(move.to_square) & ~chess.BB_SQUARES[move.from_square]
    )
    if is_slider(piece_type):
        ambiguity_causing_squares &= ~extend_ray(move.to_square, move.from_square)

    # True if we have candidates on other files so ambiguity can be resolved by file disambiguation.
    from_file = chess.square_file(move.from_square)
    return bool(ambiguity_causing_squares & ~chess.BB_FILES[from_file])


def can_require_rank_disambiguator(
    *,
    move: chess.Move,
    piece_type: chess.PieceType,
) -> bool:
    if piece_type == chess.PAWN:
        raise ValueError('Did not expect this function to be called for pawns')
    if piece_type == chess.KING:
        raise ValueError('Did not expect this function to be called for kings')

    b = chess.Board.empty()
    b.set_piece_at(move.to_square, chess.Piece(piece_type, chess.WHITE))

    # Get squares from which another `piece_type` can cause ambiguity.
    ambiguity_causing_squares = (
        b.attacks_mask(move.to_square) & ~chess.BB_SQUARES[move.from_square]
    )
    if is_slider(piece_type):
        ambiguity_causing_squares &= ~extend_ray(move.to_square, move.from_square)

    # True if we have candidates on the same `from_file` so ambiguity can be resolved by rank disambiguation.
    from_file = chess.square_file(move.from_square)
    return bool(ambiguity_causing_squares & chess.BB_FILES[from_file])


def can_require_full_square_disambiguator(
    *,
    move: chess.Move,
    piece_type: chess.PieceType,
) -> bool:
    b = chess.Board.empty()
    b.set_piece_at(move.to_square, chess.Piece(piece_type, chess.WHITE))

    # Get squares from which another `piece_type` can cause ambiguity.
    ambiguity_causing_squares = (
        b.attacks_mask(move.to_square) & ~chess.BB_SQUARES[move.from_square]
    )
    if is_slider(piece_type):
        ambiguity_causing_squares &= ~extend_ray(move.to_square, move.from_square)

    # True if we simultaneously have candidates on the same `from_file` and `from_rank`.
    from_file = chess.square_file(move.from_square)
    from_rank = chess.square_rank(move.from_square)
    return bool(
        ambiguity_causing_squares & chess.BB_FILES[from_file]
        and ambiguity_causing_squares & chess.BB_RANKS[from_rank]
    )
